"""On-demand screen capture worker. No persistent screen/text storage or networking."""
import asyncio
import ctypes
import json
import sys
import time
from core import physical_region
from translate_local import Translator


def emit(data):
    print(json.dumps(data, ensure_ascii=True), flush=True)


def deny_network(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.bind'):
        raise PermissionError('Network is disabled in the translation worker')


async def run(source):
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    import mss
    from PIL import Image
    from ocr_local import LocalOcr
    from text_layout import sentence_units
    from models import translation_ready

    ocr=LocalOcr(source)
    translator=Translator()
    missing_models=[code for code,engine in ocr.engines if not translation_ready(code)]
    with mss.mss() as capture:
        monitor=next((m for m in capture.monitors[1:] if m['left']==0 and m['top']==0),capture.monitors[1])
        emit({'type':'ready','missing':ocr.missing,'missing_models':missing_models})
        previous_signature=None; previous_output=None
        for raw in sys.stdin:
            request=json.loads(raw)
            if request.get('type')!='capture': continue
            translator.configure(request.get('glossary'),request.get('katakana',True))
            revision=request.get('revision',0)
            def frame_emit(data):
                emit(dict(data,revision=revision))
            started=time.monotonic()
            rect=physical_region(monitor,request.get('region'))
            frame=capture.grab(rect)
            image=Image.frombytes('RGB',frame.size,frame.rgb)
            try:
                blocks=await ocr.recognize(image,request.get('direction','auto'))
            finally:
                image.close(); del frame
            def screen_box(box):
                x,y,w,h=box
                return [(rect['left']-monitor['left']+x)/monitor['width'],
                        (rect['top']-monitor['top']+y)/monitor['height'],w/monitor['width'],h/monitor['height']]
            output=[]
            for block in blocks:
                output.append({'text':'번역 중…','original':block['text'],'source':block['source'],
                    'box':screen_box(block['box']),
                    'source_boxes':[screen_box(b) for b in block['source_boxes']],
                    'direction':block['direction'],'readings':block.get('readings',[]),
                    'background':block.get('background',[255,255,255]),
                    'pending':True,'failed':False})
            signature=[[[b['text'],b['box'],b['source'],b['direction']] for b in blocks],
                       translator.glossary,translator.katakana]
            if signature==previous_signature and previous_output and not any(x['failed'] for x in previous_output):
                for current,old in zip(output,previous_output):
                    current.update({key:old[key] for key in ('text','pending','failed','message')})
                frame_emit({'type':'frame','lines':output,'signature':signature,
                    'seconds':round(time.monotonic()-started,1),'failed':0})
                previous_output=output
                continue
            frame_emit({'type':'detected','signature':signature,'lines':output})
            last_progress=0
            for index,block in enumerate(blocks):
                pieces=[]; errors=[]
                if block['source']=='unreadable':
                    pieces=['문자 인식 확인 필요']; errors=['OCR이 읽지 못한 글자입니다. 이미지를 확대해 주세요.']
                else:
                    for sentence in sentence_units(block['text']):
                        try:
                            pieces.append(translator.translate(sentence,block['source']))
                        except Exception as exc:
                            pieces.append('〔번역 확인 필요〕')
                            errors.append(str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__)
                output[index].update(text=' '.join(pieces) or '문자 인식 확인 필요',
                    pending=False,failed=bool(errors),message=' / '.join(dict.fromkeys(errors)))
                if time.monotonic()-last_progress>.2:
                    frame_emit({'type':'partial','lines':output,'signature':signature,
                          'completed':index+1,'total':len(output),'seconds':round(time.monotonic()-started,1)})
                    last_progress=time.monotonic()
            frame_emit({'type':'frame','lines':output,'signature':signature,
                  'seconds':round(time.monotonic()-started,1),'failed':sum(x['failed'] for x in output)})
            previous_signature=signature; previous_output=output


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
