"""On-demand screen capture worker. No persistent screen/text storage or networking."""
import asyncio
import ctypes
import json
import sys
import time
from core import source_for, normalize, deduplicate, physical_region
from translate_local import Translator


def emit(data):
    print(json.dumps(data, ensure_ascii=True), flush=True)


def deny_network(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.bind'):
        raise PermissionError('Network is disabled in the translation worker')


async def run(source):
    # DPI context set before the first capture object is created.
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    import mss
    from winrt.runtime import init_apartment, ApartmentType
    init_apartment(ApartmentType.MULTI_THREADED)
    from PIL import Image
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat, BitmapAlphaMode
    from winrt.windows.storage.streams import DataWriter

    tags = [('en','en-US'), ('ja','ja-JP'), ('zh','zh-Hans')]
    engines = []
    missing = []
    available = list(OcrEngine.available_recognizer_languages)
    for code, tag in tags:
        if source not in ('auto', code):
            continue
        language = next((lang for lang in available if lang.language_tag.lower().startswith(code)), Language(tag))
        engine = OcrEngine.try_create_from_language(language)
        if engine:
            engines.append((code, engine))
        else:
            missing.append(code)
    if not engines:
        raise RuntimeError('Windows OCR 언어가 없습니다. Windows 설정 > 시간 및 언어 > 언어 및 지역에서 원문 언어의 OCR 기능을 설치해 주세요.')
    translator = Translator()
    with mss.mss() as capture:
        monitor = next((m for m in capture.monitors[1:] if m['left'] == 0 and m['top'] == 0), capture.monitors[1])
        emit({'type':'ready', 'missing':missing})
        for raw in sys.stdin:
            request = json.loads(raw)
            if request.get('type') != 'capture':
                continue
            started = time.monotonic()
            rect = physical_region(monitor, request.get('region'))
            frame = capture.grab(rect)
            image = Image.frombytes('RGB', frame.size, frame.rgb)
            max_dim = min(OcrEngine.max_image_dimension, 2800)
            ratio = min(1.0, max_dim / max(image.size))
            if ratio < 1:
                image = image.resize((max(1,int(image.width*ratio)), max(1,int(image.height*ratio))))
            writer = DataWriter()
            writer.write_bytes(image.convert('RGBA').tobytes('raw', 'BGRA'))
            bitmap = SoftwareBitmap.create_copy_with_alpha_from_buffer(writer.detach_buffer(),
                BitmapPixelFormat.BGRA8, image.width, image.height, BitmapAlphaMode.IGNORE)
            writer.close()
            lines = []
            try:
                for code, engine in engines:
                    result = await engine.recognize_async(bitmap)
                    for line in result.lines:
                        text = normalize(line.text)
                        lang = source_for(text, code)
                        if not lang or (source != 'auto' and lang not in (source, 'en')):
                            continue
                        words = [w.bounding_rect for w in line.words]
                        if not words:
                            continue
                        x, y = min(w.x for w in words), min(w.y for w in words)
                        r, b = max(w.x+w.width for w in words), max(w.y+w.height for w in words)
                        # Unit coordinates on the full primary monitor survive mixed DPI scaling.
                        box = [(rect['left']-monitor['left']+x/ratio)/monitor['width'],
                               (rect['top']-monitor['top']+y/ratio)/monitor['height'],
                               (r-x)/ratio/monitor['width'], (b-y)/ratio/monitor['height']]
                        lines.append({'text':text, 'source':lang, 'box':box})
            finally:
                bitmap.close()
                del image, frame
            lines = deduplicate(lines)[:60]
            # Clear stale overlays as soon as new OCR is available, before translation work.
            signature = [[x['text'], x['box']] for x in lines]
            emit({'type':'detected', 'signature':signature})
            output = []
            for line in lines:
                translated = translator.translate(line['text'], line['source'])
                if translated:
                    output.append({'text':translated, 'box':line['box']})
            emit({'type':'frame', 'lines':output, 'signature':signature,
                  'seconds':round(time.monotonic()-started, 1), 'limited':len(lines)>=60})


def main():
    # Windows' Proactor loop creates a local socketpair for wakeups. Create that
    # infrastructure before blocking future network operations, and before OCR.
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        if sys.platform == 'win32':
            # PyWinRT bundles MSVCP140 14.29, which shadows the installed runtime
            # and crashes SentencePiece 0.2.1. Load the system copy first and
            # keep its handle alive for the entire worker lifetime.
            try:
                cpp_runtime = ctypes.WinDLL('msvcp140.dll', winmode=0x00000800)
            except OSError as exc:
                raise RuntimeError(
                    'Windows의 Visual C++ x64 런타임을 불러오지 못했습니다. '
                    'Microsoft 공식 최신 x64 재배포 패키지를 설치하거나 복구해 주세요. '
                    f'(WinError {getattr(exc, "winerror", None)})') from exc
        sys.addaudithook(deny_network)
        loop.run_until_complete(run(sys.argv[1]))
    except Exception as exc:
        # Never persist a traceback or OCR text. Error messages here are in-memory only.
        message = str(exc) if isinstance(exc, RuntimeError) else ('화면 인식·번역 작업 실패: ' + type(exc).__name__)
        emit({'type':'error', 'message':message})
        return 1
    finally:
        if loop is not None:
            loop.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
