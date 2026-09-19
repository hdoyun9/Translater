"""Real-model regression for the omitted places and reversed negation."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]


class DirectTranslationTests(unittest.TestCase):
    @unittest.skipUnless((ROOT/'models/m2m100/model/model.bin').is_file(),'Direct model not bundled')
    def test_names_loanwords_and_dictionary_reconfiguration(self):
        script=r'''
import ctypes,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'app'))
runtime=ctypes.WinDLL('msvcp140.dll',winmode=0x800)
from translate_local import Translator
t=Translator()
outputs=[t.translate('カタリナはオルステッドを探しています。','ja'),
         t.translate('カタリナはコーヒーを飲みます。','ja')]
t.configure({'レイラ':'레일라','クラウド':'클라우드','ミッドガル':'미드가르'})
sentence='レイラはクラウドと一緒にミッドガルへ行きます。'
outputs.append(t.translate(sentence,'ja'))
t.configure({'レイラ':'레이나','クラウド':'클라우드','ミッドガル':'미드가르'})
outputs.append(t.translate(sentence,'ja'))
print(json.dumps(outputs,ensure_ascii=True))
'''
        result=subprocess.run([sys.executable,'-B','-X','utf8','-c',script,str(ROOT)],capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        outputs=json.loads(result.stdout)
        self.assertIn('카타리나',outputs[0]); self.assertIn('오르스테드',outputs[0])
        self.assertIn('커피',outputs[1])
        for expected in ('레일라','클라우드','미드가르'): self.assertIn(expected,outputs[2])
        self.assertIn('레이나',outputs[3]); self.assertNotIn('레일라',outputs[3])
        for output in outputs: self.assertNotIn('ZXQ',output)

    @unittest.skipUnless((ROOT/'models/m2m100/model/model.bin').is_file(),'Direct model not bundled')
    def test_meaning_and_language_survive_direct_translation(self):
        script=r'''
import ctypes,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'app'))
runtime=ctypes.WinDLL('msvcp140.dll',winmode=0x800)
from translate_local import Translator
t=Translator()
assert t.direct
cases=[('ja','明日の朝、駅で待っています。'),('ja','彼女は昨日、学校に行きませんでした。'),
       ('en','Please do not open the door until I return.'),('zh','请打开这扇门，然后找到钥匙。')]
print(json.dumps([t.translate(text,source) for source,text in cases],ensure_ascii=True))
'''
        result=subprocess.run([sys.executable,'-B','-X','utf8','-c',script,str(ROOT)],capture_output=True,text=True,encoding='utf-8',timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        outputs=json.loads(result.stdout)
        self.assertIn('내일',outputs[0]); self.assertIn('역',outputs[0])
        self.assertIn('않',outputs[1]); self.assertIn('어제',outputs[1])
        self.assertIn('열지',outputs[2]); self.assertIn('마',outputs[2])
        self.assertIn('열쇠',outputs[3])
        for output in outputs:
            self.assertNotIn('⁇',output)
            self.assertNotIn('???',output)


if __name__=='__main__': unittest.main()
