"""Real OCR/model with cropped synthetic input, never the user's screen."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
bootstrap=r'''
import io,json,sys,runpy
from pathlib import Path
from types import SimpleNamespace
stage,release=map(Path,sys.argv[1:3])
sys.path.insert(0,str(stage/'app'))
import models
models.ROOT=release; models.DATA=stage
import mss
from PIL import Image,ImageDraw,ImageFont
image=Image.new('RGB',(1100,400),'white'); draw=ImageDraw.Draw(image)
font=ImageFont.truetype('C:/Windows/Fonts/meiryo.ttc',38)
draw.text((20,20),'カタリナはコーヒーを飲みます。',font=font,fill='black')
draw.text((20,280),'範囲外の秘密は翻訳しません。',font=font,fill='black')
class SyntheticCapture:
    def __enter__(self): self.monitors=[{},dict(left=0,top=0,width=1100,height=400)]; return self
    def __exit__(self,*args): pass
    def grab(self,rect):
        assert rect==dict(left=0,top=0,width=1100,height=120),rect
        crop=image.crop((rect['left'],rect['top'],rect['left']+rect['width'],rect['top']+rect['height']))
        result=SimpleNamespace(size=crop.size,rgb=crop.tobytes()); crop.close(); return result
mss.mss=SyntheticCapture
requests=[dict(type='capture',region=[0,0,1,.3],revision=i,
    glossary={'カタリナ':name},katakana=True) for i,name in [(4,'카타리나'),(5,'카타리나 님'),(6,'카타리나 님')]]
sys.stdin=io.StringIO(''.join(json.dumps(r)+'\n' for r in requests))
sys.argv=[str(stage/'app/worker.py'),'ja']
runpy.run_path(str(stage/'app/worker.py'),run_name='__main__')
'''
result=subprocess.run([sys.executable,'-B','-X','utf8','-c',bootstrap,str(ROOT),str(Path(sys.executable).parent.parent)],
    capture_output=True,text=True,encoding='utf-8',timeout=90)
assert result.returncode==0,result.stdout+result.stderr
events=[json.loads(line) for line in result.stdout.splitlines()]
frames=[event for event in events if event['type']=='frame']
assert [f['revision'] for f in frames]==[4,5,6],events
for frame in frames:
    assert not frame['failed'],frame
    original=' '.join(line['original'] for line in frame['lines'])
    output=' '.join(line['text'] for line in frame['lines'])
    assert 'カタリナ' in original and '範囲外' not in original and '秘密' not in original,original
    assert ('카타리나 님' if frame['revision']>4 else '카타리나') in output,output
    assert '커피' in output and 'ZXQ' not in output,(original,output)
    assert all(line['box'][1]+line['box'][3]<=.3 for line in frame['lines']),frame
    print(frame['revision'],output,flush=True)
print('PASS: crop boundaries, glossary updates, katakana and repeated-frame cache.',flush=True)
