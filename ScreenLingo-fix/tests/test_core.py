import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from core import source_for, normalize, deduplicate, intersection_over_union, MemoryCache, physical_region
from models import required, safe_extract


class CoreTests(unittest.TestCase):
    def test_sources(self):
        self.assertEqual(source_for('Open the door'), 'en')
        self.assertEqual(source_for('こんにちは'), 'ja')
        self.assertEqual(source_for('明日', 'ja'), 'ja')
        self.assertEqual(source_for('你好'), 'zh')
        self.assertIsNone(source_for('한국어입니다'))
        self.assertIsNone(source_for('1234 !?'))

    def test_normalize(self):
        self.assertEqual(normalize(' hi\n   there '), 'hi there')
        self.assertEqual(len(normalize('a'*2000)),1200)

    def test_iou(self):
        self.assertEqual(intersection_over_union([0,0,1,1],[0,0,1,1]),1)
        self.assertEqual(intersection_over_union([0,0,1,1],[2,2,1,1]),0)

    def test_dedupe(self):
        lines=[{'text':'xx','source':'en','box':[0,0,.3,.1]},
               {'text':'こんにちは','source':'ja','box':[0,0,.3,.1]}]
        self.assertEqual(deduplicate(lines)[0]['source'],'ja')
        self.assertEqual(len(deduplicate(lines)),1)

    def test_cache_lru(self):
        c=MemoryCache(2); c.put('a',1); c.put('b',2)
        self.assertEqual(c.get('a'),1)
        c.put('c',3); self.assertIsNone(c.get('b'))
        c.clear(); self.assertIsNone(c.get('a'))

    def test_region(self):
        monitor=dict(left=0,top=0,width=3840,height=2160)
        self.assertEqual(physical_region(monitor,None), monitor)
        self.assertEqual(physical_region(monitor,[.5,.5,.5,.5]),dict(left=1920,top=1080,width=1920,height=1080))
        self.assertGreater(physical_region(monitor,[2,2,-1,-1])['width'],0)

    def test_pairs(self):
        self.assertEqual(required('en'),['en_ko'])
        self.assertEqual(required('ja'),['en_ko','ja_en'])
        self.assertEqual(required('auto'),['en_ko','ja_en','zh_en'])

    def test_zip_traversal(self):
        for bad in ['../escape','/tmp/escape','C:\\escape','..\\escape']:
            archive=io.BytesIO()
            with zipfile.ZipFile(archive,'w') as z: z.writestr(bad,'oops')
            archive.seek(0)
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError): safe_extract(archive,folder)

    def test_valid_zip(self):
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w') as z: z.writestr('nested/file','ok')
        archive.seek(0)
        with tempfile.TemporaryDirectory() as folder:
            safe_extract(archive,folder)
            self.assertEqual((Path(folder)/'nested/file').read_text(),'ok')

    def test_worker_has_no_network(self):
        from worker import deny_network
        for event in ('socket.connect','socket.sendto','socket.getaddrinfo','socket.bind'):
            with self.assertRaises(PermissionError): deny_network(event,())
        deny_network('open',())


if __name__=='__main__': unittest.main()
