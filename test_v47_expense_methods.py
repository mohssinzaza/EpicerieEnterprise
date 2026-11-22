import tempfile, unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_audit import snapshot
from cash_reconciliation import inspect
from cash_movements import movements

class ExpenseMethods(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=CommercialStore(Path(self.tmp.name)/'test.db')
  self.store.bootstrap('admin','Password!2026');self.store.login('admin','Password!2026')
  self.store.open_cash('100')
 def tearDown(self):
  self.store.close();self.tmp.cleanup()
 def test_cash_expense_reconciles(self):
  self.store.expense('rent','cash','7','cash')
  self.assertEqual(snapshot(self.store).expected_cents,9300)
  self.assertTrue(inspect(self.store).ready_for_close)
  self.assertEqual(sum(x.amount_cents for x in movements(self.store)),9300)
 def test_bank_expense_not_in_cash(self):
  self.store.expense('rent','bank','7','bank')
  self.assertEqual(snapshot(self.store).expected_cents,10000)
  self.assertTrue(inspect(self.store).ready_for_close)
 def test_cheque_expense_not_in_cash(self):
  self.store.expense('rent','cheque','7','cheque')
  self.assertEqual(snapshot(self.store).expected_cents,10000)
 def test_legacy_expense_warns(self):
  self.store.expense('rent','unknown','7')
  self.assertEqual(snapshot(self.store).expected_cents,9300)
  self.assertFalse(inspect(self.store).ready_for_close)
 def test_invalid_method_rejected(self):
  with self.assertRaises(ValueError):self.store.expense('rent','bad','7','crypto')
 def test_migration_existing_expense(self):
  self.store.expense('rent','old','2')
  path=Path(self.tmp.name)/'test.db'
  self.store.close()
  self.store=CommercialStore(path)
  self.assertEqual(self.store.db.execute('SELECT payment_method FROM expenses').fetchone()[0],'unknown')
