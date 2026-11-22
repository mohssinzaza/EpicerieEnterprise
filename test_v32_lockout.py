import tempfile, unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from security import SecureStore

class LockoutTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'store.db'
  self.s=SecureStore(self.path);self.s.bootstrap('admin','secure_admin_password');self.s.login('admin','secure_admin_password')
  self.s.create_user('seller','secure_seller_password','cashier')
 def tearDown(self):self.s.close();self.temp.cleanup()
 def test_five_failures_lock_even_correct_password(self):
  for _ in range(5):
   with self.assertRaises(PermissionError):self.s.login('seller','wrong_password')
  with self.assertRaisesRegex(PermissionError,'locked'):
   self.s.login('seller','secure_seller_password')
 def test_success_resets_failures(self):
  for _ in range(4):
   with self.assertRaises(PermissionError):self.s.login('seller','wrong')
  self.assertEqual(self.s.login('seller','secure_seller_password'),'cashier')
  self.assertIsNone(self.s.db.execute('SELECT failures FROM login_lockouts WHERE username=?',('seller',)).fetchone())
 def test_lock_persists_after_reopen(self):
  for _ in range(5):
   with self.assertRaises(PermissionError):self.s.login('seller','bad')
  self.s.close();self.s=SecureStore(self.path)
  with self.assertRaisesRegex(PermissionError,'locked'):self.s.login('seller','secure_seller_password')
 def test_admin_unlock_cashier(self):
  for _ in range(5):
   with self.assertRaises(PermissionError):self.s.login('seller','bad')
  self.s.login('admin','secure_admin_password')
  self.s.unlock_cashier('seller')
  self.assertEqual(self.s.login('seller','secure_seller_password'),'cashier')
 def test_cashier_cannot_unlock(self):
  self.s.login('seller','secure_seller_password')
  with self.assertRaises(PermissionError):self.s.unlock_cashier('seller')
 def test_expired_lock_allows_login(self):
  for _ in range(5):
   with self.assertRaises(PermissionError):self.s.login('seller','bad')
  old=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
  self.s.db.execute('UPDATE login_lockouts SET locked_until=? WHERE username=?',(old,'seller'))
  self.assertEqual(self.s.login('seller','secure_seller_password'),'cashier')
if __name__=='__main__':unittest.main()
