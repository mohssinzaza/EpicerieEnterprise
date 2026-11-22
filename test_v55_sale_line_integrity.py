import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_reconciliation import inspect
from verified_close import close_verified

class SaleLineIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = CommercialStore(Path(self.tmp.name) / 'shop.sqlite')
        self.addCleanup(self.store.close)
        self.store.bootstrap('admin', 'very-secure-password-2026')
        self.store.login('admin', 'very-secure-password-2026')
        self.store.add_product('A', 'Sugar', '10', '4', 30)
        self.store.open_cash('100')
        self.sid, _, _ = self.store.sale('sale1', [('A', 2)], '20')

    def test_negative_cost_detected_even_if_total_balances(self):
        self.store.db.execute('UPDATE sale_lines SET unit_cost_cents=-1 WHERE sale_id=?', (self.sid,))
        result = inspect(self.store)
        self.assertFalse(result.ready_for_close)
        self.assertTrue(any('invalid quantity, price or cost' in w for w in result.warnings))
        with self.assertRaises(ValueError):
            close_verified(self.store, '120')

    def test_negative_price_detected(self):
        self.store.db.execute('UPDATE sale_lines SET unit_price_cents=-1 WHERE sale_id=?', (self.sid,))
        self.assertFalse(inspect(self.store).ready_for_close)

    def test_orphan_line_detected(self):
        self.store.db.execute('PRAGMA foreign_keys=OFF')
        self.store.db.execute('UPDATE sale_lines SET sale_id=999999 WHERE sale_id=?', (self.sid,))
        self.assertTrue(any('orphan sale line' in w for w in inspect(self.store).warnings))

    def test_valid_sale_remains_ready(self):
        self.assertTrue(inspect(self.store).ready_for_close)
