import tempfile
import unittest
import zipfile
from pathlib import Path
from make_portable import make_portable, verify_portable
from test_v89_portable_integrity import fake_pe

class PortableSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / 'dist').mkdir()
        for name in ('EpicerieEnterprise.exe', 'EpicerieRecovery.exe'):
            (root / 'dist' / name).write_bytes(fake_pe())
        (root / 'WINDOWS_ACCEPTANCE_AR.md').write_text('acceptance')
        self.archive = make_portable(root)

    def test_valid_archive(self):
        self.assertTrue(verify_portable(self.archive))

    def test_reject_symlink_member(self):
        with zipfile.ZipFile(self.archive, 'a') as z:
            info = zipfile.ZipInfo('evil-link')
            info.create_system = 3
            info.external_attr = (0o120777 << 16)
            z.writestr(info, 'target')
        with self.assertRaisesRegex(ValueError, 'Symbolic links'):
            verify_portable(self.archive)

    def test_reject_unexpected_file(self):
        with zipfile.ZipFile(self.archive, 'a') as z:
            z.writestr('../outside.txt', 'not allowed')
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            verify_portable(self.archive)
