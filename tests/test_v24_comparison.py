import datetime as dt
import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from profit_reports import compare_periods, previous_period_date

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = CommercialStore(Path(self.temp.name) / 'store.db')
        self.store.bootstrap('admin', 'ThisIsALongTestPassword!')
        self.store.login('admin', 'ThisIsALongTestPassword!')
        self.store.add_product('101', 'Flour', 12, 8, 10)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_previous_day(self):
        self.assertEqual(previous_period_date('day', '2026-01-01'), dt.date(2025, 12, 31))

    def test_previous_week(self):
        self.assertEqual(previous_period_date('week', '2026-11-22'), dt.date(2026, 11, 15))

    def test_previous_month(self):
        self.assertEqual(previous_period_date('month', '2026-03-31'), dt.date(2026, 2, 28))

    def test_comparison_zero_base(self):
        current, previous, delta, growth = compare_periods(self.store, 'month', '2020-02-01')
        self.assertEqual((current.operating_profit_cents, previous.operating_profit_cents, delta), (0, 0, 0))
        self.assertIsNone(growth)

    def test_comparison_has_no_db_writes(self):
        before = self.store.db.total_changes
        compare_periods(self.store, 'day', '2020-02-01')
        self.assertEqual(self.store.db.total_changes, before)

if __name__ == '__main__':
    unittest.main()
