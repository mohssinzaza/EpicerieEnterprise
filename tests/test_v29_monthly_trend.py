import datetime as dt
import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from profit_reports import monthly_profit_trend, export_monthly_trend_csv

class MonthlyTrendTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=CommercialStore(Path(self.tmp.name)/'db.sqlite')
        self.store.bootstrap('admin','ThisIsALongTestPassword!')
        self.store.login('admin','ThisIsALongTestPassword!')
        self.store.add_product('123','Sugar',10,6,100)
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def test_twelve_months_and_empty_year(self):
        rows=monthly_profit_trend(self.store,2020,'UTC')
        self.assertEqual(len(rows),12)
        self.assertEqual(rows[0].month,'2020-01')
        self.assertEqual(rows[-1].month,'2020-12')
        self.assertTrue(all(r.operating_profit_cents==0 for r in rows))
    def test_current_month_sale(self):
        now=dt.datetime.now(dt.timezone.utc)
        self.store.sale('trend-sale',[('123',2)],20)
        rows=monthly_profit_trend(self.store,now.year,'UTC')
        self.assertEqual(rows[now.month-1].operating_profit_cents,800)
        self.assertEqual(sum(r.operating_profit_cents for r in rows),800)
    def test_reject_bad_year(self):
        for year in (True,'2026',0,10000):
            with self.subTest(year=year),self.assertRaises(ValueError):
                monthly_profit_trend(self.store,year)
    def test_export_and_no_overwrite(self):
        rows=monthly_profit_trend(self.store,2020,'UTC')
        target=Path(self.tmp.name)/'trend.csv'
        export_monthly_trend_csv(rows,target)
        self.assertEqual(len(target.read_text(encoding='utf-8-sig').splitlines()),13)
        with self.assertRaises(FileExistsError):export_monthly_trend_csv(rows,target)
    def test_read_only(self):
        before=self.store.db.total_changes
        monthly_profit_trend(self.store,2020,'UTC')
        self.assertEqual(self.store.db.total_changes,before)
