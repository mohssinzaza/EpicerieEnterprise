import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from make_portable import make_portable
from portable_acceptance import test_portable_archive
from test_v89_portable_integrity import fake_pe

class RecoveryAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'dist').mkdir()
        for name in ('EpicerieEnterprise.exe', 'EpicerieRecovery.exe'):
            (self.root / 'dist' / name).write_bytes(fake_pe())
        (self.root / 'WINDOWS_ACCEPTANCE_AR.md').write_text('Checklist')
        self.archive = make_portable(self.root)

    def test_both_executables_are_tested(self):
        called = []
        def runner(args, **kwargs):
            called.append(Path(args[0]).name)
            Path(args[2]).write_text('PASS: smoke', encoding='utf-8')
            return Mock(returncode=0)
        self.assertTrue(test_portable_archive(self.archive, runner=runner))
        self.assertEqual(called, ['EpicerieEnterprise.exe', 'EpicerieRecovery.exe'])

    def test_recovery_failure_rejects_package(self):
        def runner(args, **kwargs):
            Path(args[2]).write_text('PASS: smoke', encoding='utf-8')
            return Mock(returncode=0 if Path(args[0]).name == 'EpicerieEnterprise.exe' else 1)
        with self.assertRaisesRegex(RuntimeError, 'recovery executable self-test failed'):
            test_portable_archive(self.archive, runner=runner)

    def test_recovery_bad_marker_rejects_package(self):
        def runner(args, **kwargs):
            Path(args[2]).write_text('PASS: smoke' if Path(args[0]).name == 'EpicerieEnterprise.exe' else 'FAIL: recovery', encoding='utf-8')
            return Mock(returncode=0)
        with self.assertRaisesRegex(RuntimeError, 'recovery executable did not pass'):
            test_portable_archive(self.archive, runner=runner)
