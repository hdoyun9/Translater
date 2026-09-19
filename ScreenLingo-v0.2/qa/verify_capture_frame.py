"""Windows native hit test of app-owned test windows; no desktop capture."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
sys.argv.append('--preview')
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QApplication,QWidget
from main import initialize_fonts,exclude_capture
from capture_frame import CaptureFrame
app=QApplication([]); initialize_fonts()
background=QWidget(None,Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.Tool)
background.setGeometry(60,80,700,500); background.show()
frame=CaptureFrame(); frame.setGeometry(100,120,500,320); frame.show(); frame.raise_()
assert exclude_capture(frame),'Windows could not exclude the capture frame'
error=[]
def verify():
    try:
        user=ctypes.windll.user32
        user.WindowFromPoint.argtypes=[wintypes.POINT]; user.WindowFromPoint.restype=wintypes.HWND
        user.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT]; user.GetAncestor.restype=wintypes.HWND
        def owner(point):
            ratio=frame.devicePixelRatioF()
            hwnd=user.WindowFromPoint(wintypes.POINT(round(point.x()*ratio),round(point.y()*ratio)))
            return user.GetAncestor(hwnd,2)
        from PySide6.QtCore import QPoint
        assert owner(frame.mapToGlobal(frame.content_rect().center()))==int(background.winId()),'Center blocked input'
        assert owner(frame.mapToGlobal(QPoint(40,18)))==int(frame.winId()),'Header cannot be dragged'
        frame.grab().save(str(Path(__file__).with_name('capture-frame.png')))
        print('PASS: Windows frame exclusion; center hit reaches underlying test window; header remains interactive.',flush=True)
    except Exception as exc: error.append(exc)
    finally:
        frame.allow_close=True; frame.close(); background.close(); app.quit()
QTimer.singleShot(350,verify)
app.exec()
if error: raise error[0]
