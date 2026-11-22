import tempfile,unittest
from pathlib import Path
from advanced import AdvancedStore
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=AdvancedStore(Path(self.tmp.name)/'db.sqlite');self.s.add_product('111','Milk','8','5',10)
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def sell(self):
  sid,_,_=self.s.sale('order-1',[('111',3)],'24');line=self.s.db.execute('SELECT id FROM sale_lines WHERE sale_id=?',(sid,)).fetchone()[0];return sid,line
 def test_partial_return(self):
  sid,line=self.sell();rid,amount=self.s.return_items(sid,{line:2});self.assertEqual(amount,1600);self.assertEqual(self.s.db.execute('SELECT stock FROM products').fetchone()[0],9)
 def test_no_overreturn(self):
  sid,line=self.sell();self.s.return_items(sid,{line:2})
  with self.assertRaises(ValueError):self.s.return_items(sid,{line:2})
  self.assertEqual(self.s.db.execute('SELECT stock FROM products').fetchone()[0],9)
 def test_wrong_sale_line(self):
  sid,line=self.sell()
  with self.assertRaises(ValueError):self.s.return_items(sid,{line+100:1})
 def test_no_full_after_partial(self):
  sid,line=self.sell();self.s.return_items(sid,{line:1})
  with self.assertRaises(ValueError):self.s.return_full_sale(sid)
 def test_adjustment(self):
  self.assertEqual(self.s.adjust_stock('111',-2,'Damaged'),8)
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM stock_ledger WHERE reason="adjustment"').fetchone()[0],1)
 def test_negative_stock_block(self):
  with self.assertRaises(ValueError):self.s.adjust_stock('111',-11,'Count')
  self.assertEqual(self.s.db.execute('SELECT stock FROM products').fetchone()[0],10)
 def test_report(self):
  sid,line=self.sell();self.s.return_items(sid,{line:1});o=self.s.overview();self.assertEqual(o['net_sales_cents'],1600);self.assertEqual(o['estimated_gross_profit_cents'],600)
 def test_backup(self):
  target=Path(self.tmp.name)/'backup.db';self.s.backup(target);self.assertTrue(target.is_file())
if __name__=='__main__':unittest.main()
