import unittest,tempfile,datetime
from pathlib import Path
from supplier_accounts import CommercialStore
from profit_reports import product_profit_report,export_product_profit_csv
class ProductProfitTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=CommercialStore(Path(self.tmp.name)/'test.db')
  self.store.bootstrap('admin','ThisIsALongTestPassword!');self.store.login('admin','ThisIsALongTestPassword!')
  self.store.add_product('111','Sugar',10,6,20);self.store.add_product('222','Oil',20,12,20)
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def today(self):return datetime.datetime.now(datetime.timezone.utc).date().isoformat()
 def test_empty(self):self.assertEqual(product_profit_report(self.store,'day','2020-01-01'),[])
 def test_multi_product_margin(self):
  self.store.sale('sale1',[('111',2),('222',1)],40)
  r={x.barcode:x for x in product_profit_report(self.store,'day',self.today(),timezone_name='UTC')}
  self.assertEqual((r['111'].quantity_sold,r['111'].gross_profit_cents),(2,800))
  self.assertEqual((r['222'].quantity_sold,r['222'].gross_profit_cents),(1,800))
 def test_full_return(self):
  sid,_,_=self.store.sale('sale2',[('111',2)],20);self.store.return_full_sale(sid)
  r=product_profit_report(self.store,'day',self.today(),timezone_name='UTC')[0]
  self.assertEqual((r.quantity_returned,r.gross_profit_cents),(2,0))
 def test_csv(self):
  self.store.sale('sale3',[('111',1)],10)
  rows=product_profit_report(self.store,'day',self.today(),timezone_name='UTC')
  p=Path(self.tmp.name)/'products.csv';export_product_profit_csv(rows,p)
  self.assertIn('gross_profit_cents',p.read_text(encoding='utf-8-sig'))
 def test_invalid_period(self):
  with self.assertRaises(ValueError):product_profit_report(self.store,'year',self.today())
