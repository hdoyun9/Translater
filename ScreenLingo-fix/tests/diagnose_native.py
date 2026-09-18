"""Temporary synthetic-only isolation probe for the Windows native crash."""
import subprocess
import sys
from pathlib import Path

app=Path(__file__).resolve().parents[1]/'app'
probe=r'''
import sys, asyncio
from pathlib import Path
mode, app=sys.argv[1:3]
sys.path.insert(0,app)
import models
models.ROOT=Path(sys.executable).parent.parent
if mode=='system':
    import ctypes
    runtime=ctypes.WinDLL('msvcp140.dll',winmode=0x00000800)
from translate_local import Translator
from worker import deny_network
loop=asyncio.new_event_loop()
asyncio.set_event_loop(loop)
if mode=='audit': sys.addaudithook(deny_network)
if mode in ('engine','ocr','preload','system'):
    from winrt.runtime import init_apartment, ApartmentType
    init_apartment(ApartmentType.MULTI_THREADED)
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.globalization import Language
    engine=OcrEngine.try_create_from_language(Language('en-US'))
translator=Translator()
if mode=='preload': print(ascii(translator.translate('Hello.', 'en')),flush=True)
if mode in ('ocr','preload','system'):
    from PIL import Image, ImageDraw, ImageFont
    from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat, BitmapAlphaMode
    from winrt.windows.storage.streams import DataWriter
    image=Image.new('RGB',(800,140),'white')
    ImageDraw.Draw(image).text((20,40),'Hello. Welcome to the game.',font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',32),fill='black')
    writer=DataWriter()
    writer.write_bytes(image.convert('RGBA').tobytes('raw','BGRA'))
    bitmap=SoftwareBitmap.create_copy_with_alpha_from_buffer(writer.detach_buffer(),BitmapPixelFormat.BGRA8,800,140,BitmapAlphaMode.IGNORE)
    writer.close()
    async def recognize(): return await engine.recognize_async(bitmap)
    result=loop.run_until_complete(recognize())
    print('OCR:',result.text,flush=True)
    bitmap.close()
print('TRANSLATE',flush=True)
print(ascii(translator.translate('Hello. Welcome to the game.', 'en')),flush=True)
loop.close()
'''
for mode in sys.argv[1:] or ['audit','engine','ocr','preload']:
    result=subprocess.run([sys.executable,'-B','-X','utf8','-X','faulthandler','-c',probe,mode,str(app)],capture_output=True,text=True,encoding='utf-8',timeout=25)
    print(mode,hex(result.returncode & 0xffffffff),result.stdout,flush=True)
    if result.returncode: print(result.stderr[-4000:],flush=True)
