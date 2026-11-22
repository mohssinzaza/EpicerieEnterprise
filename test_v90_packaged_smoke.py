import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from runtime_selftest import run_self_test

class PackagedSmokeTests(unittest.TestCase):
    def test_success_marker(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'result.txt'
            with patch('release_check.smoke') as smoke:
                self.assertEqual(run_self_test(path),0)
                smoke.assert_called_once()
            self.assertTrue(path.read_text().startswith('PASS:'))
    def test_failure_marker(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'result.txt'
            with patch('release_check.smoke',side_effect=RuntimeError('broken')):
                self.assertEqual(run_self_test(path),1)
            self.assertIn('FAIL:',path.read_text())
    def test_windows_build_runs_packaged_exe(self):
        root=Path(__file__).resolve().parents[1]
        for fn in ('BUILD_ON_WINDOWS.bat','BUILD_PORTABLE_ONLY_WINDOWS.bat'):
            text=(root/fn).read_text()
            self.assertIn('EpicerieEnterprise.exe" --self-test',text)
            self.assertIn('findstr /b /c:"PASS:"',text)
    def test_gui_starts_after_selftest_guard(self):
        text=(Path(__file__).resolve().parents[1]/'app.py').read_text()
        self.assertLess(text.index("'--self-test'"),text.index('root=tk.Tk()'))
