import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from supplier_accounts import CommercialStore
from cash_history import closed_sessions, export_cash_history

class CashHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=CommercialStore(Path(self.temp.name)/'shop.db')
        self.addCleanup(self.store.close)
        self.store.bootstrap('admin','very-secure-password-2026')
        self.store.login('admin','very-secure-password-2026')
        self.store.open_cash('100')
        self.store.close_cash('95')

    def test_closed_session_and_variance(self):
        rows=closed_sessions(self.store)
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0].expected_cents,rows[0].actual_cents,rows[0].variance_cents),(10000,9500,-500))

    def test_export_and_no_overwrite(self):
        target=Path(self.temp.name)/'history.csv'
        export_cash_history(self.store,target)
        with target.open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.reader(f))
        self.assertEqual(rows[1][-1],'-500')
        with self.assertRaises(FileExistsError):export_cash_history(self.store,target)

    def test_tampering_detected(self):
        self.store.db.execute('UPDATE cash_sessions SET variance_cents=123 WHERE closed_at IS NOT NULL')
        with self.assertRaisesRegex(ValueError,'variance mismatch'):closed_sessions(self.store)

    def test_bad_limit(self):
        for limit in (0,-1,10001,1.5,True):
            with self.subTest(limit=limit),self.assertRaises(ValueError):closed_sessions(self.store,limit)

    def test_atomic_export_failure(self):
        target=Path(self.temp.name)/'history.csv'
        with patch('cash_history.os.link',side_effect=OSError('disk error')):
            with self.assertRaises(OSError):export_cash_history(self.store,target)
        self.assertFalse(target.exists())
        self.assertFalse(list(Path(self.temp.name).glob('.cash-history-*')))
