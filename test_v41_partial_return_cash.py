import tempfile, unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_reconciliation import inspect
from verified_close import close_verified

class PartialReturnCashTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = CommercialStore(Path(self.temp.name) / 'db.sqlite')
        self.store.bootstrap('admin', 'very-secure-password-2026')
        self.store.login('admin', 'very-secure-password-2026')
        self.store.add_product('A', 'Sugar', '10', '4', 30)
        self.store.open_cash('100')
    def tearDown(self):
        self.store.close()
        self.temp.cleanup()
    def make_partial_return(self):
        sale_id, _, _ = self.store.sale('s1', [('A', 2)], '20')
        line_id = self.store.db.execute('SELECT id FROM sale_lines WHERE sale_id=?', (sale_id,)).fetchone()[0]
        self.store.return_items(sale_id, {line_id: 1})
    def test_partial_return_blocks_close(self):
        self.make_partial_return()
        readiness = inspect(self.store)
        self.assertFalse(readiness.ready_for_close)
        self.assertTrue(any('Partial returns' in warning for warning in readiness.warnings))
        with self.assertRaisesRegex(ValueError, 'Partial returns'):
            close_verified(self.store, '110')
        self.assertIsNotNone(self.store.db.execute('SELECT id FROM cash_sessions WHERE closed_at IS NULL').fetchone())
    def test_without_return_cash_sale_is_ready(self):
        self.store.sale('s1', [('A', 2)], '20')
        self.assertTrue(inspect(self.store).ready_for_close)
    def test_partial_return_check_is_read_only(self):
        self.make_partial_return()
        before = self.store.db.total_changes
        inspect(self.store)
        self.assertEqual(before, self.store.db.total_changes)
