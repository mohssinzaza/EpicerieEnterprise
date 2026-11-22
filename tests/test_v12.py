import tempfile,unittest
from pathlib import Path
from security import SecureStore
class AuthTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=SecureStore(Path(self.tmp.name)/'test.db')
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def test_initial_admin(self):
  self.s.bootstrap('admin','strong_password_123');self.assertTrue(self.s.has_users())
  with self.assertRaises(PermissionError):self.s.bootstrap('another','strong_password_123')
 def test_wrong_password(self):
  self.s.bootstrap('admin','strong_password_123')
  with self.assertRaises(PermissionError):self.s.login('admin','wrong')
 def test_role_denied(self):
  self.s.bootstrap('admin','strong_password_123');self.s.login('admin','strong_password_123')
  self.s.create_user('cash','cashier_password_123','cashier');self.s.login('cash','cashier_password_123')
  with self.assertRaises(PermissionError):self.s.add_product('123','Milk','8','5',0)
  with self.assertRaises(PermissionError):self.s.backup(Path(self.tmp.name)/'backup.db')
 def test_cashier_can_sell(self):
  self.s.bootstrap('admin','strong_password_123');self.s.login('admin','strong_password_123')
  self.s.add_product('123','Milk','8','5',3);self.s.create_user('cash','cashier_password_123','cashier')
  self.s.login('cash','cashier_password_123');self.assertEqual(self.s.sale('req1',[('123',1)],'10')[1],800)
 def test_disabled(self):
  self.s.bootstrap('admin','strong_password_123');self.s.login('admin','strong_password_123')
  self.s.create_user('cash','cashier_password_123','cashier');self.s.disable_user('cash')
  with self.assertRaises(PermissionError):self.s.login('cash','cashier_password_123')
 def test_password_policy(self):
  with self.assertRaises(ValueError):self.s.bootstrap('admin','short')
if __name__=='__main__':unittest.main()
