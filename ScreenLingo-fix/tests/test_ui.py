"""Headless UI lifecycle tests. They do not claim Windows capture coverage."""
import os
import json
from pathlib import Path
import sys
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
sys.argv.append('--preview')
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
from main import Panel


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

    def test_region_persists_normalized(self):
        self.panel.resume_after_region=False
        self.panel.region_selected([.1,.7,.8,.2])
        self.assertEqual(self.panel.config['region'],[.1,.7,.8,.2])
        self.panel.full_screen(); self.assertIsNone(self.panel.config['region'])

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


if __name__=='__main__': unittest.main(argv=[sys.argv[0]])
