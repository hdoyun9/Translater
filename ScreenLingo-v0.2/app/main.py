"""ScreenLingo: a visible, resizable capture frame and local translation."""
import ctypes
import json
import os
from pathlib import Path
import sys
import time

from PySide6.QtCore import Qt, QTimer, QProcess, QRectF, QRect, Signal, QAbstractNativeEventFilter
from PySide6.QtGui import QColor, QPainter, QFont, QFontMetrics, QPen, QFontDatabase
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSlider, QMessageBox, QFrame, QDialog, QPlainTextEdit, QScrollArea, QCheckBox)
from models import ROOT, DATA, required, find_model, translation_ready
from overlay_layout import layout_items, TEXT_FLAGS
from capture_frame import CaptureFrame
from glossary_ui import GlossaryDialog
from terms import clean_glossary

PREVIEW = '--preview' in sys.argv
IS_WINDOWS = sys.platform == 'win32'
_fonts_loaded=False


def initialize_fonts():
    global _fonts_loaded
    if _fonts_loaded: return
    if IS_WINDOWS:
        # Register Windows CJK fonts explicitly: the offscreen/platform font
        # database can lack them even when the actual font files are installed.
        folder=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
        for name in ('malgun.ttf','meiryo.ttc'):
            if (folder/name).is_file(): QFontDatabase.addApplicationFont(str(folder/name))
    _fonts_loaded=True


STYLE = '''
QWidget { background: #101923; color: #e9f0f6; font-family: "Malgun Gothic", "Noto Sans CJK KR"; font-size: 13px; }
QLabel { background: transparent; }
QLabel#brand { color:#73e0bd; font-size:12px; font-weight:bold; }
QLabel#title { font-size:26px; font-weight:bold; }
QLabel#muted { color:#9caebd; }
QLabel#status { color:#73e0bd; background:#172e2b; padding:14px; border-radius:10px; }
QFrame#card { background:#172330; border:1px solid #263747; border-radius:12px; }
QPushButton { background:#253545; border:0; border-radius:8px; padding:11px 15px; }
QPushButton:hover { background:#344b5f; }
QPushButton#primary { background:#73e0bd; color:#09291f; font-weight:bold; }
QPushButton#danger { background:#3a252d; color:#ffb8bd; }
QPushButton:disabled { background:#1c2834; color:#617587; }
QComboBox { background:#253545; padding:9px; border:1px solid #3c5367; border-radius:6px; }
QSlider::groove:horizontal { background:#2c4152; height:5px; }
QSlider::handle:horizontal { background:#73e0bd; width:14px; margin:-5px 0; border-radius:7px; }
'''


def exclude_capture(widget):
    if not IS_WINDOWS:
        return PREVIEW
    f = ctypes.windll.user32.SetWindowDisplayAffinity
    f.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    f.restype = ctypes.c_int
    return bool(f(int(widget.winId()), 0x11))


class Overlay(QWidget):
    def __init__(self):
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self.lines = []
        self.font_size = 15
        self.enabled = True
        self.region = None
        self.show()
        self.excluded = exclude_capture(self)

    def clear(self):
        self.lines = []
        self.update()

    def paintEvent(self, event):
        if not self.enabled: return
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.region:
            x,y,w,h=self.region
            painter.setClipRect(QRectF(x*self.width(),y*self.height(),w*self.width(),h*self.height()))
        items=layout_items(self.lines,self.width(),self.height(),self.font_size)
        # Opaque masks are painted at EVERY original glyph's position, even if
        # a translation needs a larger box. Moving text never exposes the source.
        for item in items:
            background=QColor(*item['background'])
            for mask in item['masks']:
                painter.fillRect(mask,background)
        for item in items:
            background=QColor(*item['background'])
            painter.fillRect(item['rect'],background)
            painter.setFont(item['font'])
            r,g,b=item['background']
            painter.setPen(QColor('#151515') if .299*r+.587*g+.114*b>145 else QColor('#ffffff'))
            text=item['text']
            if item['overflow']:
                text=f"{item['index']+1}번 번역 · 전체 번역 보기"
            painter.drawText(item['rect'].adjusted(3,3,-3,-3),TEXT_FLAGS,text)


