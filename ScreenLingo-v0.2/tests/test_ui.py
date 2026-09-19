"""Headless UI lifecycle tests. They do not claim Windows capture coverage."""
import os
import json
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
sys.argv.append('--preview')
from PySide6.QtCore import QProcess, QPoint, Qt
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtTest import QTest
from main import Panel
import main
from glossary_ui import GlossaryDialog
from overlay_layout import layout_items


class FakeProcess:
    def __init__(self):
        self.killed=False; self.waited=False; self.writes=[]
        self.stdout=b''; self.deleted=False
    def kill(self): self.killed=True
    def waitForFinished(self,timeout): self.waited=True; return True
    def state(self): return QProcess.Running
    def write(self,data): self.writes.append(data)
    def readAllStandardOutput(self):
        data,self.stdout=self.stdout,b''
        return data
    def deleteLater(self): self.deleted=True


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self): self.panel=Panel()
    def tearDown(self): self.panel.close()

    def test_pause_kills_worker(self):
        worker=FakeProcess(); self.panel.worker=worker; self.panel.running=True
        self.panel.overlay.lines=[{'text':'test','box':[0,0,.1,.1]}]
        self.panel.stop()
        self.assertTrue(worker.killed); self.assertTrue(worker.waited)
        self.assertFalse(self.panel.running); self.assertEqual(self.panel.overlay.lines,[])
        self.assertIsNone(self.panel.worker)

    def test_no_capture_when_paused(self):
        worker=FakeProcess(); self.panel.worker=worker
        self.panel.request_capture(); self.assertEqual(worker.writes,[])

    def test_only_one_capture_inflight(self):
        worker=FakeProcess(); self.panel.worker=worker; self.panel.running=True
        self.panel.request_capture(); self.panel.request_capture()
        self.assertEqual(len(worker.writes),1)

    def test_close_kills_download(self):
        download=FakeProcess(); self.panel.downloader=download
        self.panel.close()
        self.assertTrue(download.killed); self.assertTrue(download.waited)
        self.panel.downloader=None

    def test_hide_does_not_claim_pause(self):
        self.panel.running=True
        self.panel.toggle_overlay()
        self.assertFalse(self.panel.overlay.enabled)
        self.assertTrue(self.panel.running)

    def test_frame_is_visible_and_its_interior_does_not_intercept_input(self):
        frame=self.panel.capture_frame
        self.assertTrue(frame.isVisible())
        self.assertFalse(frame.mask().contains(frame.content_rect().center()))
        self.assertTrue(frame.mask().contains(QPoint(3,3)))
        self.assertEqual(frame.grab().toImage().pixelColor(frame.content_rect().center()).alpha(),0)
        labels={button.text() for button in self.panel.findChildren(QPushButton)}
        self.assertNotIn('영역 지정',labels); self.assertNotIn('화면 전체',labels)

    def test_frame_move_and_resize_update_only_inner_capture_region(self):
        frame=self.panel.capture_frame
        frame.set_region([.1,.2,.5,.4]); self.app.processEvents()
        for actual,expected in zip(self.panel.config['region'],[.1,.2,.5,.4]):
            self.assertAlmostEqual(actual,expected,delta=.004)
        worker=FakeProcess(); self.panel.worker=worker; self.panel.running=True
        self.panel.request_capture()
        packet=json.loads(worker.writes[-1])
        self.assertEqual(packet['region'],frame.normalized_region())
        self.assertEqual(packet['revision'],self.panel.capture_revision)

    def test_drag_header_moves_frame_and_edge_resizes_it(self):
        frame=self.panel.capture_frame
        frame.set_region([.15,.2,.4,.4]); self.app.processEvents()
        initial=frame.geometry()
        QTest.mousePress(frame,Qt.LeftButton,pos=QPoint(80,20))
        self.assertTrue(self.panel.frame_editing)
        QTest.mouseMove(frame,QPoint(100,40))
        QTest.mouseRelease(frame,Qt.LeftButton,pos=QPoint(80,20))
        self.assertFalse(self.panel.frame_editing)
        self.assertEqual(frame.x(),initial.x()+20)
        before=frame.size()
        corner=QPoint(frame.width()-3,frame.height()-3)
        QTest.mousePress(frame,Qt.LeftButton,pos=corner)
        QTest.mouseMove(frame,corner+QPoint(25,25))
        QTest.mouseRelease(frame,Qt.LeftButton,pos=corner)
        self.assertEqual(frame.width(),before.width()+25)
        self.assertEqual(frame.height(),before.height()+25)

    def test_moving_frame_drops_old_results_and_suspends_new_capture(self):
        worker=FakeProcess(); self.panel.worker=worker; self.panel.running=True
        self.panel.buffers[worker]=b''
        self.panel.request_capture()
        old_revision=self.panel.capture_revision
        self.panel.frame_editing_changed(True)
        self.panel.frame_changed([.1,.2,.4,.4])
        worker.stdout=(json.dumps({'type':'frame','revision':old_revision,'signature':[],
            'lines':[{'text':'obsolete'}],'seconds':1})+'\n').encode()
        self.panel.read_process(worker)
        self.assertEqual(self.panel.overlay.lines,[])
        self.assertFalse(self.panel.busy)
        self.panel.request_capture(); self.assertEqual(len(worker.writes),1)
        self.panel.frame_editing_changed(False)
        self.assertEqual(len(worker.writes),2)

    def test_closing_panel_also_closes_frame(self):
        self.panel.close()
        self.assertFalse(self.panel.capture_frame.isVisible())

    def test_frame_is_clamped_to_primary_screen(self):
        self.panel.capture_frame.set_region([.99,.99,1,1])
        self.app.processEvents()
        x,y,w,h=self.panel.config['region']
        self.assertGreaterEqual(x,0); self.assertGreaterEqual(y,0)
        self.assertLessEqual(x+w,1); self.assertLessEqual(y+h,1)

    def test_glossary_editor_validates_duplicate_and_empty_targets(self):
        dialog=GlossaryDialog({'カタリナ':'카타리나'},self.panel)
        dialog.add_row('ｶﾀﾘﾅ','다른 표기')
        with self.assertRaises(ValueError): dialog.entries()
        dialog.table.removeRow(1)
        self.assertEqual(dialog.entries(),{'カタリナ':'카타리나'})
        dialog.add_row('東京','')
        with self.assertRaises(ValueError): dialog.entries()
        dialog.deleteLater()

    def test_frame_and_dictionary_are_saved_as_settings(self):
        self.panel.config['glossary']={'カタリナ':'카타리나'}
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(main,'DATA',Path(folder)),patch.object(main,'PREVIEW',False):
                self.panel.save()
            saved=json.loads((Path(folder)/'settings.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['region'],self.panel.capture_frame.normalized_region())
            self.assertEqual(saved['glossary'],{'カタリナ':'카타리나'})

    def test_final_worker_error_is_preserved(self):
        worker=FakeProcess(); self.panel.worker=worker; self.panel.running=True
        self.panel.buffers[worker]=b''
        message='번역 모델을 읽지 못했습니다.'
        worker.stdout=(json.dumps({'type':'error','message':message})+'\n').encode()
        self.panel.process_finished(worker,1)
        self.assertEqual(self.panel.status.text(),message)
        self.assertFalse(self.panel.running)
        self.assertIsNone(self.panel.worker)
        self.assertNotIn(worker,self.panel.buffers)
        self.assertTrue(worker.deleted)

    def test_unexpected_exit_reports_code_without_diagnosing_installation(self):
        worker=FakeProcess(); self.panel.worker=worker; self.panel.running=True
        self.panel.busy=True; self.panel.buffers[worker]=b''
        self.panel.process_finished(worker,-1073741819)
        self.assertIn('0xC0000005',self.panel.status.text())
        self.assertNotIn('설치',self.panel.status.text())
        self.assertFalse(self.panel.running)
        self.assertFalse(self.panel.busy)
        self.assertIsNone(self.panel.worker)

    def test_opaque_mask_covers_source_near_bottom_edge(self):
        self.panel.overlay.region=None
        self.panel.overlay.resize(400,300)
        self.panel.overlay.lines=[{'text':'한국어 번역','box':[.1,.94,.3,.04],
            'background':[250,250,250]}]
        self.app.processEvents()
        image=self.panel.overlay.grab().toImage()
        self.assertEqual(image.pixelColor(45,285).alpha(),255)
        self.assertEqual(image.pixelColor(45,285).red(),250)

    def test_overlay_never_draws_outside_capture_frame(self):
        overlay=self.panel.overlay; overlay.resize(400,300)
        overlay.region=[.25,.25,.5,.5]
        overlay.lines=[{'text':'한국어','box':[0,0,1,1],'background':[250,250,250]}]
        image=overlay.grab().toImage()
        self.assertEqual(image.pixelColor(50,50).alpha(),0)
        self.assertEqual(image.pixelColor(150,100).alpha(),255)

    def test_no_overlay_entry_is_silently_dropped(self):
        lines=[{'text':str(i)+'번 번역','box':[.1,i/80,.3,.01]} for i in range(75)]
        self.assertEqual(len(layout_items(lines,800,600,15)),75)

    def test_complete_results_remain_readable_after_pause(self):
        self.panel.latest_results=[{'text':'끝까지 표시합니다.'*500}]
        self.panel.stop()
        self.panel.show_results()
        self.assertTrue(self.panel.results_text.toPlainText().endswith('끝까지 표시합니다.'))
        self.assertGreater(len(self.panel.results_text.toPlainText()),1200)

    def test_partial_results_do_not_unlock_another_capture(self):
        worker=FakeProcess(); self.panel.worker=worker; self.panel.running=True; self.panel.busy=True
        self.panel.buffers[worker]=b''
        worker.stdout=(json.dumps({'type':'partial','signature':[],'revision':self.panel.capture_revision,
            'lines':[{'text':'첫 문장','pending':False,'failed':False}], 'seconds':1})+'\n').encode()
        self.panel.read_process(worker)
        self.assertTrue(self.panel.busy)
        self.assertEqual(self.panel.latest_results[0]['text'],'첫 문장')


if __name__=='__main__': unittest.main(argv=[sys.argv[0]])
