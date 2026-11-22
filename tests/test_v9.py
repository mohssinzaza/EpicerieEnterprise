import unittest,tempfile,datetime
from pathlib import Path
from expiry import ExpiryStore
class TestExpiry(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=ExpiryStore(Path(self.tmp.name)/'test.db')
  self.s.add_product('6111234567890','Lait',8,5,0)
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def test_receipt_and_alert(self):
  today=datetime.date(2026,11,22)
  self.s.receive_lot('6111234567890',12,'INV1','LOT1','2026-11-25')
  self.assertEqual(self.s.db.execute('SELECT stock FROM products').fetchone()[0],12)
  self.assertEqual(self.s.expiry_alerts(30,today)[0][-1],'SOON')
 def test_expired(self):
  self.s.receive_lot('6111234567890',2,'INV2','LOT2','2026-11-01')
  self.assertEqual(self.s.expiry_alerts(30,datetime.date(2026,11,22))[0][-1],'EXPIRED')
 def test_duplicate_atomic(self):
  self.s.receive_lot('6111234567890',2,'INV2','LOT2','2026-11-01')
  with self.assertRaises(Exception):self.s.receive_lot('6111234567890',5,'INV2','LOT2','2026-11-01')
  self.assertEqual(self.s.db.execute('SELECT stock FROM products').fetchone()[0],2)
 def test_invalid_date(self):
  with self.assertRaises(ValueError):self.s.receive_lot('6111234567890',1,'INV','LOT','2026-02-30')
  self.assertEqual(self.s.db.execute('SELECT stock FROM products').fetchone()[0],0)
 def test_unknown_product_atomic(self):
  with self.assertRaises(ValueError):self.s.receive_lot('UNKNOWN',1,'INV','LOT','2026-12-01')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM expiry_lots').fetchone()[0],0)
if __name__=='__main__':unittest.main()
