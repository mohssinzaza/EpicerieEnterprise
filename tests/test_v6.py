import tempfile,unittest
from pathlib import Path
from enterprise import EnterpriseStore
class TestEnterprise(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=EnterpriseStore(Path(self.tmp.name)/'test.db');self.s.add_product('ABC','Milk','10','4',5);self.sid=self.s.supplier('Supplier')
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def stock(self):return self.s.db.execute("SELECT stock FROM products WHERE barcode='ABC'").fetchone()[0]
 def test_purchase_and_debt(self):
  pid,total=self.s.purchase('INV-1',self.sid,[('ABC',3,'5')],'4');self.assertEqual((total,self.stock()),(1500,8));self.s.pay_supplier(pid,'11');self.assertEqual(self.s.db.execute('SELECT paid_cents FROM purchases').fetchone()[0],1500)
 def test_duplicate_purchase_rollback(self):
  self.s.purchase('INV-1',self.sid,[('ABC',3,'5')]);
  with self.assertRaises(ValueError):self.s.purchase('INV-1',self.sid,[('ABC',2,'5')]);
  self.assertEqual(self.stock(),8)
 def test_unknown_product_atomic(self):
  with self.assertRaises(ValueError):self.s.purchase('INV-X',self.sid,[('ABC',2,'5'),('BAD',1,'2')]);
  self.assertEqual(self.stock(),5);self.assertEqual(self.s.db.execute('SELECT count(*) FROM purchases').fetchone()[0],0)
 def test_return_once(self):
  sale_id,_,_=self.s.sale('sale1',[('ABC',2)],'20');self.assertEqual(self.stock(),3);self.assertEqual(self.s.return_full_sale(sale_id),2000);self.assertEqual(self.stock(),5)
  with self.assertRaises(ValueError):self.s.return_full_sale(sale_id)
 def test_cash(self):
  self.s.open_cash('100');self.s.sale('sale1',[('ABC',1)],'10');self.s.expense('transport','delivery','3');self.assertEqual(self.s.close_cash('107'),(10700,0))
 def test_single_open_cash(self):
  self.s.open_cash('0')
  with self.assertRaises(Exception):self.s.open_cash('0')
 def test_backup(self):
  path=Path(self.tmp.name)/'backup.db';self.s.backup(path);self.assertTrue(path.is_file())
if __name__=='__main__':unittest.main()
