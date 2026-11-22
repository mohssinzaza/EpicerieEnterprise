import unittest,tempfile,uuid
from pathlib import Path
from supplier_accounts import CommercialStore

class SupplierAccountTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=CommercialStore(Path(self.tmp.name)/'test.db')
  self.s.bootstrap('admin','secure password 123');self.s.login('admin','secure password 123')
  self.s.add_product('6111111111111','Sucre','12','7',0)
  self.supplier=self.s.supplier('Fournisseur A')
  self.purchase,_=self.s.purchase('INV-001',self.supplier,[('6111111111111',10,'7')])
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def test_partial_payment(self):
  self.s.settle_supplier_invoice('pay1',self.purchase,'20')
  self.assertEqual(self.s.supplier_balances()[0][-1],5000)
 def test_pending_cheque_and_clearing(self):
  pid=self.s.settle_supplier_invoice('cheque1',self.purchase,'40','cheque',cheque_number='C123',bank_name='Bank',due_date='2027-01-01')
  self.assertEqual(self.s.supplier_balances()[0][-1],7000)
  with self.assertRaises(ValueError):self.s.settle_supplier_invoice('pay2',self.purchase,'40')
  self.s.resolve_supplier_cheque(pid,True)
  self.assertEqual(self.s.supplier_balances()[0][-1],3000)
  with self.assertRaises(ValueError):self.s.resolve_supplier_cheque(pid,True)
 def test_rejected_cheque_releases_balance(self):
  pid=self.s.settle_supplier_invoice('c',self.purchase,'70','cheque',cheque_number='C',bank_name='B',due_date='2027-01-01')
  self.s.resolve_supplier_cheque(pid,False)
  self.s.settle_supplier_invoice('pay',self.purchase,'70')
  self.assertEqual(self.s.supplier_balances()[0][-1],0)
 def test_idempotency_conflict(self):
  x=self.s.settle_supplier_invoice('k',self.purchase,'10')
  self.assertEqual(x,self.s.settle_supplier_invoice('k',self.purchase,'10'))
  with self.assertRaises(ValueError):self.s.settle_supplier_invoice('k',self.purchase,'11')
 def test_invalid_cheque_rolls_back(self):
  with self.assertRaises(ValueError):self.s.settle_supplier_invoice('x',self.purchase,'10','cheque')
  self.assertEqual(self.s.supplier_balances()[0][-1],7000)
 def test_statement(self):
  self.s.settle_supplier_invoice('p',self.purchase,'10','bank',reference='TX-1')
  a,b=self.s.supplier_statement(self.supplier)
  self.assertEqual(len(a),1);self.assertEqual(b[0][5],'TX-1')
if __name__=='__main__':unittest.main()
