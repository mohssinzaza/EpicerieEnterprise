import tempfile,unittest
from pathlib import Path
from credit import CreditStore
from customer_reports import CustomerReports
class TestReports(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=CreditStore(Path(self.tmp.name)/'db.sqlite');self.s.bootstrap('admin','verysecurepassword123');self.s.login('admin','verysecurepassword123');self.s.add_product('6111234567890','Milk','10','6',100);self.cid=self.s.add_customer('Client');self.r=CustomerReports(self.s);self.iid,_,_=self.s.credit_sale('sale',self.cid,[('6111234567890',3,'piece','detail')],'5','2026-01-10')
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def test_statement(self):
  x=self.r.statement(self.cid)[0];self.assertEqual((x['total_cents'],x['collected_cents'],x['unpaid_cents']),(3000,500,2500))
 def test_pending_cheque(self):
  self.s.receive_payment('ch',self.iid,'10','cheque',cheque_number='A1',bank_name='Bank',due_date='2026-01-15');x=self.r.statement(self.cid)[0];self.assertEqual((x['pending_cheques_cents'],x['unpaid_cents']),(1000,2500));self.assertEqual(len(self.r.cheques_due('2026-01-16')),1)
 def test_settlement(self):
  pid=self.s.receive_payment('ch',self.iid,'10','cheque',cheque_number='A1',bank_name='Bank',due_date='2026-01-15');self.s.settle_cheque(pid,True);self.assertEqual(self.r.statement(self.cid)[0]['unpaid_cents'],1500)
 def test_aging(self):self.assertEqual(self.r.aging('2026-01-20')[0][4],10)
 def test_export(self):
  p=Path(self.tmp.name)/'export.csv';self.assertEqual(self.r.export_statement(self.cid,p),1);self.assertIn('invoice_id',p.read_text(encoding='utf-8-sig'))
 def test_unknown_customer(self):
  with self.assertRaises(ValueError):self.r.statement(999)
if __name__=='__main__':unittest.main()
