import unittest,tempfile,uuid
from pathlib import Path
from credit import CreditStore
class TestCredit(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.s=CreditStore(Path(self.t.name)/'t.db');self.s.bootstrap('admin','verysecurepassword123');self.s.login('admin','verysecurepassword123');self.s.add_product('6111234567890','Milk','10','6',100);self.c=self.s.add_customer('Client','', '1000')
 def tearDown(self):self.s.close();self.t.cleanup()
 def sale(self,key='s1',deposit='0'):return self.s.credit_sale(key,self.c,[('6111234567890',2,'piece','detail')],deposit)
 def test_credit_and_cash(self):
  iid,sid,total=self.sale(deposit='5');self.assertEqual(total,2000);self.assertEqual(self.s.outstanding(self.c),1500)
  self.s.receive_payment('p1',iid,'10');self.assertEqual(self.s.outstanding(self.c),500)
 def test_cheque_pending_and_collected(self):
  iid,_,_=self.sale();pid=self.s.receive_payment('ch',iid,'20','cheque',cheque_number='A123',bank_name='Bank',due_date='2027-01-01');self.assertEqual(self.s.outstanding(self.c),2000)
  self.s.settle_cheque(pid,True);self.assertEqual(self.s.outstanding(self.c),0)
 def test_rejected_cheque(self):
  iid,_,_=self.sale();pid=self.s.receive_payment('ch',iid,'20','cheque',cheque_number='A123',bank_name='Bank',due_date='2027-01-01');self.s.settle_cheque(pid,False);self.assertEqual(self.s.outstanding(self.c),2000)
 def test_duplicate(self):
  self.sale();self.sale();self.assertEqual(self.s.db.execute('SELECT count(*) FROM sales').fetchone()[0],1)
 def test_rollback(self):
  with self.assertRaises(ValueError):self.s.credit_sale('bad',self.c,[('6111234567890',101,'piece','detail')]);self.assertEqual(self.s.db.execute('SELECT stock FROM products').fetchone()[0],100)
 def test_overpay(self):
  iid,_,_=self.sale();self.s.receive_payment('p',iid,'15');
  with self.assertRaises(ValueError):self.s.receive_payment('p2',iid,'6')
 def test_no_permission(self):
  self.s.create_user('cashier','verysecurepassword123','cashier');self.s.login('cashier','verysecurepassword123');
  with self.assertRaises(PermissionError):self.s.add_customer('No')
if __name__=='__main__':unittest.main()
