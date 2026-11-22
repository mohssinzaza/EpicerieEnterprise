import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PortableOnlyBuildTests(unittest.TestCase):
    def test_build_file_exists(self):
        self.assertTrue((ROOT/'BUILD_PORTABLE_ONLY_WINDOWS.bat').is_file())
    def test_no_inno_requirement(self):
        s=(ROOT/'BUILD_PORTABLE_ONLY_WINDOWS.bat').read_text()
        self.assertNotIn('ISCC',s)
        self.assertNotIn('installer.iss',s)
    def test_builds_both_executables(self):
        s=(ROOT/'BUILD_PORTABLE_ONLY_WINDOWS.bat').read_text()
        self.assertIn('--name EpicerieEnterprise',s)
        self.assertIn('--name EpicerieRecovery',s)
    def test_checks_tests_and_failure(self):
        s=(ROOT/'BUILD_PORTABLE_ONLY_WINDOWS.bat').read_text()
        self.assertIn('unittest discover',s)
        self.assertIn('|| goto error',s)
    def test_portable_package(self):
        s=(ROOT/'BUILD_PORTABLE_ONLY_WINDOWS.bat').read_text()
        self.assertIn('python make_portable.py',s)
