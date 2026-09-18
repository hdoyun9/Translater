"""Windows OCR at readable resolution, preserving geometry and reading order."""
from text_layout import make_line, assemble_blocks, tile_boxes


class LocalOcr:
    def __init__(self,source):
        from winrt.runtime import init_apartment, ApartmentType
        init_apartment(ApartmentType.MULTI_THREADED)
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.globalization import Language
        self.engine_type=OcrEngine
        self.engines=[]; self.missing=[]
        available=list(OcrEngine.available_recognizer_languages)
        for code,tag in [('en','en-US'),('ja','ja-JP'),('zh','zh-Hans')]:
            if source not in ('auto',code): continue
            language=next((l for l in available if l.language_tag.lower().startswith(code)),None)
            engine=OcrEngine.try_create_from_language(language or Language(tag))
            if engine: self.engines.append((code,engine))
            else: self.missing.append(code)
        if not self.engines:
            raise RuntimeError('선택한 원문 언어의 Windows OCR 기능이 없습니다. Windows 언어 옵션에서 설치해 주세요.')

    async def recognize(self,image,direction='auto'):
        from PIL import Image
        from winrt.windows.graphics.imaging import SoftwareBitmap,BitmapPixelFormat,BitmapAlphaMode
        from winrt.windows.storage.streams import DataWriter
        limit=min(1800,self.engine_type.max_image_dimension//2)
        lines=[]
        for left,top,right,bottom in tile_boxes(*image.size,limit):
            # A single scale can omit an entire vertical column. Reconcile both
            # native resolution and an enlarged pass instead of trusting one.
            for scale in (1,2):
                tile=image.crop((left,top,right,bottom))
                if scale!=1:
                    resized=tile.resize((tile.width*scale,tile.height*scale),Image.Resampling.LANCZOS)
                    tile.close(); tile=resized
                writer=DataWriter()
                writer.write_bytes(tile.convert('RGBA').tobytes('raw','BGRA'))
                bitmap=SoftwareBitmap.create_copy_with_alpha_from_buffer(writer.detach_buffer(),
                    BitmapPixelFormat.BGRA8,tile.width,tile.height,BitmapAlphaMode.IGNORE)
                writer.close()
                try:
                    for code,engine in self.engines:
                        result=await engine.recognize_async(bitmap)
                        for line in result.lines:
                            words=[]
                            for word in line.words:
                                box=word.bounding_rect
                                words.append({'text':word.text,'box':[left+box.x/scale,top+box.y/scale,
                                    box.width/scale,box.height/scale]})
                            if words:
                                lines.append(make_line(words,code,direction))
                finally:
                    bitmap.close(); tile.close()
        blocks=assemble_blocks(lines)
        for block in blocks:
            x,y,w,h=block['box']
            samples=[]
            for dx,dy in [(0,0),(.5,0),(1,0),(0,1),(.5,1),(1,1)]:
                px=max(0,min(image.width-1,int(x+w*dx)))
                py=max(0,min(image.height-1,int(y+h*dy)))
                samples.append(image.getpixel((px,py)))
            from statistics import median
            block['background']=[int(median(p[c] for p in samples)) for c in range(3)]
        return blocks
