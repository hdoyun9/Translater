import asyncio
import ctypes
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')
stage=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(stage/'app'))
import models
models.ROOT=Path(sys.executable).parent.parent
models.DATA=stage
runtime=ctypes.WinDLL('msvcp140.dll',winmode=0x800)
from translate_local import Translator
translator=Translator()
for text in ['こんにちは。今日はいい天気ですね。','この扉を開けて、鍵を探してください。','明日の朝、駅で待っています。']:
    print('SOURCE',text,flush=True)
    print('EN',translator._pair(text,'ja_en'),flush=True)
    print('KO',translator.translate(text,'ja'),flush=True)

from winrt.runtime import init_apartment, ApartmentType
init_apartment(ApartmentType.MULTI_THREADED)
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import SoftwareBitmap,BitmapPixelFormat,BitmapAlphaMode
from winrt.windows.storage.streams import DataWriter
from PIL import Image,ImageDraw,ImageFont
font=ImageFont.truetype('C:/Windows/Fonts/meiryo.ttc',32)
engine=OcrEngine.try_create_from_language(Language('ja-JP'))

async def probe():
    for orientation in ['horizontal','vertical']:
        image=Image.new('RGB',(820,660),'white')
        draw=ImageDraw.Draw(image)
        phrases=['この扉を開けて、','鍵を探してください。']
        if orientation=='horizontal':
            for i,text in enumerate(phrases): draw.text((30,40+i*55),text,font=font,fill='black')
        else:
            for i,text in enumerate(phrases):
                for j,char in enumerate(text): draw.text((700-i*64,25+j*45),char,font=font,fill='black')
        image.save(stage/'qa'/f'japanese-{orientation}.png')
        writer=DataWriter(); writer.write_bytes(image.convert('RGBA').tobytes('raw','BGRA'))
        bitmap=SoftwareBitmap.create_copy_with_alpha_from_buffer(writer.detach_buffer(),BitmapPixelFormat.BGRA8,*image.size,BitmapAlphaMode.IGNORE)
        writer.close()
        result=await engine.recognize_async(bitmap)
        print('OCR',orientation,result.text,flush=True)
        for line in result.lines:
            print('LINE',line.text,[(w.text,(w.bounding_rect.x,w.bounding_rect.y,w.bounding_rect.width,w.bounding_rect.height)) for w in line.words],flush=True)
        bitmap.close()
asyncio.run(probe())
