import sqlite3
import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_reconciliation import inspect

class CashIntegrityV50(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = CommercialStore(Path(self.temp.name) / 'test.sqlite')
        self.store.bootstrap('admin', 'Password!2026')
        self.store.login('admin', 'Password!2026')
        self.store.add_product('A50', 'Product', '10', '5', 20)
        self.store.open_cash('100')
        self.sale_id = self.store.sale('v50', [('A50', 2)], '20')[0]
    def tearDown(self):
        self.store.close()
        self.temp.cleanup()
    def test_clean_session(self):
        self.assertTrue(inspect(self.store).ready_for_close)
    def test_negative_bank_expense_blocks(self):
        self.store.expense('test', 'negative', '2', 'bank')
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.db.execute('UPDATE expenses SET amount_cents=-200')
        self.assertTrue(inspect(self.store).ready_for_close)
    def test_zero_full_refund_blocks(self):
        self.store.return_full_sale(self.sale_id, 'bank')
        self.store.db.execute('UPDATE sale_returns SET refund_cents=0')
        self.assertTrue(any('Full refunds contain invalid' in w for w in inspect(self.store).warnings))
    def test_invalid_full_refund_method_blocks(self):
        self.store.return_full_sale(self.sale_id, 'cash')
        self.store.db.execute("UPDATE sale_returns SET refund_method='invalid'")
        self.assertFalse(inspect(self.store).ready_for_close)
    def test_negative_partial_refund_blocks(self):
        line = self.store.db.execute('SELECT id FROM sale_lines WHERE sale_id=?',(self.sale_id,)).fetchone()[0]
        self.store.return_items(self.sale_id, {line:1}, 'bank')
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.db.execute('UPDATE partial_returns SET refund_cents=-1')
        self.assertTrue(inspect(self.store).ready_for_close)
