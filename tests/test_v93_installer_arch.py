import unittest
from pathlib import Path

class InstallerArchitectureTests(unittest.TestCase):
    def test_installer_requires_x64_windows(self):
        script = (Path(__file__).resolve().parents[1] / "BUILD_ON_WINDOWS.bat").read_text()
        self.assertIn("PROCESSOR_ARCHITECTURE", script)
        self.assertIn("PROCESSOR_ARCHITEW6432", script)
        self.assertIn("AMD64", script)

    def test_installer_requires_64_bit_python(self):
        script = (Path(__file__).resolve().parents[1] / "BUILD_ON_WINDOWS.bat").read_text()
        self.assertIn("struct.calcsize", script)
        self.assertIn("64-bit Python required", script)

    def test_installer_checks_packaged_binary_before_setup(self):
        script = (Path(__file__).resolve().parents[1] / "BUILD_ON_WINDOWS.bat").read_text()
        self.assertLess(script.index("--self-test"), script.index('"installer.iss"'))
