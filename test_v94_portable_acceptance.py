import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from make_portable import make_portable
from portable_acceptance import test_portable_archive
from test_v89_portable_integrity import fake_pe

class PortableAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'dist').mkdir()
        for name in ('EpicerieEnterprise.exe', 'EpicerieRecovery.exe'):
            (self.root / 'dist' / name).write_bytes(fake_pe())
        (self.root / 'WINDOWS_ACCEPTANCE_AR.md').write_text('Checklist')
        self.archive = make_portable(self.root)

    def test_extracted_archive_runs_self_test(self):
        def runner(args, **kwargs):
            self.assertTrue(Path(args[0]).is_file())
            self.assertEqual(args[1], '--self-test')
            Path(args[2]).write_text('PASS: accepted', encoding='utf-8')
            return Mock(returncode=0)
        self.assertTrue(test_portable_archive(self.archive, runner=runner))

    def test_missing_result_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            test_portable_archive(self.archive, runner=lambda *a, **k: Mock(returncode=0))

    def test_failure_result_is_rejected(self):
        def runner(args, **kwargs):
            Path(args[2]).write_text('FAIL: issue', encoding='utf-8')
            return Mock(returncode=0)
        with self.assertRaisesRegex(RuntimeError, 'did not pass'):
            test_portable_archive(self.archive, runner=runner)

    def test_both_build_scripts_run_portable_acceptance(self):
        project = Path(__file__).resolve().parents[1]
        for name in ('BUILD_ON_WINDOWS.bat', 'BUILD_PORTABLE_ONLY_WINDOWS.bat'):
            self.assertIn('python portable_acceptance.py', (project/name).read_text())
