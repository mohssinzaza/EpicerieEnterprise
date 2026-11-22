import tempfile,unittest
from pathlib import Path
from pricing import PricingStore
class TierTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=PricingStore(Path(self.tmp.name)/'a.db');self.s.bootstrap('admin','StrongPass1234');self.s.login('admin','StrongPass1234');self.s.add_product('ABC','Test',10,5,120);self.s.set_tier('ABC','gros',7,12);self.s.set_tier('ABC','demi_gros',8,6);self.s.set_unit('ABC','carton',12)
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def test_wholesale_carton(self):
  sid,total,change=self.s.sale_tiered('s1',[('ABC',2,'carton','gros')],200)
  self.assertEqual((total,change),(16800,3200));self.assertEqual(self.s.db.execute('SELECT stock FROM products').fetchone()[0],96)
 def test_minimum_rejected(self):
  with self.assertRaises(ValueError):self.s.sale_tiered('s2',[('ABC',2,'piece','gros')],200)
 def test_duplicate_key(self):
  self.s.sale_tiered('s1',[('ABC',1,'carton','gros')],100)
  self.s.sale_tiered('s1',[('ABC',1,'carton','gros')],100)
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM sales').fetchone()[0],1)
 def test_aggregate_stock(self):
  with self.assertRaises(ValueError):self.s.sale_tiered('s3',[('ABC',6,'carton','gros'),('ABC',6,'carton','gros')],2000)
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM sales').fetchone()[0],0)
 def test_detail_default(self):
  self.assertEqual(self.s.sale_tiered('s4',[('ABC',1,'piece','detail')],10)[1],1000)
 def test_permission(self):
  self.s.create_user('seller','SellerPass1234','cashier');self.s.login('seller','SellerPass1234')
  with self.assertRaises(PermissionError):self.s.set_tier('ABC','gros',6,12)
if __name__=='__main__':unittest.main()