class Hotkeys(QAbstractNativeEventFilter):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.registered = []
        if IS_WINDOWS:
            for ident, key in [(1,0x77),(2,0x78),(3,0x79)]:
                if ctypes.windll.user32.RegisterHotKey(None, ident, 0x4003, key):
                    self.registered.append(ident)

    def nativeEventFilter(self, event_type, message):
        if IS_WINDOWS:
            from ctypes.wintypes import MSG
            msg = MSG.from_address(int(message))
            if msg.message == 0x0312:
                if msg.wParam == 1:
                    self.panel.toggle()
                elif msg.wParam == 2:
                    self.panel.toggle_overlay()
                elif msg.wParam == 3:
                    self.panel.close()
                return True, 0
        return False, 0

    def close(self):
        if IS_WINDOWS:
            for ident in self.registered:
                ctypes.windll.user32.UnregisterHotKey(None, ident)


class Panel(QWidget):
    def __init__(self):
        super().__init__()
        initialize_fonts()
        self.setWindowTitle('ScreenLingo 0.2 · 번역 범위 창 업데이트')
        self.setMinimumWidth(480)
        self.resize(520,min(820,QApplication.primaryScreen().availableGeometry().height()-60))
        self.setStyleSheet(STYLE)
        self.worker = None
        self.downloader = None
        self.buffers = {}
        self.running = False
        self.busy = False
        self.signature = None
        self.worker_warning = ''
        self.last_frame = 0
        self.latest_results=[]
        self.capture_revision=0
        self.frame_editing=False
        self.config = {'source':'auto','interval':1200,'font':15,'region':None,'consent':False,
                       'direction':'auto','glossary':{},'katakana':True}
        if not PREVIEW:
            try:
                stored = json.loads((DATA/'settings.json').read_text(encoding='utf-8'))
                for key in self.config:
                    if key in stored:
                        self.config[key] = stored[key]
            except (OSError, ValueError, TypeError):
                pass
        # Treat settings as untrusted input, including interrupted/manual edits.
        if self.config['source'] not in ('en','ja','zh','auto'): self.config['source']='en'
        if self.config['interval'] not in (700,1200,2000): self.config['interval']=1200
        if not isinstance(self.config['font'],int): self.config['font']=15
        self.config['font']=max(10,min(28,self.config['font']))
        region=self.config['region']
        if (not isinstance(region,list) or len(region)!=4 or
            not all(isinstance(x,(float,int)) and 0<=x<=1 for x in region)):
            self.config['region']=None
        self.config['consent']=self.config['consent'] is True
        if self.config['direction'] not in ('auto','horizontal','vertical'): self.config['direction']='auto'
        self.config['glossary']=clean_glossary(self.config['glossary'])
        self.config['katakana']=self.config['katakana'] is not False
        self.results_dialog=None
        self.overlay = Overlay()
        self.capture_frame=CaptureFrame(self.config['region'])
        self.config['region']=self.capture_frame.normalized_region()
        self.overlay.region=self.config['region']
        outer=QVBoxLayout(self); outer.setContentsMargins(0,0,0,0)
        scroll=QScrollArea(self); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        content=QWidget(); scroll.setWidget(content); outer.addWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(26,24,26,24)
        layout.setSpacing(14)
        self.label(layout,'SCREENLINGO  /  0.2 BETA','brand')
        self.label(layout,'화면은 그대로,\n언어는 한국어로.','title')
        self.label(layout,'주 모니터 · 로컬 문자 인식 + 로컬 번역','muted')
        self.status = self.label(layout,'준비 중 · 아직 화면을 읽지 않습니다.','status')
        self.status.setWordWrap(True)
        card = QFrame(); card.setObjectName('card')
        controls = QVBoxLayout(card); controls.setContentsMargins(16,16,16,16); controls.setSpacing(12)
        self.label(controls,'원문 언어 → 한국어')
        self.language = QComboBox()
        for label, code in [('영어','en'),('일본어','ja'),('중국어 (간체)','zh'),('자동 · 영어 / 일본어 / 중국어','auto')]:
            self.language.addItem(label, code)
        self.language.setCurrentIndex(max(0, self.language.findData(self.config['source'])))
        controls.addWidget(self.language)
        self.language.currentIndexChanged.connect(self.change_language)
        self.label(controls,'만화 글자 방향')
        self.direction = QComboBox()
        for label,code in [('자동 판별','auto'),('가로쓰기','horizontal'),('세로쓰기 · 오른쪽 열부터','vertical')]:
            self.direction.addItem(label,code)
        self.direction.setCurrentIndex(max(0,self.direction.findData(self.config['direction'])))
        self.direction.currentIndexChanged.connect(self.change_direction)
        controls.addWidget(self.direction)
        self.label(controls,'일본어 만화는 원문 언어를 일본어 또는 자동으로 선택하세요.','muted').setWordWrap(True)
        self.label(controls,'초록색 번역 창 안쪽만 읽습니다.\n상단 바를 끌어 이동하고 테두리·모서리를 끌어 크기를 조절하세요.','muted').setWordWrap(True)
        self.katakana=QCheckBox('가타카나 이름·외래어 표기 일관성 유지')
        self.katakana.setChecked(self.config['katakana'])
        self.katakana.toggled.connect(self.change_katakana); controls.addWidget(self.katakana)
        self.label(controls,'공식 표기나 원하는 이름은 사전에 등록하면 우선 적용됩니다.','muted').setWordWrap(True)
        terms_row=QHBoxLayout()
        self.glossary_button=self.button(terms_row,f"이름·외래어 사전 ({len(self.config['glossary'])})",self.edit_glossary)
        self.button(terms_row,'번역 창 앞으로',self.show_capture_frame)
        controls.addLayout(terms_row)
        self.font_label = self.label(controls,'번역 글자 크기')
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(10,28); self.font_slider.setValue(int(self.config['font']))
        self.font_slider.valueChanged.connect(self.change_font); controls.addWidget(self.font_slider)
        self.label(controls,'갱신 간격 (처리 시간은 별도로 소요)','muted')
        self.interval = QComboBox()
        for name,value in [('빠르게 · 0.7초',700),('보통 · 1.2초',1200),('여유롭게 · 2초',2000)]:
            self.interval.addItem(name,value)
        self.interval.setCurrentIndex(max(0,self.interval.findData(self.config['interval'])))
        self.interval.currentIndexChanged.connect(self.change_interval); controls.addWidget(self.interval)
        layout.addWidget(card)
        footer=QWidget()
        footer_layout=QVBoxLayout(footer); footer_layout.setContentsMargins(20,10,20,14)
        outer.addWidget(footer)
        actions = QHBoxLayout()
        self.start_button = self.button(actions,'번역 시작',self.toggle,'primary')
        self.overlay_button = self.button(actions,'번역 숨기기',self.toggle_overlay)
        footer_layout.addLayout(actions)
        results_actions=QHBoxLayout()
        self.button(results_actions,'전체 번역 보기',self.show_results)
        self.button(results_actions,'전체 종료',self.close,'danger')
        footer_layout.addLayout(results_actions)
        privacy = self.label(footer_layout,'화면·글자 외부 전송 없음 · 캡처 파일 저장 없음\n창을 닫으면 화면 인식도 완전히 종료됩니다.','muted')
        privacy.setWordWrap(True)
        self.label(footer_layout,'Ctrl+Alt+F8 일시정지   F9 번역 표시   F10 종료','muted')
        self.timer = QTimer(self); self.timer.timeout.connect(self.request_capture)
        self.save_timer=QTimer(self); self.save_timer.setSingleShot(True); self.save_timer.timeout.connect(self.save)
        self.capture_frame.changed.connect(self.frame_changed)
        self.capture_frame.editing.connect(self.frame_editing_changed)
        self.capture_frame.close_requested.connect(self.close)
        self.watchdog = QTimer(self); self.watchdog.timeout.connect(self.expire_stale)
        self.watchdog.start(1000)
        self.overlay.font_size = int(self.config['font'])
        self.hotkeys = Hotkeys(self)
        QApplication.instance().installNativeEventFilter(self.hotkeys)
        self.show()
        self.excluded = exclude_capture(self)
        self.capture_frame.show()
        self.capture_frame.excluded=exclude_capture(self.capture_frame)
        if PREVIEW:
            self.status.setText('● 로컬 번역 준비 완료 · 화면 전송 없음')
        else:
            QTimer.singleShot(350,self.autostart)

    def label(self, layout, text, name=None):
        label = QLabel(text)
        if name: label.setObjectName(name)
        layout.addWidget(label)
        return label

    def button(self, layout, text, callback, name=None):
        button = QPushButton(text)
        if name: button.setObjectName(name)
        button.clicked.connect(callback); layout.addWidget(button)
        return button

    def save(self):
        if PREVIEW: return
        try:
            DATA.mkdir(parents=True,exist_ok=True)
            target = DATA/'settings.json'
            temp = DATA/'settings.tmp'
            temp.write_text(json.dumps(self.config),encoding='utf-8')
            temp.replace(target)
        except OSError:
            self.status.setText('설정을 저장할 수 없습니다. 이번 실행에는 적용됩니다.')

    def autostart(self):
        if not self.config.get('consent'):
            answer = QMessageBox.question(self,'첫 실행 안내',
                '이 앱이 열려 있는 동안 초록색 번역 창 안쪽의 글자만 읽어 한국어로 표시합니다.\n\n'
                '화면과 글자는 PC 밖으로 전송하지 않고 파일로 저장하지 않습니다.\n'
                '창을 닫으면 종료되며 자동 실행·트레이 상주는 없습니다.\n'
                '번역 모델이 없으면 다운로드 전에 별도로 안내합니다.\n\n'
                '지금 시작할까요? 다음 실행부터는 자동으로 시작합니다.',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                self.status.setText('대기 중 · 화면을 읽지 않습니다.'); return
            self.config['consent'] = True; self.save()
        self.start()

    def start(self):
        if PREVIEW or self.downloader or self.running: return
        if not self.config.get('consent'):
            self.autostart(); return
        if not self.excluded or not self.overlay.excluded or not self.capture_frame.excluded:
            self.status.setText('번역창 캡처 제외 기능을 사용할 수 없어 시작하지 않았습니다. Windows 10 2004 이상이 필요합니다.'); return
        source = self.language.currentData()
        if not translation_ready('en' if source=='auto' else source):
            self.ask_download(source); return
        self.running = True; self.busy = False; self.signature = None
        self.start_button.setText('일시정지'); self.status.setText('로컬 문자 인식 엔진 준비 중…')
        self.worker = self.make_process('worker.py',source)
        self.worker.start()

    def make_process(self, script, source):
        process = QProcess(self)
        program = str(Path(sys.executable).with_name('python.exe')) if IS_WINDOWS else sys.executable
        process.setProgram(program)
        process.setArguments(['-B','-u','-X','utf8',str(ROOT/'app'/script),source])
        process.setWorkingDirectory(str(ROOT/'app'))
        self.buffers[process] = b''
        process.readyReadStandardOutput.connect(lambda p=process:self.read_process(p))
        # Drain stderr without keeping possibly sensitive diagnostics on disk.
        process.readyReadStandardError.connect(lambda p=process:p.readAllStandardError())
        process.finished.connect(lambda code,status,p=process:self.process_finished(p,code))
        process.errorOccurred.connect(lambda error,p=process:self.process_failed(p,error))
        return process

    def process_failed(self, process, error):
        if error == QProcess.FailedToStart:
            if process is self.worker:
                self.stop()
            if process is self.downloader:
                self.downloader = None
            self.status.setText('실행 파일을 시작할 수 없습니다. ZIP을 전체 압축 해제했는지 확인해 주세요.')

    def process_finished(self, process, code):
        # QProcess can still have unread output when finished is emitted.
        # Preserve a specific worker error before falling back to its exit code.
        self.read_process(process)
        if process is self.worker and self.running:
            self.running = False; self.busy = False; self.timer.stop(); self.overlay.clear()
            self.start_button.setText('번역 시작')
            if code != 0:
                self.status.setText(f'화면 인식·번역 작업이 종료되었습니다. 종료 코드: 0x{code & 0xffffffff:08X}. 다시 시작해 주세요.')
        if process is self.worker:
            self.worker = None
        if process is self.downloader:
            self.downloader = None; self.start_button.setEnabled(True); self.language.setEnabled(True)
            if code == 0:
                QTimer.singleShot(0,self.start)
        self.buffers.pop(process,None)
        process.deleteLater()

    def read_process(self, process):
        buffer = self.buffers.get(process,b'') + bytes(process.readAllStandardOutput())
        while b'\n' in buffer:
            raw, buffer = buffer.split(b'\n',1)
            try:
                data = json.loads(raw)
            except (ValueError,UnicodeError):
                continue
            if process is not self.worker and process is not self.downloader:
                continue
            kind = data.get('type')
            if kind in ('detected','partial','frame') and data.get('revision',0)!=self.capture_revision:
                # A frame already being translated can finish after a resize.
                # Never paint its obsolete coordinates onto the new region.
                if kind=='frame':
                    self.busy=False
                    QTimer.singleShot(0,self.request_capture)
                continue
            if kind == 'ready' and self.running:
                self.worker_warning = (' · OCR 미설치: '+', '.join(data['missing'])) if data.get('missing') else ''
                if data.get('missing_models'): self.worker_warning += ' · 모델 미설치: '+', '.join(data['missing_models'])
                self.status.setText('● 번역 중 · 초록색 창 안쪽만 읽습니다.' +
                    ('\n설치되지 않은 OCR 언어: '+', '.join(data['missing']) if data.get('missing') else ''))
                self.timer.start(self.interval.currentData()); self.request_capture()
            elif kind == 'detected' and self.running:
                self.signature=data['signature']
                self.last_frame=time.monotonic()
                self.overlay.lines=data.get('lines',[]); self.overlay.update()
                self.latest_results=self.overlay.lines
                self.status.setText(f"● {len(self.overlay.lines)}개 문장 영역 인식 · 번역 중…"+self.worker_warning)
                self.refresh_results()
            elif kind in ('partial','frame') and self.running:
                self.last_frame=time.monotonic()
                self.signature=data['signature']; self.overlay.lines=data['lines']; self.overlay.update()
                self.latest_results=self.overlay.lines
                if kind=='frame': self.busy=False
                completed=sum(not item.get('pending') for item in data['lines'])
                failed=sum(bool(item.get('failed')) for item in data['lines'])
                self.status.setText(f"● 번역 {completed}/{len(data['lines'])}개 영역 · {data['seconds']}초"+self.worker_warning+
                    (f"\n확인 필요 {failed}개 · 전체 번역 보기에서 원인을 확인하세요." if failed else '')+
                    ('\n인식된 글자가 없습니다. 이미지 확대 또는 원문 언어를 확인하세요.' if not data['lines'] else ''))
                self.refresh_results()
            elif kind == 'progress':
                mb = data['bytes']//1048576
                total = data.get('total',0)//1048576
                self.status.setText(f"모델 다운로드 · {data['pair']} · {mb} / {total or '?'} MB\n화면을 읽지 않는 상태입니다.")
            elif kind == 'error':
                message = data.get('message','작업에 실패했습니다.')
                if process is self.worker: self.stop()
                self.status.setText(message)
        if process in self.buffers:
            self.buffers[process] = buffer

    def request_capture(self):
        if not self.running or self.busy or self.frame_editing or not self.worker or self.worker.state() != QProcess.Running:
            return
        self.busy = True
        packet = {'type':'capture','region':self.config['region'],'direction':self.config['direction'],
                  'revision':self.capture_revision,'glossary':self.config['glossary'],'katakana':self.config['katakana']}
        self.worker.write((json.dumps(packet)+'\n').encode())

    def expire_stale(self):
        if not self.busy and self.last_frame and time.monotonic()-self.last_frame > 8:
            self.overlay.clear()

    def stop(self):
        self.timer.stop(); self.running = False; self.busy = False
        self.overlay.clear(); self.signature = None
        process, self.worker = self.worker, None
        if process:
            process.kill(); process.waitForFinished(1500)
        self.start_button.setText('번역 시작')
        self.status.setText('일시정지 · 화면 인식과 번역이 중단되었습니다.')

    def toggle(self):
        if self.running: self.stop()
        else: self.start()

    def toggle_overlay(self):
        self.overlay.enabled = not self.overlay.enabled; self.overlay.update()
        self.overlay_button.setText('번역 숨기기' if self.overlay.enabled else '번역 표시')

    def ask_download(self, source):
        answer = QMessageBox.question(self,'로컬 번역 모델 준비',
            '선택한 언어의 번역 모델을 인터넷에서 다운로드합니다.\n'
            '언어에 따라 수백 MB와 몇 분이 필요할 수 있습니다.\n'
            '다운로드 중에는 화면을 읽지 않습니다. 이후 번역은 오프라인입니다.\n\n'
            '출처: Argos Open Technologies (argos-net.com)\n다운로드할까요?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            self.status.setText('모델 준비 대기 · 화면을 읽지 않습니다.'); return
        self.downloader = self.make_process('models.py',source)
        self.start_button.setEnabled(False); self.language.setEnabled(False)
        self.status.setText('모델 연결 중 · 화면을 읽지 않습니다.')
        self.downloader.start()

    def change_language(self):
        was_running = self.running; self.stop()
        self.config['source'] = self.language.currentData(); self.save()
        if was_running: self.start()

    def change_direction(self):
        self.config['direction']=self.direction.currentData(); self.save()
        was_running=self.running
        self.stop()
        if was_running: self.start()

    def show_results(self):
        if self.results_dialog is None:
            self.results_dialog=QDialog(self)
            self.results_dialog.setWindowTitle('전체 번역 · 인식된 모든 문장')
            self.results_dialog.resize(600,650)
            layout=QVBoxLayout(self.results_dialog)
            self.results_text=QPlainTextEdit()
            self.results_text.setReadOnly(True)
            layout.addWidget(self.results_text)
        self.refresh_results()
        self.results_dialog.show()
        if not exclude_capture(self.results_dialog) and self.running:
            self.stop()
        self.results_dialog.raise_()

    def refresh_results(self):
        if self.results_dialog is None: return
        rows=[]
        for index,line in enumerate(self.latest_results,1):
            rows.append(f"{index}. {line['text']}"+(f"\n원문: {line['original']}" if line.get('original') else '')+
                        (f"\n확인: {line['message']}" if line.get('message') else ''))
        scroll=self.results_text.verticalScrollBar().value()
        self.results_text.setPlainText('\n\n'.join(rows) or '아직 인식된 문장이 없습니다.')
        self.results_text.verticalScrollBar().setValue(scroll)

    def change_font(self, value):
        self.config['font'] = value; self.overlay.font_size = value; self.overlay.update(); self.save()

    def change_interval(self):
        self.config['interval'] = self.interval.currentData(); self.timer.setInterval(self.interval.currentData()); self.save()

    def frame_changed(self,region):
        self.config['region']=region
        self.overlay.region=region
        self.capture_revision+=1
        self.overlay.clear()
        self.save_timer.start(350)

    def frame_editing_changed(self,editing):
        self.frame_editing=editing
        if editing: self.overlay.clear()
        else: self.request_capture()

    def show_capture_frame(self):
        self.capture_frame.show(); self.capture_frame.raise_()

    def change_katakana(self,enabled):
        self.config['katakana']=enabled
        self.capture_revision+=1; self.overlay.clear(); self.save()
        self.request_capture()

    def edit_glossary(self):
        dialog=GlossaryDialog(self.config['glossary'],self)
        dialog.show()
        if not exclude_capture(dialog) and self.running: self.stop()
        if dialog.exec()==QDialog.Accepted:
            self.config['glossary']=dialog.entries()
            self.glossary_button.setText(f"이름·외래어 사전 ({len(self.config['glossary'])})")
            self.capture_revision+=1; self.overlay.clear(); self.save(); self.request_capture()
        dialog.deleteLater()

    def closeEvent(self,event):
        self.stop(); self.watchdog.stop()
        self.save_timer.stop(); self.save()
        if self.downloader:
            self.downloader.kill(); self.downloader.waitForFinished(1500)
        self.hotkeys.close(); self.overlay.close()
        self.capture_frame.allow_close=True; self.capture_frame.close()
        event.accept(); QApplication.instance().quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('ScreenLingo')
    if PREVIEW:
        from PySide6.QtGui import QFontDatabase
        font = ROOT.parent/'build'/'NotoSansCJKkr-Regular.otf'
        if font.exists(): QFontDatabase.addApplicationFont(str(font))
    if not IS_WINDOWS and not PREVIEW:
        QMessageBox.warning(None,'Windows 전용','Windows 10 2004 이상 / Windows 11 x64에서 실행해 주세요.'); return 1
    panel = Panel()
    if PREVIEW:
        def preview():
            panel.grab().save(str(ROOT.parent/'build'/'ui-preview.png'))
            panel.close()
        QTimer.singleShot(500,preview)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
