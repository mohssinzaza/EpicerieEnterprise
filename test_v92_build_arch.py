import unittest
from pathlib import Path
from make_portable import README, is_x64_pe

ROOT = Path(__file__).resolve().parents[1]

class BuildArchTests(unittest.TestCase):
    def test_build_requires_64_bit_python(self):
        script = (ROOT / 'BUILD_PORTABLE_ONLY_WINDOWS.bat').read_text()
        self.assertIn("struct.calcsize('P') == 8", script)
    def test_direct_executable_launch_is_documented(self):
        self.assertIn('double-click EpicerieEnterprise.exe', README)
    def test_invalid_pe_rejected(self):
        self.assertFalse(is_x64_pe(b'not a windows executable'))
