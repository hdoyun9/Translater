"""A movable capture border with a real, input-transparent hole in its center."""
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QFontMetrics, QRegion
from PySide6.QtWidgets import QApplication, QWidget


class CaptureFrame(QWidget):
    changed = Signal(object)
    editing = Signal(bool)
    close_requested = Signal()
    BORDER = 7
    HEADER = 34

    def __init__(self, region=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowTitle('ScreenLingo 번역 범위')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setMinimumSize(220,160)
        self.drag = None
        self.allow_close = False
        self.set_region(region or [.45,.18,.45,.64])

    def bounds(self):
        return QApplication.primaryScreen().geometry()

    def content_rect(self):
        return self.rect().adjusted(self.BORDER,self.HEADER,-self.BORDER,-self.BORDER)

    def normalized_region(self):
        area=self.content_rect().translated(self.pos())
        screen=self.bounds()
        return [(area.x()-screen.x())/screen.width(),(area.y()-screen.y())/screen.height(),
                area.width()/screen.width(),area.height()/screen.height()]

    def set_region(self,region):
        screen=self.bounds()
        x,y,w,h=region
        rect=QRect(screen.x()+round(x*screen.width())-self.BORDER,
                   screen.y()+round(y*screen.height())-self.HEADER,
                   round(w*screen.width())+2*self.BORDER,
                   round(h*screen.height())+self.HEADER+self.BORDER)
        self.setGeometry(self.constrain(rect))
        self.update_mask()

    def constrain(self,rect):
        screen=self.bounds()
        rect=QRect(rect)
        rect.setWidth(min(screen.width(),max(self.minimumWidth(),rect.width())))
        rect.setHeight(min(screen.height(),max(self.minimumHeight(),rect.height())))
        rect.moveLeft(max(screen.left(),min(rect.left(),screen.right()-rect.width()+1)))
        rect.moveTop(max(screen.top(),min(rect.top(),screen.bottom()-rect.height()+1)))
        return rect

    def update_mask(self):
        # A transparent painted rectangle alone still intercepts browser clicks.
        self.setMask(QRegion(self.rect()).subtracted(QRegion(self.content_rect())))

    def resizeEvent(self,event):
        self.update_mask()
        self.changed.emit(self.normalized_region())
        super().resizeEvent(event)

    def moveEvent(self,event):
        self.changed.emit(self.normalized_region())
        super().moveEvent(event)

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setClipRegion(self.mask())
        painter.fillRect(self.rect(),QColor('#173c3c'))
        painter.setPen(QPen(QColor('#73e0bd'),2))
        painter.drawRect(self.rect().adjusted(1,1,-2,-2))
        painter.setFont(QFont('Malgun Gothic',10))
        painter.setPen(QColor('#e9fff7'))
        title=QFontMetrics(painter.font()).elidedText('번역 범위 · 상단 이동 / 테두리 크기 조절',Qt.ElideRight,self.width()-26)
        painter.drawText(QRect(13,5,self.width()-26,25),Qt.AlignVCenter,title)
        for dx in (4,8,12):
            painter.drawLine(self.width()-dx-2,self.height()-3,self.width()-3,self.height()-dx-2)

    def edges_at(self,point):
        return (point.x()<self.BORDER,point.y()<self.BORDER,
                point.x()>=self.width()-self.BORDER,point.y()>=self.height()-self.BORDER)

    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton: return
        self.drag=(event.globalPosition().toPoint(),QRect(self.geometry()),self.edges_at(event.position().toPoint()))
        self.editing.emit(True)

    def mouseMoveEvent(self,event):
        if self.drag is None:
            left,top,right,bottom=self.edges_at(event.position().toPoint())
            cursor=(Qt.SizeFDiagCursor if (left and top) or (right and bottom) else
                    Qt.SizeBDiagCursor if (right and top) or (left and bottom) else
                    Qt.SizeHorCursor if left or right else Qt.SizeVerCursor if top or bottom else Qt.SizeAllCursor)
            self.setCursor(cursor)
            return
        anchor,start,edges=self.drag
        delta=event.globalPosition().toPoint()-anchor
        left,top,right,bottom=edges
        rect=QRect(start)
        screen=self.bounds()
        if not any(edges): rect.translate(delta)
        else:
            if left: rect.setLeft(max(screen.left(),min(start.left()+delta.x(),start.right()-self.minimumWidth()+1)))
            if top: rect.setTop(max(screen.top(),min(start.top()+delta.y(),start.bottom()-self.minimumHeight()+1)))
            if right: rect.setRight(min(screen.right(),max(start.right()+delta.x(),start.left()+self.minimumWidth()-1)))
            if bottom: rect.setBottom(min(screen.bottom(),max(start.bottom()+delta.y(),start.top()+self.minimumHeight()-1)))
        self.setGeometry(self.constrain(rect))

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton and self.drag is not None:
            self.drag=None
            self.editing.emit(False)

    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape and self.drag:
            self.setGeometry(self.drag[1]); self.drag=None; self.editing.emit(False)

    def closeEvent(self,event):
        if self.allow_close: event.accept()
        else: event.ignore(); self.close_requested.emit()
