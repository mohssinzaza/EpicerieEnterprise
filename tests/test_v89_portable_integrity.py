import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from make_portable import make_portable, verify_portable

def fake_pe(machine=0x8664):
    data = bytearray(1200)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 128)
    data[128:132] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', data, 132, machine, 3, 0, 0, 0, 240, 0)
    return bytes(data)

class PortableIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'dist').mkdir()
        for exe in ('EpicerieEnterprise.exe', 'EpicerieRecovery.exe'):
            (self.root/'dist'/exe).write_bytes(fake_pe())
        (self.root/'WINDOWS_ACCEPTANCE_AR.md').write_text('acceptance')

    def test_archive_is_verified(self):
        self.assertTrue(verify_portable(make_portable(self.root)))

    def test_detects_same_size_tampering(self):
        output = make_portable(self.root)
        with zipfile.ZipFile(output) as z:
            entries = {name:z.read(name) for name in z.namelist()}
        entries['EpicerieEnterprise.exe'] = fake_pe()[:-1] + b'1'
        with zipfile.ZipFile(output, 'w') as z:
            for name,data in entries.items(): z.writestr(name,data)
        with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):
            verify_portable(output)

    def test_rejects_unexpected_file(self):
        output = make_portable(self.root)
        with zipfile.ZipFile(output,'a') as z: z.writestr('extra.txt','x')
        with self.assertRaisesRegex(ValueError,'Unexpected'):
            verify_portable(output)

    def test_rejects_non_windows_executable(self):
        (self.root/'dist'/'EpicerieRecovery.exe').write_bytes(b'NO' + b'0'*1100)
        with self.assertRaisesRegex(RuntimeError,'Missing/incomplete Windows build'):
            make_portable(self.root)

if __name__ == '__main__': unittest.main()
