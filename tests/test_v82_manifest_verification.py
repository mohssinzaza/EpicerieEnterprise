import json
import tempfile
import unittest
from pathlib import Path
from verify_windows_build import REQUIRED, verify_manifest, write_manifest
from tests.test_v80_windows_artifacts import WindowsArtifactTests


class ManifestVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        payload = WindowsArtifactTests._minimal_pe()
        for relative in REQUIRED:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        self.manifest = write_manifest(self.root)

    def test_valid_release(self):
        self.assertEqual(verify_manifest(self.root), [])

    def test_changed_bytes_same_size(self):
        path = self.root / REQUIRED[0]
        payload = bytearray(path.read_bytes())
        payload[-1] ^= 1
        path.write_bytes(payload)
        self.assertIn('SHA-256 mismatch', ' '.join(verify_manifest(self.root)))

    def test_missing_artifact(self):
        (self.root / REQUIRED[1]).unlink()
        self.assertTrue(verify_manifest(self.root))

    def test_missing_manifest(self):
        self.manifest.unlink()
        self.assertTrue(verify_manifest(self.root))

    def test_extra_manifest_entry(self):
        obj = json.loads(self.manifest.read_text())
        obj['files']['other.exe'] = obj['files'][REQUIRED[0].as_posix()]
        self.manifest.write_text(json.dumps(obj))
        self.assertIn('list mismatch', ' '.join(verify_manifest(self.root)))

    def test_malformed_manifest(self):
        self.manifest.write_text('{invalid')
        self.assertTrue(verify_manifest(self.root))
