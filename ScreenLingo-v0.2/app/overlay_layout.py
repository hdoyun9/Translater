"""Fit text over its source; never discard an item to resolve a collision."""
from PySide6.QtCore import Qt,QRectF,QRect
from PySide6.QtGui import QFont,QFontMetrics

TEXT_FLAGS=Qt.TextWordWrap


def pixel_box(box,width,height,padding=3):
    x,y,w,h=box
    return QRectF(x*width-padding,y*height-padding,w*width+padding*2,h*height+padding*2)


def layout_items(lines,width,height,font_size):
    items=[]
    screen=QRectF(0,0,width,height)
    for index,line in enumerate(lines):
        source=pixel_box(line['box'],width,height)
        rect=source.intersected(screen)
        # Tiny OCR labels need a little room for a Korean word.
        rect.setWidth(min(max(rect.width(),48),width))
        rect.setHeight(min(max(rect.height(),24),height))
        if rect.right()>width: rect.moveRight(width)
        if rect.bottom()>height: rect.moveBottom(height)
        text=line['text']; font=QFont('Malgun Gothic')
        needed=None
        for size in range(max(9,int(font_size*1.25)),8,-1):
            font.setPixelSize(size)
            needed=QFontMetrics(font).boundingRect(QRect(0,0,max(1,int(rect.width()-6)),100000),TEXT_FLAGS,text)
            if needed.height()<=rect.height()-6 and needed.width()<=rect.width()-6: break
        overflow=needed.height()>rect.height()-6 or needed.width()>rect.width()-6
        if overflow:
            # Grow in place before using the complete, scrollable text view.
            rect.setWidth(min(width,max(rect.width(),160)))
            if rect.right()>width: rect.moveRight(width)
            needed=QFontMetrics(font).boundingRect(QRect(0,0,max(1,int(rect.width()-6)),100000),TEXT_FLAGS,text)
            rect.setHeight(min(height,max(rect.height(),needed.height()+6)))
            if rect.bottom()>height: rect.moveBottom(height)
            overflow=needed.height()>rect.height()-6 or needed.width()>rect.width()-6
        items.append(dict(index=index,rect=rect,font=font,text=text,overflow=overflow,
            masks=[pixel_box(b,width,height,2) for b in line.get('source_boxes',[line['box']])],
            background=line.get('background',[255,255,255])))
    return items
