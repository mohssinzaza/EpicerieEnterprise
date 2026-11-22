import tempfile,unittest
from pathlib import Path
from security import SecureStore
class TwoAccounts(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=SecureStore(Path(self.tmp.name)/'db.sqlite')
  self.s.bootstrap('owner','administrator_123');self.s.login('owner','administrator_123')
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def test_only_cashier_role(self):
  with self.assertRaises(ValueError):self.s.create_user('stock','employee_password_123','stock')
 def test_max_two_accounts(self):
  self.s.create_user('seller','employee_password_123','cashier')
  with self.assertRaises(ValueError):self.s.create_user('seller2','employee_password_123','cashier')
 def test_cashier_no_financial_permissions(self):
  self.s.create_user('seller','employee_password_123','cashier');self.s.login('seller','employee_password_123')
  for permission in ('products','finance','reports','backup','users','purchases'):
   with self.assertRaises(PermissionError):self.s.require(permission)
 def test_admin_resets_cashier(self):
  self.s.create_user('seller','employee_password_123','cashier')
  self.s.reset_cashier_password('seller','new_employee_password_123')
  with self.assertRaises(PermissionError):self.s.login('seller','employee_password_123')
  self.assertEqual(self.s.login('seller','new_employee_password_123'),'cashier')
 def test_cashier_cannot_reset(self):
  self.s.create_user('seller','employee_password_123','cashier');self.s.login('seller','employee_password_123')
  with self.assertRaises(PermissionError):self.s.reset_cashier_password('seller','new_employee_password_123')
 def test_change_own_password(self):
  self.s.change_own_password('administrator_123','updated_admin_password_123')
  with self.assertRaises(PermissionError):self.s.login('owner','administrator_123')
  self.assertEqual(self.s.login('owner','updated_admin_password_123'),'admin')
 def test_wrong_old_password(self):
  with self.assertRaises(PermissionError):self.s.change_own_password('wrong','updated_admin_password_123')
if __name__=='__main__':unittest.main()
