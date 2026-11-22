"""V14: customer accounts, credit sales and cheque collection. All money integer cents."""
import datetime, json
from engine import cents, stamp
from pricing import PricingStore, TIERS

class CreditStore(PricingStore):
 def __init__(self,path):
  super().__init__(path)
  self.db.executescript("""
  CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,phone TEXT DEFAULT '',credit_limit_cents INTEGER NOT NULL DEFAULT 0 CHECK(credit_limit_cents>=0));
  CREATE TABLE IF NOT EXISTS customer_invoices(id INTEGER PRIMARY KEY,sale_id INTEGER NOT NULL UNIQUE REFERENCES sales(id),customer_id INTEGER NOT NULL REFERENCES customers(id),total_cents INTEGER NOT NULL CHECK(total_cents>=0),paid_cents INTEGER NOT NULL DEFAULT 0 CHECK(paid_cents>=0),created_at TEXT NOT NULL,due_date TEXT);
  CREATE TABLE IF NOT EXISTS customer_payments(id INTEGER PRIMARY KEY,request_key TEXT NOT NULL UNIQUE,invoice_id INTEGER NOT NULL REFERENCES customer_invoices(id),amount_cents INTEGER NOT NULL CHECK(amount_cents>0),method TEXT NOT NULL CHECK(method IN ('cash','bank','cheque')),created_at TEXT NOT NULL,reference TEXT NOT NULL DEFAULT '',state TEXT NOT NULL CHECK(state IN ('collected','pending','rejected')));
  CREATE TABLE IF NOT EXISTS cheques(id INTEGER PRIMARY KEY,payment_id INTEGER NOT NULL UNIQUE REFERENCES customer_payments(id),cheque_number TEXT NOT NULL,bank_name TEXT NOT NULL,due_date TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '');
  CREATE INDEX IF NOT EXISTS idx_invoices_customer ON customer_invoices(customer_id);
  CREATE INDEX IF NOT EXISTS idx_cheques_due ON cheques(due_date);
  """)
 def add_customer(self,name,phone='',limit='0'):
  self.require('finance')
  if not name.strip():raise ValueError('Customer name required')
  with self.db:return self.db.execute('INSERT INTO customers(name,phone,credit_limit_cents) VALUES(?,?,?)',(name.strip(),phone.strip(),cents(limit))).lastrowid
 def customers(self):
  self.require('finance')
  return self.db.execute('SELECT id,name,phone,credit_limit_cents FROM customers ORDER BY name').fetchall()
 def outstanding(self,customer_id):
  return self.db.execute('SELECT COALESCE(SUM(total_cents-paid_cents),0) FROM customer_invoices WHERE customer_id=?',(customer_id,)).fetchone()[0]
 def credit_sale(self,key,customer_id,lines,deposit='0',due_date=None):
  """Atomic sale + receivable + cash deposit. lines: barcode,count,unit,tier."""
  self.require('sales')
  if not key or not lines:raise ValueError('Sale key and lines required')
  deposit_cents=cents(deposit)
  if due_date:datetime.date.fromisoformat(due_date)
  self.db.execute('BEGIN IMMEDIATE')
  try:
   prior=self.db.execute('SELECT id,total_cents FROM sales WHERE request_key=?',(key,)).fetchone()
   if prior:
    invoice=self.db.execute('SELECT id FROM customer_invoices WHERE sale_id=?',(prior[0],)).fetchone()
    if not invoice:raise ValueError('Key already used for non-credit sale')
    self.db.execute('COMMIT');return invoice[0],prior[0],prior[1]
   customer=self.db.execute('SELECT credit_limit_cents FROM customers WHERE id=?',(customer_id,)).fetchone()
   if not customer:raise ValueError('Unknown customer')
   prepared=[];requested={};total=0
   for barcode,count,unit,tier in lines:
    if tier not in TIERS or type(count)!=int or count<=0:raise ValueError('Invalid line')
    p=self.db.execute('SELECT id,price_cents,cost_cents,stock FROM products WHERE barcode=?',(barcode,)).fetchone()
    if not p:raise ValueError('Unknown barcode')
    if unit=='piece':factor=1
    else:
     row=self.db.execute('SELECT units_per_pack FROM product_units WHERE product_id=? AND unit_name=?',(p[0],unit)).fetchone()
     if not row:raise ValueError('Unknown unit')
     factor=row[0]
    qty=count*factor
    tier_row=self.db.execute('SELECT price_cents,min_qty FROM product_tiers WHERE product_id=? AND tier=?',(p[0],tier)).fetchone()
    if tier!='detail' and not tier_row:raise ValueError('Tier not configured')
    unit_price,minimum=tier_row if tier_row else (p[1],1)
    if qty<minimum:raise ValueError('Tier minimum not met')
    requested[p[0]]=requested.get(p[0],0)+qty
    prepared.append((p,qty,count,unit,tier,unit_price));total+=qty*unit_price
   if deposit_cents>total:raise ValueError('Deposit exceeds total')
   due=total-deposit_cents
   if customer[0]>0 and self.outstanding(customer_id)+due>customer[0]:raise ValueError('Customer credit limit exceeded')
   today=datetime.date.today().isoformat();allocations={}
   for pid,qty in requested.items():
    stock=self.db.execute('SELECT stock FROM products WHERE id=?',(pid,)).fetchone()[0]
    if stock<qty:raise ValueError('Insufficient stock')
    if not self.db.execute('SELECT 1 FROM tracked_products WHERE product_id=?',(pid,)).fetchone():continue
    remain=qty;allocations[pid]=[]
    for lot_id,available in self.db.execute('SELECT l.id,b.remaining_qty FROM expiry_lots l JOIN lot_balances b ON b.lot_id=l.id WHERE l.product_id=? AND l.expiry_date>=? AND b.remaining_qty>0 ORDER BY l.expiry_date,l.id',(pid,today)):
     take=min(remain,available)
     if take:allocations[pid].append((lot_id,take));remain-=take
     if remain==0:break
    if remain:raise ValueError('Insufficient non-expired stock')
   sid=self.db.execute('INSERT INTO sales(request_key,created_at,total_cents,received_cents,change_cents) VALUES(?,?,?,?,0)',(key,stamp(),total,deposit_cents)).lastrowid
   for p,qty,count,unit,tier,price in prepared:
    self.db.execute('UPDATE products SET stock=stock-? WHERE id=?',(qty,p[0]))
    lid=self.db.execute('INSERT INTO sale_lines(sale_id,product_id,quantity,unit_price_cents,unit_cost_cents) VALUES(?,?,?,?,?)',(sid,p[0],qty,price,p[2])).lastrowid
    self.db.execute('INSERT INTO sale_tier_info VALUES(?,?,?,?)',(lid,tier,unit,count))
    for lotid,take in allocations.get(p[0],[]):
     self.db.execute('UPDATE lot_balances SET remaining_qty=remaining_qty-? WHERE lot_id=?',(take,lotid))
     self.db.execute('INSERT INTO sale_lot_allocations(sale_line_id,lot_id,quantity) VALUES(?,?,?)',(lid,lotid,take))
    self.db.execute('INSERT INTO stock_ledger(created_at,product_id,delta,reason,reference) VALUES(?,?,?,?,?)',(stamp(),p[0],-qty,'credit_sale',str(sid)))
   iid=self.db.execute('INSERT INTO customer_invoices(sale_id,customer_id,total_cents,paid_cents,created_at,due_date) VALUES(?,?,?,?,?,?)',(sid,customer_id,total,deposit_cents,stamp(),due_date)).lastrowid
   if deposit_cents:self.db.execute('INSERT INTO customer_payments(request_key,invoice_id,amount_cents,method,created_at,reference,state) VALUES(?,?,?,?,?,?,?)',(key+':deposit',iid,deposit_cents,'cash',stamp(),'initial deposit','collected'))
   self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'credit_sale',str(iid),json.dumps({'customer':customer_id,'total':total,'deposit':deposit_cents})))
   self.db.execute('COMMIT');return iid,sid,total
  except BaseException:self.db.execute('ROLLBACK');raise
 def receive_payment(self,key,invoice_id,amount,method='cash',reference='',cheque_number='',bank_name='',due_date=None):
  self.require('finance')
  if not key or method not in ('cash','bank','cheque'):raise ValueError('Invalid payment')
  value=cents(amount)
  if value<=0:raise ValueError('Positive amount required')
  if method=='cheque':
   if not cheque_number.strip() or not bank_name.strip() or not due_date:raise ValueError('Cheque details required')
   datetime.date.fromisoformat(due_date)
  self.db.execute('BEGIN IMMEDIATE')
  try:
   old=self.db.execute('SELECT id FROM customer_payments WHERE request_key=?',(key,)).fetchone()
   if old:self.db.execute('COMMIT');return old[0]
   row=self.db.execute('SELECT total_cents,paid_cents FROM customer_invoices WHERE id=?',(invoice_id,)).fetchone()
   if not row:raise ValueError('Unknown invoice')
   pending=self.db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM customer_payments WHERE invoice_id=? AND state='pending'",(invoice_id,)).fetchone()[0]
   if value>row[0]-row[1]-pending:raise ValueError('Amount exceeds unpaid balance')
   state='pending' if method=='cheque' else 'collected'
   pid=self.db.execute('INSERT INTO customer_payments(request_key,invoice_id,amount_cents,method,created_at,reference,state) VALUES(?,?,?,?,?,?,?)',(key,invoice_id,value,method,stamp(),reference,state)).lastrowid
   if method=='cheque':self.db.execute('INSERT INTO cheques(payment_id,cheque_number,bank_name,due_date) VALUES(?,?,?,?)',(pid,cheque_number.strip(),bank_name.strip(),due_date))
   else:self.db.execute('UPDATE customer_invoices SET paid_cents=paid_cents+? WHERE id=?',(value,invoice_id))
   self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'customer_payment',str(pid),json.dumps({'method':method,'amount':value})))
   self.db.execute('COMMIT');return pid
  except BaseException:self.db.execute('ROLLBACK');raise
 def settle_cheque(self,payment_id,collected):
  self.require('finance')
  self.db.execute('BEGIN IMMEDIATE')
  try:
   row=self.db.execute("SELECT invoice_id,amount_cents,state FROM customer_payments WHERE id=? AND method='cheque'",(payment_id,)).fetchone()
   if not row or row[2]!='pending':raise ValueError('Cheque not pending')
   state='collected' if collected else 'rejected'
   self.db.execute('UPDATE customer_payments SET state=? WHERE id=?',(state,payment_id))
   if collected:self.db.execute('UPDATE customer_invoices SET paid_cents=paid_cents+? WHERE id=?',(row[1],row[0]))
   self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'cheque_'+state,str(payment_id),'{}'))
   self.db.execute('COMMIT')
  except BaseException:self.db.execute('ROLLBACK');raise
 def receivables(self):
  self.require('finance')
  return self.db.execute('SELECT i.id,c.name,i.total_cents,i.paid_cents,i.total_cents-i.paid_cents,i.due_date FROM customer_invoices i JOIN customers c ON c.id=i.customer_id ORDER BY i.id DESC').fetchall()
 def cheque_register(self):
  self.require('finance')
  return self.db.execute('SELECT p.id,c.cheque_number,c.bank_name,c.due_date,p.amount_cents,p.state FROM cheques c JOIN customer_payments p ON p.id=c.payment_id ORDER BY c.due_date').fetchall()
