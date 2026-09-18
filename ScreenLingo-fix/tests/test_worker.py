import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import worker


class WorkerStartupTests(unittest.TestCase):
    def test_event_loop_failure_is_reported_to_ui(self):
        output=io.StringIO()
        with patch.object(worker.asyncio,'new_event_loop',side_effect=OSError('private detail')):
            with contextlib.redirect_stdout(output):
                code=worker.main()
        event=json.loads(output.getvalue())
        self.assertEqual(code,1)
        self.assertEqual(event['type'],'error')
        self.assertIn('OSError',event['message'])
        self.assertNotIn('private detail',event['message'])

    @unittest.skipUnless(sys.platform=='win32','Windows DLL loader')
    def test_runtime_load_failure_is_reported_to_ui(self):
        output=io.StringIO()
        with patch.object(worker.ctypes,'WinDLL',side_effect=OSError('missing runtime')):
            with contextlib.redirect_stdout(output):
                code=worker.main()
        event=json.loads(output.getvalue())
        self.assertEqual(code,1)
        self.assertEqual(event['type'],'error')
        self.assertIn('Visual C++ x64',event['message'])


if __name__=='__main__': unittest.main()
