"""V6 extensions: supplier invoices, expenses, cash sessions, full sale returns."""
import json
from engine import Store,stamp,cents

class EnterpriseStore(Store):
 def __init__(self,path):
  super().__init__(path)
  self.db.executescript('''
  CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,phone TEXT DEFAULT '');
  CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY,reference TEXT NOT NULL UNIQUE,supplier_id INTEGER NOT NULL REFERENCES suppliers(id),created_at TEXT NOT NULL,total_cents INTEGER NOT NULL CHECK(total_cents>=0),paid_cents INTEGER NOT NULL CHECK(paid_cents>=0 AND paid_cents<=total_cents));
  CREATE TABLE IF NOT EXISTS purchase_lines(id INTEGER PRIMARY KEY,purchase_id INTEGER NOT NULL REFERENCES purchases(id),product_id INTEGER NOT NULL REFERENCES products(id),quantity INTEGER NOT NULL CHECK(quantity>0),unit_cost_cents INTEGER NOT NULL CHECK(unit_cost_cents>=0));
  CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,category TEXT NOT NULL,description TEXT NOT NULL,amount_cents INTEGER NOT NULL CHECK(amount_cents>0));
  CREATE TABLE IF NOT EXISTS cash_sessions(id INTEGER PRIMARY KEY,opened_at TEXT NOT NULL,opening_cents INTEGER NOT NULL,closed_at TEXT,expected_cents INTEGER,actual_cents INTEGER,variance_cents INTEGER);
  CREATE UNIQUE INDEX IF NOT EXISTS one_open_cash_session ON cash_sessions((1)) WHERE closed_at IS NULL;
  CREATE TABLE IF NOT EXISTS sale_returns(id INTEGER PRIMARY KEY,sale_id INTEGER NOT NULL UNIQUE REFERENCES sales(id),created_at TEXT NOT NULL,refund_cents INTEGER NOT NULL);
  ''')
  # Existing databases get an explicit payment method without losing legacy rows.
  cols={row[1] for row in self.db.execute('PRAGMA table_info(expenses)')}
  if 'payment_method' not in cols:
   self.db.execute("ALTER TABLE expenses ADD COLUMN payment_method TEXT NOT NULL DEFAULT 'unknown'")
  purchase_cols={row[1] for row in self.db.execute('PRAGMA table_info(purchases)')}
  if 'initial_payment_method' not in purchase_cols:
   self.db.execute("ALTER TABLE purchases ADD COLUMN initial_payment_method TEXT NOT NULL DEFAULT 'unknown'")
  return_cols={row[1] for row in self.db.execute('PRAGMA table_info(sale_returns)')}
  if 'refund_method' not in return_cols:
   self.db.execute("ALTER TABLE sale_returns ADD COLUMN refund_method TEXT NOT NULL DEFAULT 'unknown'")
 def supplier(self,name,phone=''):
  if not name.strip():raise ValueError('Supplier name required')
  with self.db:return self.db.execute('INSERT INTO suppliers(name,phone) VALUES(?,?)',(name.strip(),phone.strip())).lastrowid
 def purchase(self,reference,supplier_id,lines,paid='0',payment_method='unknown'):
  if not reference.strip() or not lines:raise ValueError('Reference and lines required')
  paid_amount=cents(paid)
  if payment_method not in ('unknown','cash','bank','cheque'):
   raise ValueError('Invalid purchase payment method')
  if paid_amount>0 and payment_method=='unknown':
   # Legacy callers remain supported, but cash close will require reconciliation.
   pass
  self.db.execute('BEGIN IMMEDIATE')
  try:
   if self.db.execute('SELECT 1 FROM purchases WHERE reference=?',(reference,)).fetchone():raise ValueError('Duplicate invoice reference')
   if not self.db.execute('SELECT 1 FROM suppliers WHERE id=?',(supplier_id,)).fetchone():raise ValueError('Unknown supplier')
   grouped={}
   for barcode,qty,unit_cost in lines:
    if type(qty)!=int or qty<=0:raise ValueError('Invalid quantity')
    unit=cents(unit_cost)
    if barcode in grouped and grouped[barcode][1]!=unit:raise ValueError('Conflicting unit costs')
    prev=grouped.get(barcode,(0,unit))[0];grouped[barcode]=(prev+qty,unit)
   prepared=[];total=0
   for barcode,(qty,unit) in grouped.items():
    p=self.db.execute('SELECT id FROM products WHERE barcode=?',(barcode,)).fetchone()
    if not p:raise ValueError('Unknown barcode '+barcode)
    prepared.append((p[0],qty,unit));total+=qty*unit
   if paid_amount>total:raise ValueError('Paid amount exceeds invoice')
   cur=self.db.execute('INSERT INTO purchases(reference,supplier_id,created_at,total_cents,paid_cents,initial_payment_method) VALUES(?,?,?,?,?,?)',(reference,supplier_id,stamp(),total,paid_amount,payment_method));pid=cur.lastrowid
   for product_id,qty,unit in prepared:
    self.db.execute('INSERT INTO purchase_lines(purchase_id,product_id,quantity,unit_cost_cents) VALUES(?,?,?,?)',(pid,product_id,qty,unit))
    self.db.execute('UPDATE products SET stock=stock+?,cost_cents=? WHERE id=?',(qty,unit,product_id))
    self.db.execute('INSERT INTO stock_ledger(created_at,product_id,delta,reason,reference) VALUES(?,?,?,?,?)',(stamp(),product_id,qty,'purchase',str(pid)))
   self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'purchase',str(pid),json.dumps({'total_cents':total})))
   self.db.execute('COMMIT');return pid,total
  except BaseException:self.db.execute('ROLLBACK');raise
 def pay_supplier(self,purchase_id,amount):
  amount=cents(amount)
  if amount<=0:raise ValueError('Payment must be positive')
  self.db.execute('BEGIN IMMEDIATE')
  try:
   row=self.db.execute('SELECT total_cents,paid_cents FROM purchases WHERE id=?',(purchase_id,)).fetchone()
   if not row or amount>row[0]-row[1]:raise ValueError('Payment exceeds outstanding balance')
   self.db.execute('UPDATE purchases SET paid_cents=paid_cents+? WHERE id=?',(amount,purchase_id))
   self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'supplier_payment',str(purchase_id),json.dumps({'amount_cents':amount})))
   self.db.execute('COMMIT')
  except BaseException:self.db.execute('ROLLBACK');raise
 def expense(self,category,description,amount,payment_method='unknown'):
  amount=cents(amount)
  if amount<=0 or not category.strip():raise ValueError('Invalid expense')
  if payment_method not in ('unknown','cash','bank','cheque'):
   raise ValueError('Invalid expense payment method')
  with self.db:return self.db.execute('INSERT INTO expenses(created_at,category,description,amount_cents,payment_method) VALUES(?,?,?,?,?)',(stamp(),category.strip(),description.strip(),amount,payment_method)).lastrowid
 def open_cash(self,opening):
  amount=cents(opening)
  with self.db:return self.db.execute('INSERT INTO cash_sessions(opened_at,opening_cents) VALUES(?,?)',(stamp(),amount)).lastrowid
 def close_cash(self,actual):
  actual=cents(actual)
  self.db.execute('BEGIN IMMEDIATE')
  try:
   row=self.db.execute('SELECT id,opened_at,opening_cents FROM cash_sessions WHERE closed_at IS NULL').fetchone()
   if not row:raise ValueError('No open session')
   # Sales, refunds and expenses from session opening. Purchase payments are not yet cash-method attributed.
   sales=self.db.execute('SELECT COALESCE(SUM(total_cents),0) FROM sales WHERE created_at>=?',(row[1],)).fetchone()[0]
   refunds=self.db.execute('SELECT COALESCE(SUM(refund_cents),0) FROM sale_returns WHERE created_at>=?',(row[1],)).fetchone()[0]
   expenses=self.db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM expenses WHERE created_at>=?',(row[1],)).fetchone()[0]
   expected=row[2]+sales-refunds-expenses
   self.db.execute('UPDATE cash_sessions SET closed_at=?,expected_cents=?,actual_cents=?,variance_cents=? WHERE id=?',(stamp(),expected,actual,actual-expected,row[0]))
   self.db.execute('COMMIT');return expected,actual-expected
  except BaseException:self.db.execute('ROLLBACK');raise
 def return_full_sale(self,sale_id,refund_method='unknown'):
  if refund_method not in ('unknown','cash','bank','cheque'):
   raise ValueError('Invalid refund payment method')
  self.db.execute('BEGIN IMMEDIATE')
  try:
   sale=self.db.execute('SELECT total_cents FROM sales WHERE id=?',(sale_id,)).fetchone()
   if not sale:raise ValueError('Sale not found')
   if self.db.execute('SELECT 1 FROM sale_returns WHERE sale_id=?',(sale_id,)).fetchone():raise ValueError('Already returned')
   for product_id,qty in self.db.execute('SELECT product_id,quantity FROM sale_lines WHERE sale_id=?',(sale_id,)).fetchall():
    self.db.execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,product_id))
    self.db.execute('INSERT INTO stock_ledger(created_at,product_id,delta,reason,reference) VALUES(?,?,?,?,?)',(stamp(),product_id,qty,'sale_return',str(sale_id)))
   self.db.execute('INSERT INTO sale_returns(sale_id,created_at,refund_cents,refund_method) VALUES(?,?,?,?)',(sale_id,stamp(),sale[0],refund_method))
   self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'sale_return',str(sale_id),json.dumps({'refund_cents':sale[0]})))
   self.db.execute('COMMIT');return sale[0]
  except BaseException:self.db.execute('ROLLBACK');raise
