import json,os
from pathlib import Path
import sys
os.environ['QT_QPA_PLATFORM']='offscreen'
stage=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(stage/'app'))
sys.argv.append('--preview')
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from main import Panel,Overlay
from glossary_ui import GlossaryDialog
app=QApplication([])
panel=Panel()
app.processEvents()
panel.grab().save(str(stage/'qa'/'panel.png'))
panel.capture_frame.grab().save(str(stage/'qa'/'capture-frame.png'))
dialog=GlossaryDialog({'カタリナ':'카타리나','東京':'도쿄'},panel)
dialog.show(); app.processEvents()
dialog.grab().save(str(stage/'qa'/'glossary.png')); dialog.close()
for mode,orientation in [('ja_horizontal','horizontal'),('ja_vertical','vertical')]:
    frame=json.loads((stage/'qa'/(mode+'-results.json')).read_text(encoding='utf-8'))
    overlay=Overlay(); overlay.resize(820,660); overlay.lines=frame['lines']; overlay.update()
    app.processEvents()
    image=QImage(str(stage/'qa'/('japanese-'+orientation+'.png')))
    painter=QPainter(image); painter.drawImage(0,0,overlay.grab().toImage()); painter.end()
    image.save(str(stage/'qa'/(mode+'-overlay.png')))
    overlay.close()
panel.close()
print('Rendered panel and Japanese overlays.')
