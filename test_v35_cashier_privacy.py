import unittest
from pathlib import Path
from security import PERMISSIONS

class CashierPrivacy(unittest.TestCase):
 def test_cashier_sales_only(self):
  self.assertEqual(PERMISSIONS['cashier'], {'sales'})
 def test_no_cost_query_for_cashier(self):
  source=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
  self.assertIn("SELECT id,barcode,name,price_cents,stock FROM products",source)
  self.assertIn("if store.current_user[2]=='cashier':",source)
 def test_startup_confidential_refresh_admin_only(self):
  source=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
  self.assertIn("if store.current_user[2]=='admin':\n refresh_products();refresh_history();refresh_suppliers();refresh_return_lines();refresh_lots();refresh_reports()",source)
