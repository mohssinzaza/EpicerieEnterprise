import tempfile
import unittest
import zipfile
from pathlib import Path
from make_portable import make_portable
from tests.test_v89_portable_integrity import fake_pe

class PortableTests(unittest.TestCase):
    def test_missing_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError, 'Missing'):
                make_portable(d)
    def test_zip_contains_two_exes_and_launcher(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'dist').mkdir()
            for name in ('EpicerieEnterprise.exe','EpicerieRecovery.exe'):
                (root/'dist'/name).write_bytes(fake_pe())
            (root/'WINDOWS_ACCEPTANCE_AR.md').write_bytes(b'x'*2048)
            path=make_portable(root)
            with zipfile.ZipFile(path) as z:
                self.assertIsNone(z.testzip())
                self.assertIn('START_EPICERIE.bat', z.namelist())
                self.assertIn('EpicerieEnterprise.exe', z.namelist())
                self.assertIn('EpicerieRecovery.exe', z.namelist())
                self.assertIn('LOCALAPPDATA', z.read('READ_ME_FIRST.txt').decode())
