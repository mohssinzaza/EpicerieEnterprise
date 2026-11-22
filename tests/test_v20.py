import tempfile,unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_audit import snapshot
class TestCashAudit(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=CommercialStore(Path(self.tmp.name)/'db.sqlite')
  self.s.bootstrap('admin','very-secure-password-2026');self.s.login('admin','very-secure-password-2026')
  self.s.add_product('A','Sugar','10','4',30);self.s.open_cash('100')
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def test_empty(self):self.assertEqual(snapshot(self.s).expected_cents,10000)
 def test_sale(self):
  self.s.sale('s1',[('A',2)],'20');self.assertEqual(snapshot(self.s).expected_cents,12000)
 def test_expense(self):
  self.s.expense('rent','test','5');self.assertEqual(snapshot(self.s).expected_cents,9500)
 def test_credit_deposit_once(self):
  cid=self.s.add_customer('Ali',limit='500');self.s.credit_sale('c1',cid,[('A',2,'piece','detail')],deposit='5')
  r=snapshot(self.s);self.assertEqual(r.cash_sales_cents,0);self.assertEqual(r.customer_cash_cents,500);self.assertEqual(r.expected_cents,10500)
 def test_supplier_cash(self):
  sid=self.s.supplier('Vendor');pid,_=self.s.purchase('p1',sid,[('A',2,'4')]);self.s.settle_supplier_invoice('pay1',pid,'3',method='cash')
  self.assertEqual(snapshot(self.s).expected_cents,9700)
 def test_read_only(self):
  before=self.s.db.total_changes;snapshot(self.s);self.assertEqual(self.s.db.total_changes,before)
 def test_closed(self):
  self.s.close_cash('100')
  with self.assertRaises(ValueError):snapshot(self.s)
