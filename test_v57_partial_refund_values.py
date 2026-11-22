import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_reconciliation import inspect
from engine import stamp


class PartialRefundValueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = CommercialStore(Path(self.tmp.name) / 'shop.db')
        self.addCleanup(self.store.close)
        self.store.bootstrap('admin', 'secure-password-2026')
        self.store.login('admin', 'secure-password-2026')
        self.store.add_product('SUGAR', 'Sugar', '10', '4', 30)
        self.store.open_cash('100')
        self.sale_id, _, _ = self.store.sale('sale-ref', [('SUGAR', 2)], '20')
        self.line_id = self.store.db.execute('SELECT id FROM sale_lines WHERE sale_id=?', (self.sale_id,)).fetchone()[0]

    def refund(self, amount, qty=1):
        db = self.store.db
        rid = db.execute('INSERT INTO partial_returns(sale_id,created_at,refund_cents,refund_method) VALUES(?,?,?,?)',
                         (self.sale_id, stamp(), amount, 'cash')).lastrowid
        db.execute('INSERT INTO partial_return_lines(return_id,sale_line_id,quantity) VALUES(?,?,?)',
                   (rid, self.line_id, qty))

    def test_valid_partial_refund(self):
        self.refund(1000)
        self.assertFalse(any('do not match returned item values' in w for w in inspect(self.store).warnings))

    def test_underpaid_partial_refund(self):
        self.refund(900)
        self.assertTrue(any('do not match returned item values' in w for w in inspect(self.store).warnings))

    def test_overpaid_partial_refund(self):
        self.refund(1100)
        self.assertTrue(any('do not match returned item values' in w for w in inspect(self.store).warnings))

    def test_check_does_not_modify_data(self):
        self.refund(900)
        before = self.store.db.execute('SELECT refund_cents FROM partial_returns').fetchall()
        inspect(self.store)
        self.assertEqual(before, self.store.db.execute('SELECT refund_cents FROM partial_returns').fetchall())
