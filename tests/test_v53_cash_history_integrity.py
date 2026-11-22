import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_history import closed_sessions

class HistoryIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=CommercialStore(Path(self.tmp.name)/'shop.db')
        self.addCleanup(self.store.close)
        self.store.bootstrap('admin','very-secure-password-2026')
        self.store.login('admin','very-secure-password-2026')
        self.store.open_cash('100')
        self.store.close_cash('95')

    def test_normal_history(self):
        self.assertEqual(len(closed_sessions(self.store)),1)

    def test_negative_actual_detected(self):
        self.store.db.execute('UPDATE cash_sessions SET actual_cents=-1, variance_cents=-10001 WHERE closed_at IS NOT NULL')
        with self.assertRaisesRegex(ValueError,'Negative historical'):closed_sessions(self.store)

    def test_reversed_timestamps_detected(self):
        self.store.db.execute("UPDATE cash_sessions SET opened_at='2099-01-01T00:00:00' WHERE closed_at IS NOT NULL")
        with self.assertRaisesRegex(ValueError,'timestamps'):closed_sessions(self.store)

    def test_invalid_timestamp_detected(self):
        self.store.db.execute("UPDATE cash_sessions SET closed_at='invalid-date' WHERE closed_at IS NOT NULL")
        with self.assertRaisesRegex(ValueError,'timestamps'):closed_sessions(self.store)
