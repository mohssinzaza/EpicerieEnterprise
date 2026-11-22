import unittest,tempfile,datetime
from pathlib import Path
from quarantine import QuarantineStore
class QuarantineTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.s=QuarantineStore(Path(self.t.name)/'store.db')
  self.s.add_product('100','Milk','10','6');self.s.enable_lot_tracking('100')
  future=(datetime.date.today()+datetime.timedelta(days=30)).isoformat()
  self.s.receive_lot('100',3,'R1','L1',future)
  self.sid,_,_=self.s.sale('sale1',[('100',3)],'30')
  self.line=self.s.db.execute('SELECT id FROM sale_lines WHERE sale_id=?',(self.sid,)).fetchone()[0]
 def tearDown(self):self.s.close();self.t.cleanup()
 def test_quarantine_no_restock(self):
  rid=self.s.quarantine_return('q1',self.sid,{self.line:2},'customer return')
  self.assertEqual(self.s.quarantine_return('q1',self.sid,{self.line:2},'customer return'),rid)
  self.assertEqual(self.s.db.execute('SELECT stock FROM products WHERE barcode="100"').fetchone()[0],0)
  self.assertEqual(self.s.db.execute('SELECT remaining_qty FROM lot_balances').fetchone()[0],0)
  self.assertEqual(self.s.quarantine_report()[0][-1],2)
 def test_overreturn_rollback(self):
  self.s.quarantine_return('q1',self.sid,{self.line:2},'return')
  with self.assertRaises(ValueError):self.s.quarantine_return('q2',self.sid,{self.line:2},'return')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM quarantine_returns').fetchone()[0],1)
 def test_disposal_audit(self):
  rid=self.s.quarantine_return('q1',self.sid,{self.line:1},'damaged')
  self.s.dispose_quarantine(rid)
  self.assertEqual(self.s.quarantine_report()[0][4],'DISPOSED')
  with self.assertRaises(ValueError):self.s.dispose_quarantine(rid)
 def test_backup(self):
  self.s.quarantine_return('q1',self.sid,{self.line:1},'damaged')
  self.assertTrue(self.s.backup(Path(self.t.name)/'backup.db').exists())
if __name__=='__main__':unittest.main()
