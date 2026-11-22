"""Supplier payment register: issued cheques are not settled until cleared."""
import datetime, json
from credit import CreditStore
from engine import cents, stamp

class CommercialStore(CreditStore):
 def __init__(self,path):
  super().__init__(path)
  self.db.executescript("""
  CREATE TABLE IF NOT EXISTS supplier_settlements(
   id INTEGER PRIMARY KEY,request_key TEXT NOT NULL UNIQUE,
   purchase_id INTEGER NOT NULL REFERENCES purchases(id),
   amount_cents INTEGER NOT NULL CHECK(amount_cents>0),
   method TEXT NOT NULL CHECK(method IN ('cash','bank','cheque')),
   state TEXT NOT NULL CHECK(state IN ('pending','collected','rejected')),
   reference TEXT NOT NULL DEFAULT '',cheque_number TEXT,bank_name TEXT,due_date TEXT,
   created_at TEXT NOT NULL,settled_at TEXT);
  CREATE INDEX IF NOT EXISTS idx_supplier_settlements_purchase ON supplier_settlements(purchase_id);
  CREATE INDEX IF NOT EXISTS idx_supplier_settlements_due ON supplier_settlements(due_date);
  """)
 def supplier_balances(self):
  self.require('finance')
  return self.db.execute("""SELECT s.id,s.name,COALESCE(SUM(p.total_cents),0),COALESCE(SUM(p.paid_cents),0),COALESCE(SUM(p.total_cents-p.paid_cents),0) FROM suppliers s LEFT JOIN purchases p ON p.supplier_id=s.id GROUP BY s.id ORDER BY s.name""").fetchall()
 def supplier_statement(self,supplier_id):
  self.require('finance')
  purchases=self.db.execute('SELECT id,reference,created_at,total_cents,paid_cents FROM purchases WHERE supplier_id=? ORDER BY id',(supplier_id,)).fetchall()
  payments=self.db.execute("""SELECT x.id,x.purchase_id,x.amount_cents,x.method,x.state,x.reference,x.cheque_number,x.bank_name,x.due_date FROM supplier_settlements x JOIN purchases p ON p.id=x.purchase_id WHERE p.supplier_id=? ORDER BY x.id""",(supplier_id,)).fetchall()
  return purchases,payments
 def settle_supplier_invoice(self,key,purchase_id,amount,method='cash',reference='',cheque_number='',bank_name='',due_date=None):
  self.require('finance')
  if not key or method not in ('cash','bank','cheque'):raise ValueError('Invalid settlement')
  value=cents(amount)
  if value<=0:raise ValueError('Positive amount required')
  if method=='cheque':
   if not cheque_number.strip() or not bank_name.strip() or not due_date:raise ValueError('Cheque details required')
   datetime.date.fromisoformat(due_date)
  self.db.execute('BEGIN IMMEDIATE')
  try:
   old=self.db.execute('SELECT id,purchase_id,amount_cents,method FROM supplier_settlements WHERE request_key=?',(key,)).fetchone()
   if old:
    if old[1:]!=(purchase_id,value,method):raise ValueError('Idempotency key conflict')
    self.db.execute('COMMIT');return old[0]
   row=self.db.execute('SELECT total_cents,paid_cents FROM purchases WHERE id=?',(purchase_id,)).fetchone()
   if not row:raise ValueError('Unknown purchase')
   pending=self.db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM supplier_settlements WHERE purchase_id=? AND state='pending'",(purchase_id,)).fetchone()[0]
   if value>row[0]-row[1]-pending:raise ValueError('Payment exceeds unallocated balance')
   state='pending' if method=='cheque' else 'collected'
   cur=self.db.execute("""INSERT INTO supplier_settlements(request_key,purchase_id,amount_cents,method,state,reference,cheque_number,bank_name,due_date,created_at,settled_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(key,purchase_id,value,method,state,reference,cheque_number if method=='cheque' else None,bank_name if method=='cheque' else None,due_date if method=='cheque' else None,stamp(),stamp() if state=='collected' else None))
   if state=='collected':self.db.execute('UPDATE purchases SET paid_cents=paid_cents+? WHERE id=?',(value,purchase_id))
   self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'supplier_settlement',str(cur.lastrowid),json.dumps({'method':method,'amount':value})))
   self.db.execute('COMMIT');return cur.lastrowid
  except BaseException:self.db.execute('ROLLBACK');raise
 def resolve_supplier_cheque(self,settlement_id,cleared):
  self.require('finance')
  self.db.execute('BEGIN IMMEDIATE')
  try:
   row=self.db.execute("SELECT purchase_id,amount_cents,state FROM supplier_settlements WHERE id=? AND method='cheque'",(settlement_id,)).fetchone()
   if not row or row[2]!='pending':raise ValueError('Cheque not pending')
   state='collected' if cleared else 'rejected'
   self.db.execute('UPDATE supplier_settlements SET state=?,settled_at=? WHERE id=?',(state,stamp(),settlement_id))
   if cleared:self.db.execute('UPDATE purchases SET paid_cents=paid_cents+? WHERE id=?',(row[1],row[0]))
   self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'supplier_cheque_'+state,str(settlement_id),'{}'))
   self.db.execute('COMMIT')
  except BaseException:self.db.execute('ROLLBACK');raise
