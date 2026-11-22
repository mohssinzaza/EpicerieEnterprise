import subprocess
import tempfile
import unittest
from pathlib import Path
from make_portable import make_portable
from portable_acceptance import test_portable_archive
from test_v89_portable_integrity import fake_pe

class PortableFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / 'dist').mkdir()
        for name in ('EpicerieEnterprise.exe', 'EpicerieRecovery.exe'):
            (root / 'dist' / name).write_bytes(fake_pe())
        (root / 'WINDOWS_ACCEPTANCE_AR.md').write_text('check')
        self.archive = make_portable(root)

    def test_main_timeout_rejected(self):
        def runner(args, **kwargs):
            raise subprocess.TimeoutExpired(args, 120)
        with self.assertRaisesRegex(RuntimeError, 'executable self-test timed out'):
            test_portable_archive(self.archive, runner=runner)

    def test_main_launch_error_rejected(self):
        def runner(args, **kwargs):
            raise OSError('missing runtime')
        with self.assertRaisesRegex(RuntimeError, 'executable could not start'):
            test_portable_archive(self.archive, runner=runner)

    def test_recovery_timeout_rejected(self):
        def runner(args, **kwargs):
            marker = Path(args[2])
            if Path(args[0]).name == 'EpicerieRecovery.exe':
                raise subprocess.TimeoutExpired(args, 120)
            marker.write_text('PASS: smoke', encoding='utf-8')
            return type('Result', (), {'returncode': 0})()
        with self.assertRaisesRegex(RuntimeError, 'recovery self-test timed out'):
            test_portable_archive(self.archive, runner=runner)

    def test_recovery_launch_error_rejected(self):
        def runner(args, **kwargs):
            marker = Path(args[2])
            if Path(args[0]).name == 'EpicerieRecovery.exe':
                raise OSError('not executable')
            marker.write_text('PASS: smoke', encoding='utf-8')
            return type('Result', (), {'returncode': 0})()
        with self.assertRaisesRegex(RuntimeError, 'recovery could not start'):
            test_portable_archive(self.archive, runner=runner)
