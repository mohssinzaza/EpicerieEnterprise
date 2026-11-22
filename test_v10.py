import tempfile,datetime,unittest
from pathlib import Path
from lot_control import ControlledStore
class LotTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=ControlledStore(Path(self.tmp.name)/'test.db')
  self.s.add_product('111','Lait','10','6',0);self.s.enable_lot_tracking('111')
  today=datetime.date.today();self.future=(today+datetime.timedelta(days=20)).isoformat();self.later=(today+datetime.timedelta(days=40)).isoformat();self.expired=(today-datetime.timedelta(days=1)).isoformat()
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def test_fefo_and_expiry(self):
  a=self.s.receive_lot('111',3,'A','A',self.later)
  b=self.s.receive_lot('111',2,'B','B',self.future)
  c=self.s.receive_lot('111',4,'C','C',self.expired)
  sid,total,change=self.s.sale('k1',[('111',4)],'40')
  self.assertEqual((total,change),(4000,0))
  allocations=self.s.db.execute('SELECT lot_id,quantity FROM sale_lot_allocations ORDER BY id').fetchall()
  self.assertEqual(allocations,[(b,2),(a,2)])
  self.assertEqual(self.s.db.execute('SELECT remaining_qty FROM lot_balances WHERE lot_id=?',(c,)).fetchone()[0],4)
  with self.assertRaisesRegex(ValueError,'non-expired'):self.s.sale('k2',[('111',2)],'20')
  self.assertEqual(self.s.db.execute('SELECT stock FROM products WHERE barcode="111"').fetchone()[0],5)
 def test_duplicate_sale(self):
  self.s.receive_lot('111',3,'A','A',self.future)
  a=self.s.sale('same',[('111',1)],'10');b=self.s.sale('same',[('111',1)],'10')
  self.assertEqual(a,b);self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM sale_lot_allocations').fetchone()[0],1)
 def test_guardrails(self):
  with self.assertRaises(ValueError):self.s.receive('111',1,'X')
  with self.assertRaises(ValueError):self.s.adjust_stock('111',1,'count')
  self.s.receive_lot('111',1,'A','A',self.future)
  sid,_,_=self.s.sale('x',[('111',1)],'10')
  with self.assertRaises(ValueError):self.s.return_full_sale(sid)
 def test_reconcile_before_tracking(self):
  self.s.add_product('222','Bread','5','2',2)
  with self.assertRaises(ValueError):self.s.enable_lot_tracking('222')
 def test_backup(self):
  self.s.receive_lot('111',2,'A','A',self.future)
  path=self.s.backup(Path(self.tmp.name)/'backup.db');self.assertTrue(path.exists())
if __name__=='__main__':unittest.main()
