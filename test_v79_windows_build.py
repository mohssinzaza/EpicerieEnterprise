"""Static regression checks for Windows release build script."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class WindowsBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script=(ROOT/'BUILD_ON_WINDOWS.bat').read_text(encoding='utf-8')
        cls.installer=(ROOT/'installer.iss').read_text(encoding='utf-8')

    def test_fallback_python_command(self):
        self.assertIn('where python',self.script)
        self.assertIn('set "PYTHON_CMD=python"',self.script)

    def test_release_gate_precedes_executable_build(self):
        self.assertLess(self.script.index('python release_check.py'),self.script.index('python -m PyInstaller'))

    def test_inno_setup_failure_is_fatal(self):
        self.assertIn('"%ISCC%" "installer.iss" || goto error',self.script)
        self.assertIn('if not exist "installer_output\\EpicerieEnterprise_Setup.exe" goto error',self.script)

    def test_missing_inno_setup_does_not_claim_installer(self):
        self.assertIn('Inno Setup 6 required for a complete installer',self.script)

    def test_install_does_not_bundle_database(self):
        self.assertNotIn('enterprise_v14.db',self.installer)
        self.assertIn('EpicerieRecovery.exe',self.installer)

if __name__=='__main__': unittest.main()
