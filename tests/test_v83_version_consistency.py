import tempfile
import unittest
from pathlib import Path
from release_version import check_versions, VERSION

ROOT = Path(__file__).resolve().parents[1]

class VersionConsistencyTests(unittest.TestCase):
    def test_current_release_consistent(self):
        self.assertEqual(check_versions(ROOT), [])

    def test_outdated_installer_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'app.py').write_text((ROOT / 'app.py').read_text(encoding='utf-8'), encoding='utf-8')
            (root / 'installer.iss').write_text('#define AppVersion "81.0-buildkit"\n', encoding='utf-8')
            self.assertIn('Installer version mismatch', check_versions(root))

    def test_outdated_app_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'app.py').write_text('Épicerie Enterprise V80\nÉPICERIE ENTERPRISE V80', encoding='utf-8')
            (root / 'installer.iss').write_text(f'#define AppVersion "{VERSION}.0-buildkit"\n', encoding='utf-8')
            self.assertEqual(len(check_versions(root)), 2)
