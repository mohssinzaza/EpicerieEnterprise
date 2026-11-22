import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from verify_windows_build import REQUIRED, verify, write_manifest
from tests.test_v80_windows_artifacts import WindowsArtifactTests

class ManifestTests(unittest.TestCase):
    def test_manifest_hashes_all_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = WindowsArtifactTests._minimal_pe()
            for relative in REQUIRED:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            manifest = write_manifest(root)
            obj = json.loads(manifest.read_text(encoding='utf-8'))
            self.assertEqual(len(obj['files']), 3)
            for relative in REQUIRED:
                item = obj['files'][relative.as_posix()]
                self.assertEqual(item['sha256'], hashlib.sha256(payload).hexdigest())
                self.assertEqual(item['size_bytes'], len(payload))

    def test_manifest_refuses_invalid_build(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                write_manifest(Path(folder))

    def test_mz_only_does_not_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for relative in REQUIRED:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'MZ' + bytes(2048))
            self.assertEqual(len(verify(root)), 3)
