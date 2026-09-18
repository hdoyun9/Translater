"""Synthetic manga/page fixtures; no capture or storage of user content."""
import json
from pathlib import Path
import subprocess
import sys
stage=Path(__file__).resolve().parents[1]
release=Path(sys.executable).parent.parent
bootstrap=r'''
import io,sys,runpy
from pathlib import Path
from types import SimpleNamespace
stage,release=map(Path,sys.argv[1:3]); mode=sys.argv[3]
sys.path.insert(0,str(stage/'app'))
import models
models.ROOT=release; models.DATA=stage
import mss
from PIL import Image,ImageDraw,ImageFont
font=ImageFont.truetype('C:/Windows/Fonts/meiryo.ttc',32)
source='ja'
if mode=='en_many':
    image=Image.new('RGB',(800,2500),'white'); draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20)
    for row in range(95): draw.text((20,10+row*25),'Open the door and find the key.',font=font,fill='black')
    draw.text((20,10+95*25),'Final sentence: welcome to the game.',font=font,fill='black')
    source='en'
else:
    image=Image.new('RGB',(820,660),'white'); draw=ImageDraw.Draw(image)
    if mode in ('ja_vertical','ja_ruby'):
        for column,text in enumerate(['この扉を開けて、','鍵を探してください。']):
            for row,char in enumerate(text): draw.text((700-column*64,25+row*45),char,font=font,fill='black')
        if mode=='ja_ruby':
            ruby_font=ImageFont.truetype('C:/Windows/Fonts/meiryo.ttc',14)
            for i,c in enumerate('とびら'): draw.text((738,123+i*14),c,font=ruby_font,fill='black')
    elif mode in ('zh_horizontal','auto_zh'):
        font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',32)
        draw.text((30,40),'请打开这扇门，',font=font,fill='black')
        draw.text((30,95),'然后找到钥匙。',font=font,fill='black'); source='auto' if mode=='auto_zh' else 'zh'
    elif mode in ('en_wrapped','auto_en'):
        draw.text((30,40),'Open this door and',font=font,fill='black')
        draw.text((30,95),'look for the key.',font=font,fill='black'); source='auto' if mode=='auto_en' else 'en'
    else:
        draw.text((30,40),'この扉を開けて、',font=font,fill='black')
        draw.text((30,95),'鍵を探してください。',font=font,fill='black')
        if mode=='auto': source='auto'
class SyntheticCapture:
    def __enter__(self): self.monitors=[{},dict(left=0,top=0,width=image.width,height=image.height)]; return self
    def __exit__(self,*args): pass
    def grab(self,rect): return SimpleNamespace(size=image.size,rgb=image.tobytes())
mss.mss=SyntheticCapture
sys.stdin=io.StringIO('{"type":"capture","direction":"auto"}\n')
sys.argv=[str(stage/'app'/'worker.py'),source]
runpy.run_path(str(stage/'app'/'worker.py'),run_name='__main__')
'''
for mode in sys.argv[1:] or ['en_wrapped','ja_horizontal','ja_vertical','auto','en_many']:
    result=subprocess.run([sys.executable,'-B','-X','utf8','-X','faulthandler','-c',bootstrap,str(stage),str(release),mode],
        capture_output=True,text=True,encoding='utf-8',timeout=180)
    events=[json.loads(line) for line in result.stdout.splitlines()]
    frames=[e for e in events if e['type']=='frame']
    print(mode,'exit=',result.returncode,flush=True)
    if not frames:
        print(result.stdout[-1000:],result.stderr[-3000:]); raise SystemExit(1)
    frame=frames[-1]
    print('blocks=',len(frame['lines']),'failed=',frame['failed'],'seconds=',frame['seconds'],flush=True)
    for line in frame['lines'][:5]: print(json.dumps({k:(v[:160] if isinstance(v,str) else v) for k,v in line.items() if k in ('text','original','source','direction','message')},ensure_ascii=True),flush=True)
    (stage/'qa'/(mode+'-results.json')).write_text(json.dumps(frame,ensure_ascii=False,indent=2),encoding='utf-8')
    assert result.returncode==0 and frame['lines'],mode
    assert not frame['failed'],mode
    if mode=='en_many':
        original=' '.join(l['original'] for l in frame['lines'])
        assert 'Final sentence' in original,original[-300:]
        assert len(original)>1200,len(original)
    else:
        if mode in ('ja_horizontal','ja_vertical','auto'):
            original=' '.join(l['original'] for l in frame['lines'])
            assert '扉' in original and '鍵' in original,original
        assert any('\uac00'<=c<='\ud7a3' for l in frame['lines'] for c in l['text']),frame
print('PASS',flush=True)
