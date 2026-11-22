import tempfile,unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from profit_reports import calculate,bounds,export_csv

class ProfitTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=CommercialStore(Path(self.tmp.name)/'test.db')
  self.store.bootstrap('admin','ThisIsALongTestPassword!');self.store.login('admin','ThisIsALongTestPassword!')
  self.store.add_product('111','Sugar',10,6,20)
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def test_day_and_week_boundaries(self):
  self.assertEqual(bounds('week','2026-11-22'),('2026-11-16','2026-11-23'))
  self.assertEqual(bounds('month','2026-12-31'),('2026-12-01','2027-01-01'))
  self.assertEqual(bounds('day','2026-11-22'),('2026-11-22','2026-11-23'))
 def test_invalid_period(self):
  with self.assertRaises(ValueError):bounds('year','2026-11-22')
 def test_sales_cost_expenses(self):
  self.store.sale('key1',[('111',2)],20)
  today=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).date().isoformat()
  report=calculate(self.store,'day',today)
  self.assertEqual((report.sales_cents,report.cogs_cents,report.gross_profit_cents),(2000,1200,800))
  self.store.expense('rent','Test expense','3')
  report=calculate(self.store,'day',today)
  self.assertEqual(report.operating_profit_cents,500)
 def test_old_period_empty(self):
  self.assertEqual(calculate(self.store,'month','2020-01-01').operating_profit_cents,0)
 def test_export_utf8(self):
  p=calculate(self.store,'day','2020-01-01');target=Path(self.tmp.name)/'profits.csv'
  export_csv(p,target)
  self.assertIn('operating_profit_cents',target.read_text(encoding='utf-8-sig'))
 def test_returns_restore_original_cost(self):
  sid,_,_=self.store.sale('key2',[('111',2)],20)
  self.store.return_full_sale(sid)
  today=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).date().isoformat()
  p=calculate(self.store,'day',today)
  self.assertEqual((p.net_revenue_cents,p.gross_profit_cents,p.operating_profit_cents),(0,0,0))

if __name__=='__main__':unittest.main()
