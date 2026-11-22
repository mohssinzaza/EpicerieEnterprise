import tempfile,unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_audit import snapshot
from cash_reconciliation import inspect
from cash_movements import movements

class RefundMethods(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.s=CommercialStore(Path(self.tmp.name)/'db.sqlite')
  self.s.bootstrap('admin','Password!2026');self.s.login('admin','Password!2026')
  self.s.add_product('ABC','Item','10','5',10)
  self.s.open_cash('100')
 def tearDown(self):
  self.s.close();self.tmp.cleanup()
 def sale(self):
  return self.s.sale('test',[('ABC',1)],'10')[0]
 def test_cash_refund(self):
  self.s.return_full_sale(self.sale(),'cash')
  self.assertEqual(snapshot(self.s).expected_cents,10000)
  self.assertTrue(inspect(self.s).ready_for_close)
  self.assertEqual(sum(m.amount_cents for m in movements(self.s)),10000)
 def test_bank_refund_does_not_reduce_cash(self):
  self.s.return_full_sale(self.sale(),'bank')
  self.assertEqual(snapshot(self.s).expected_cents,11000)
  self.assertTrue(inspect(self.s).ready_for_close)
 def test_cheque_refund_does_not_reduce_cash(self):
  self.s.return_full_sale(self.sale(),'cheque')
  self.assertEqual(snapshot(self.s).expected_cents,11000)
 def test_unknown_refund_blocks_verified_close(self):
  self.s.return_full_sale(self.sale())
  self.assertEqual(snapshot(self.s).expected_cents,10000)
  self.assertFalse(inspect(self.s).ready_for_close)
 def test_invalid_method_no_mutation(self):
  sid=self.sale()
  with self.assertRaises(ValueError):self.s.return_full_sale(sid,'crypto')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM sale_returns').fetchone()[0],0)
 def test_method_persists_reopen(self):
  self.s.return_full_sale(self.sale(),'bank')
  path=Path(self.tmp.name)/'db.sqlite'
  self.s.close();self.s=CommercialStore(path)
  self.assertEqual(self.s.db.execute('SELECT refund_method FROM sale_returns').fetchone()[0],'bank')
