# V12 role-aware store. Authentication required for mutating public API.
import hashlib, hmac, secrets, json
from datetime import datetime, timedelta, timezone
from engine import stamp
from quarantine import QuarantineStore

PERMISSIONS={
 'admin': {'products','sales','purchases','finance','inventory','returns','lots','backup','users','reports'},
 'manager': {'products','sales','purchases','finance','inventory','returns','lots','backup','reports'},
 'cashier': {'sales'},
 'stock': {'products','purchases','inventory','lots'},
}
class SecureStore(QuarantineStore):
 def __init__(self,path):
  super().__init__(path)
  self.db.executescript('''CREATE TABLE IF NOT EXISTS app_users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','manager','cashier','stock')),salt TEXT NOT NULL,hash TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
  CREATE TABLE IF NOT EXISTS login_events(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,username TEXT NOT NULL,success INTEGER NOT NULL);''')
  self.db.execute('''CREATE TABLE IF NOT EXISTS login_lockouts(username TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0, locked_until TEXT);''')
  self.current_user=None
 def has_users(self):return self.db.execute('SELECT COUNT(*) FROM app_users').fetchone()[0]>0
 def _hash(self,password,salt):return hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),bytes.fromhex(salt),310000).hex()
 def _validate_password(self,password):
  if len(password)<12 or len(password)>256:raise ValueError('Password must contain 12 to 256 characters')
 def bootstrap(self,username,password):
  self._validate_password(password)
  if not username.strip():raise ValueError('Username required')
  self.db.execute('BEGIN IMMEDIATE')
  try:
   if self.has_users():raise PermissionError('Initial admin already exists')
   salt=secrets.token_hex(16)
   self.db.execute('INSERT INTO app_users(username,role,salt,hash) VALUES(?,?,?,?)',(username.strip(),'admin',salt,self._hash(password,salt)))
   self.db.execute('COMMIT')
  except BaseException:self.db.execute('ROLLBACK');raise
 def login(self,username,password):
  # Persistent, per-username lockout: five failures -> fifteen minutes.
  # UTC timestamps avoid local clock/DST ambiguities.
  now=datetime.now(timezone.utc)
  lock=self.db.execute('SELECT failures,locked_until FROM login_lockouts WHERE username=?',(username,)).fetchone()
  if lock and lock[1]:
   until=datetime.fromisoformat(lock[1])
   if until>now:
    self.current_user=None
    raise PermissionError('Account temporarily locked; retry later / الحساب مقفل مؤقتاً')
  row=self.db.execute('SELECT id,role,salt,hash,active FROM app_users WHERE username=?',(username,)).fetchone()
  dummy_salt='00'*16
  digest=self._hash(password,row[2] if row else dummy_salt)
  ok=bool(row and row[4] and hmac.compare_digest(digest,row[3]))
  with self.db:
   self.db.execute('INSERT INTO login_events(created_at,username,success) VALUES(?,?,?)',(stamp(),username,int(ok)))
   if ok:
    self.db.execute('DELETE FROM login_lockouts WHERE username=?',(username,))
   else:
    failures=(lock[0] if lock and lock[1] and datetime.fromisoformat(lock[1])>now else (lock[0] if lock and not lock[1] else 0))+1
    until=(now+timedelta(minutes=15)).isoformat() if failures>=5 else None
    self.db.execute('INSERT INTO login_lockouts(username,failures,locked_until) VALUES(?,?,?) ON CONFLICT(username) DO UPDATE SET failures=excluded.failures,locked_until=excluded.locked_until',(username,failures,until))
  self.current_user=(row[0],username,row[1]) if ok else None
  if not ok:raise PermissionError('Invalid username or password')
  return row[1]
 def unlock_cashier(self,username):
  self.require('users')
  row=self.db.execute("SELECT 1 FROM app_users WHERE username=? AND role='cashier'",(username,)).fetchone()
  if not row:raise ValueError('Cashier not found')
  with self.db:self.db.execute('DELETE FROM login_lockouts WHERE username=?',(username,))
 def logout(self):self.current_user=None
 def require(self,permission):
  if not self.current_user or permission not in PERMISSIONS[self.current_user[2]]:raise PermissionError('Access denied: '+permission)
 def create_user(self,username,password,role):
  self.require('users');self._validate_password(password)
  if role!='cashier' or not username.strip():raise ValueError('Only one cashier account is permitted')
  if self.db.execute('SELECT COUNT(*) FROM app_users').fetchone()[0]>=2:raise ValueError('Maximum two accounts: administrator and cashier')
  salt=secrets.token_hex(16)
  with self.db:self.db.execute('INSERT INTO app_users(username,role,salt,hash) VALUES(?,?,?,?)',(username.strip(),role,salt,self._hash(password,salt)))
 def reset_cashier_password(self,username,new_password):
  self.require('users');self._validate_password(new_password)
  salt=secrets.token_hex(16)
  with self.db:
   cur=self.db.execute("UPDATE app_users SET salt=?,hash=? WHERE username=? AND role='cashier' AND active=1",(salt,self._hash(new_password,salt),username))
   if cur.rowcount!=1:raise ValueError('Active cashier not found')
   self.db.execute('DELETE FROM login_lockouts WHERE username=?',(username,))
 def change_own_password(self,old_password,new_password):
  if not self.current_user:raise PermissionError('Login required')
  self._validate_password(new_password)
  uid,username,_=self.current_user
  row=self.db.execute('SELECT salt,hash FROM app_users WHERE id=?',(uid,)).fetchone()
  if not row or not hmac.compare_digest(self._hash(old_password,row[0]),row[1]):raise PermissionError('Incorrect current password')
  salt=secrets.token_hex(16)
  with self.db:self.db.execute('UPDATE app_users SET salt=?,hash=? WHERE id=?',(salt,self._hash(new_password,salt),uid))
 def disable_user(self,username):
  self.require('users')
  if username==self.current_user[1]:raise ValueError('Cannot disable current user')
  with self.db:
   cur=self.db.execute('UPDATE app_users SET active=0 WHERE username=? AND role!=\'admin\'',(username,))
   if cur.rowcount!=1:raise ValueError('Unknown user or admin account')
 def list_users(self):
  self.require('users');return self.db.execute('SELECT username,role,active FROM app_users ORDER BY username').fetchall()
 def add_product(self,*args,**kwargs):
  self.require('products')
  return super().add_product(*args,**kwargs)
 def receive(self,*args,**kwargs):
  self.require('purchases')
  return super().receive(*args,**kwargs)
 def sale(self,*args,**kwargs):
  self.require('sales')
  return super().sale(*args,**kwargs)
 def supplier(self,*args,**kwargs):
  self.require('purchases')
  return super().supplier(*args,**kwargs)
 def purchase(self,*args,**kwargs):
  self.require('purchases')
  return super().purchase(*args,**kwargs)
 def pay_supplier(self,*args,**kwargs):
  self.require('finance')
  return super().pay_supplier(*args,**kwargs)
 def expense(self,*args,**kwargs):
  self.require('finance')
  return super().expense(*args,**kwargs)
 def open_cash(self,*args,**kwargs):
  self.require('finance')
  return super().open_cash(*args,**kwargs)
 def close_cash(self,*args,**kwargs):
  self.require('finance')
  return super().close_cash(*args,**kwargs)
 def return_full_sale(self,*args,**kwargs):
  self.require('returns')
  return super().return_full_sale(*args,**kwargs)
 def return_items(self,*args,**kwargs):
  self.require('returns')
  return super().return_items(*args,**kwargs)
 def adjust_stock(self,*args,**kwargs):
  self.require('inventory')
  return super().adjust_stock(*args,**kwargs)
 def receive_lot(self,*args,**kwargs):
  self.require('lots')
  return super().receive_lot(*args,**kwargs)
 def enable_lot_tracking(self,*args,**kwargs):
  self.require('lots')
  return super().enable_lot_tracking(*args,**kwargs)
 def quarantine_return(self,*args,**kwargs):
  self.require('returns')
  return super().quarantine_return(*args,**kwargs)
 def dispose_quarantine(self,*args,**kwargs):
  self.require('returns')
  return super().dispose_quarantine(*args,**kwargs)
 def backup(self,*args,**kwargs):
  self.require('backup')
  return super().backup(*args,**kwargs)
