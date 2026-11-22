import tempfile,unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_audit import snapshot
from cash_movements import movements
from cash_reconciliation import inspect

class PartialRefundMethods(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.s=CommercialStore(Path(self.tmp.name)/'db.sqlite')
  self.s.bootstrap('admin','Password!2026');self.s.login('admin','Password!2026')
  self.s.add_product('ABC','Item','10','5',10)
  self.s.open_cash('100')
  self.sid=self.s.sale('test',[('ABC',2)],'20')[0]
  self.line=self.s.db.execute('SELECT id FROM sale_lines WHERE sale_id=?',(self.sid,)).fetchone()[0]
 def tearDown(self):
  self.s.close();self.tmp.cleanup()
 def test_cash(self):
  self.s.return_items(self.sid,{self.line:1},'cash')
  self.assertEqual(snapshot(self.s).expected_cents,11000)
  self.assertTrue(inspect(self.s).ready_for_close)
  self.assertEqual(sum(x.amount_cents for x in movements(self.s)),11000)
 def test_bank(self):
  self.s.return_items(self.sid,{self.line:1},'bank')
  self.assertEqual(snapshot(self.s).expected_cents,12000)
  self.assertTrue(inspect(self.s).ready_for_close)
 def test_cheque(self):
  self.s.return_items(self.sid,{self.line:1},'cheque')
  self.assertEqual(snapshot(self.s).expected_cents,12000)
 def test_unknown_blocks(self):
  self.s.return_items(self.sid,{self.line:1})
  self.assertEqual(snapshot(self.s).expected_cents,11000)
  self.assertFalse(inspect(self.s).ready_for_close)
 def test_invalid_no_mutation(self):
  with self.assertRaises(ValueError):self.s.return_items(self.sid,{self.line:1},'crypto')
  self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM partial_returns').fetchone()[0],0)
 def test_persist(self):
  self.s.return_items(self.sid,{self.line:1},'bank')
  self.assertEqual(self.s.db.execute('SELECT refund_method FROM partial_returns').fetchone()[0],'bank')
