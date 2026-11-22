import unittest
from tests.test_v89_portable_integrity import fake_pe
from make_portable import is_x64_pe

class X64PortableTests(unittest.TestCase):
    def test_x64_pe_accepted(self):
        self.assertTrue(is_x64_pe(fake_pe()))
    def test_x86_pe_rejected(self):
        self.assertFalse(is_x64_pe(fake_pe(0x14c)))
    def test_fake_mz_rejected(self):
        self.assertFalse(is_x64_pe(b'MZ' + b'0' * 1100))
    def test_truncated_header_rejected(self):
        self.assertFalse(is_x64_pe(fake_pe()[:80]))
