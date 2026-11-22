import csv
import tempfile
import unittest
from pathlib import Path
from security import SecureStore
from verified_profit_export import export_verified_profit


class VerifiedProfitExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SecureStore(Path(self.tmp.name) / 'shop.db')
        self.store.bootstrap('admin', 'SafePassword!123')
        self.store.login('admin', 'SafePassword!123')
        self.target = Path(self.tmp.name) / 'profit.csv'

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def read(self):
        with self.target.open(encoding='utf-8-sig', newline='') as f:
            return list(csv.reader(f))

    def test_empty_period_verified_zero(self):
        export_verified_profit(self.store, self.target, 'month')
        self.assertIn(['status', 'VERIFIED'], self.read())
        self.assertIn(['net_profit_cents', '0'], self.read())

    def test_unknown_lot_cost_never_claims_profit(self):
        self.store.add_product('A', 'Test', 10, 4, 1)
        self.store.sale('s1', [('A', 1)], 10)
        export_verified_profit(self.store, self.target, 'month')
        self.assertIn(['status', 'UNVERIFIED'], self.read())
        self.assertIn(['net_profit_cents', ''], self.read())
        self.assertTrue(any(r[0] == 'issue' for r in self.read()))

    def test_no_overwrite(self):
        self.target.write_text('existing', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            export_verified_profit(self.store, self.target)
        self.assertEqual(self.target.read_text(encoding='utf-8'), 'existing')

    def test_cashier_cannot_export(self):
        self.store.create_user('cashier', 'CashierPass!123', 'cashier')
        self.store.logout()
        self.store.login('cashier', 'CashierPass!123')
        with self.assertRaises(PermissionError):
            export_verified_profit(self.store, self.target)
        self.assertFalse(self.target.exists())

    def test_invalid_period_creates_no_file(self):
        with self.assertRaises(ValueError):
            export_verified_profit(self.store, self.target, 'century')
        self.assertFalse(self.target.exists())
