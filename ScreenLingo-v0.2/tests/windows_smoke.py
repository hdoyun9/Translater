"""Real Windows OCR + translation with an in-memory synthetic capture.

Usage: runtime\python.exe -B tests\windows_smoke.py RELEASE_ROOT [APP_DIR]
The capture source is replaced so this test never reads the user's screen.
No downloads, screenshots, or recognized text are saved to disk.
"""
import json
from pathlib import Path
import subprocess
import sys


def main():
    root=Path(sys.argv[1]).resolve()
    app=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else root/'app'
    bootstrap=r'''
import io, runpy, sys
from pathlib import Path
from types import SimpleNamespace
root, app = map(Path, sys.argv[1:3])
sys.path.insert(0,str(app))
import models
models.ROOT=root
import mss
from PIL import Image, ImageDraw, ImageFont
class SyntheticCapture:
    def __enter__(self):
        self.monitors=[{},dict(left=0,top=0,width=800,height=140)]
        return self
    def __exit__(self,*args): pass
    def grab(self,rect):
        image=Image.new('RGB',(800,140),'white')
        ImageDraw.Draw(image).text((20,40),'Hello. Welcome to the game.',
            font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',32),fill='black')
        return SimpleNamespace(size=image.size,rgb=image.tobytes())
mss.mss=SyntheticCapture
sys.stdin=io.StringIO('{"type":"capture"}\n'*3)
sys.argv=[str(app/'worker.py'),'en']
runpy.run_path(str(app/'worker.py'),run_name='__main__')
'''
    result=subprocess.run([str(root/'runtime'/'python.exe'),'-B','-X','utf8','-X','faulthandler',
        '-c',bootstrap,str(root),str(app)],capture_output=True,text=True,
        encoding='utf-8',timeout=60)
    events=[json.loads(line) for line in result.stdout.splitlines()]
    print('Exit:',result.returncode)
    print('Events:',[event['type'] for event in events])
    errors=[event for event in events if event['type']=='error']
    if errors:
        print(json.dumps(errors,ensure_ascii=True))
    frames=[event for event in events if event['type']=='frame']
    if result.returncode or len(frames)!=3 or any(not frame['lines'] for frame in frames):
        print(result.stderr)
        return 1
    translated=' '.join(line['text'] for line in frames[-1]['lines'])
    print('Synthetic translation:',ascii(translated))
    assert any('\uac00'<=char<='\ud7a3' for char in translated),translated
    print('PASS: real Windows OCR and Korean translation under the supplied path.')
    return 0


if __name__=='__main__': sys.exit(main())
