import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_history import closed_sessions

class OverlapHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = CommercialStore(Path(self.tmp.name) / 'shop.db')
        self.addCleanup(self.store.close)
        self.store.bootstrap('admin', 'very-secure-password-2026')
        self.store.login('admin', 'very-secure-password-2026')
        self.store.open_cash('100')
        self.store.close_cash('100')
        self.store.open_cash('100')
        self.store.close_cash('100')

    def test_normal_adjacent_sessions(self):
        self.assertEqual(len(closed_sessions(self.store)), 2)

    def test_overlapping_sessions_rejected(self):
        self.store.db.execute("UPDATE cash_sessions SET opened_at='2020-01-01T00:00:00+00:00', closed_at='2030-01-01T00:00:00+00:00' WHERE id=1")
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            closed_sessions(self.store)

    def test_reverse_id_order_is_checked_chronologically(self):
        self.store.db.execute("UPDATE cash_sessions SET opened_at='2020-01-01T00:00:00+00:00', closed_at='2020-01-02T00:00:00+00:00' WHERE id=2")
        self.assertEqual(len(closed_sessions(self.store)), 2)
