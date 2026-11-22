import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_reconciliation import inspect
from verified_close import close_verified

class CashSaleIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CommercialStore(Path(self.tmp.name) / 'test.sqlite')
        self.store.bootstrap('admin', 'very-secure-password-2026')
        self.store.login('admin', 'very-secure-password-2026')
        self.store.add_product('A', 'Sugar', '10', '4', 30)
        self.store.open_cash('100')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_valid_sale_can_close(self):
        self.store.sale('sale1', [('A', 2)], '20')
        self.assertTrue(inspect(self.store).ready_for_close)

    def test_mismatched_sale_line_blocks_close(self):
        sale_id, _, _ = self.store.sale('sale1', [('A', 2)], '20')
        self.store.db.execute('UPDATE sale_lines SET unit_price_cents=1 WHERE sale_id=?', (sale_id,))
        result = inspect(self.store)
        self.assertFalse(result.ready_for_close)
        self.assertTrue(any('inconsistent' in msg for msg in result.warnings))
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            close_verified(self.store, '120')

    def test_missing_lines_blocks_close(self):
        sale_id, _, _ = self.store.sale('sale1', [('A', 2)], '20')
        self.store.db.execute('DELETE FROM sale_lines WHERE sale_id=?', (sale_id,))
        self.assertFalse(inspect(self.store).ready_for_close)

    def test_integrity_inspection_is_read_only(self):
        self.store.sale('sale1', [('A', 2)], '20')
        before = self.store.db.total_changes
        inspect(self.store)
        self.assertEqual(before, self.store.db.total_changes)
