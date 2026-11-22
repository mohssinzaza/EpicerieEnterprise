import unittest
from pathlib import Path

class LotCostGuiTests(unittest.TestCase):
 def test_manager_only_controls(self):
  src=(Path(__file__).resolve().parents[1]/'app.py').read_text()
  self.assertIn("if 'inventory' in PERMISSIONS[store.current_user[2]] and 'reports' in PERMISSIONS[store.current_user[2]]:",src)
  self.assertIn('command=save_lot_acquisition_cost',src)
  self.assertIn('command=show_lot_costing_summary',src)
 def test_no_silent_cost_substitution(self):
  src=(Path(__file__).resolve().parents[1]/'lot_costing.py').read_text()
  self.assertIn('None if cost is None else qty*cost',src)
