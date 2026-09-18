"""Startup errors are shown visibly; no diagnostic log files are written."""
import ctypes
import sys

if __name__ == '__main__':
    try:
        if sys.platform == 'win32':
            if sys.getwindowsversion().build < 19041:
                raise RuntimeError('Windows 10 2004 이상 또는 Windows 11이 필요합니다.')
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        from main import main
        sys.exit(main())
    except Exception as exc:
        if sys.platform == 'win32':
            ctypes.windll.user32.MessageBoxW(None,
                '앱을 시작하지 못했습니다. 화면 인식은 시작되지 않았습니다.\n\n'
                + type(exc).__name__ + ': ' + str(exc)[:700]
                + '\n\nZIP을 모두 압축 해제했는지 확인하고 README.html을 참고해 주세요.',
                'ScreenLingo 시작 오류', 0x10)
        else:
            raise
        sys.exit(1)
