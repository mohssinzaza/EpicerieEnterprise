import tempfile
import unittest
from pathlib import Path
from verify_windows_build import verify, REQUIRED

ROOT = Path(__file__).resolve().parents[1]

class WindowsArtifactTests(unittest.TestCase):
    @staticmethod
    def _minimal_pe():
        import struct
        data = bytearray(2048)
        data[:2] = b'MZ'
        struct.pack_into('<I', data, 0x3c, 128)
        data[128:132] = b'PE\0\0'
        struct.pack_into('<HHIIIHH', data, 132, 0x8664, 1, 0, 0, 0, 240, 0)
        return bytes(data)

    def test_missing_artifacts_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(len(verify(Path(folder))), 3)

    def test_small_artifacts_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for rel in REQUIRED:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b'MZ')
            self.assertEqual(len(verify(root)), 3)

    def test_non_pe_files_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for rel in REQUIRED:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b'XX' + bytes(1024))
            self.assertEqual(len(verify(root)), 3)

    def test_pe_signature_passes_structural_check(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for rel in REQUIRED:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(self._minimal_pe())
            self.assertEqual(verify(root), [])

    def test_build_requires_inno_and_runs_tests(self):
        text = (ROOT / 'BUILD_ON_WINDOWS.bat').read_text()
        self.assertIn('if not defined ISCC (', text)
        self.assertIn('python -m unittest discover -s tests -q || goto error', text)
        self.assertIn('python verify_windows_build.py || goto error', text)
