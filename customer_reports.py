"""Customer ledger and cheque maturity reporting; all amounts in integer centimes."""
import csv,datetime
from pathlib import Path

class CustomerReports:
 def __init__(self,store):self.store=store
 def statement(self,customer_id):
  self.store.require('finance')
  if not self.store.db.execute('SELECT 1 FROM customers WHERE id=?',(customer_id,)).fetchone():raise ValueError('Unknown customer')
  rows=self.store.db.execute("""SELECT i.id,i.created_at,i.due_date,i.total_cents,i.paid_cents,
   (SELECT COALESCE(SUM(p.amount_cents),0) FROM customer_payments p WHERE p.invoice_id=i.id AND p.state='pending')
   FROM customer_invoices i WHERE i.customer_id=? ORDER BY i.created_at,i.id""",(customer_id,)).fetchall()
  return [{'invoice_id':r[0],'date':r[1],'due_date':r[2] or '', 'total_cents':r[3], 'collected_cents':r[4], 'pending_cheques_cents':r[5], 'unpaid_cents':r[3]-r[4]} for r in rows]
 def aging(self,as_of=None):
  self.store.require('finance')
  today=datetime.date.fromisoformat(as_of) if as_of else datetime.date.today()
  result=[]
  for invoice,client,due,total,paid in self.store.db.execute("""SELECT i.id,c.name,i.due_date,i.total_cents,i.paid_cents FROM customer_invoices i JOIN customers c ON c.id=i.customer_id WHERE i.total_cents>i.paid_cents ORDER BY i.id"""):
   days=max(0,(today-datetime.date.fromisoformat(due)).days) if due else 0
   result.append((invoice,client,due or '',total-paid,days,'overdue' if due and days>0 else 'open'))
  return result
 def cheques_due(self,as_of=None):
  self.store.require('finance')
  day=as_of or datetime.date.today().isoformat();datetime.date.fromisoformat(day)
  return self.store.db.execute("""SELECT p.id,c.cheque_number,c.bank_name,c.due_date,p.amount_cents
    FROM cheques c JOIN customer_payments p ON p.id=c.payment_id
    WHERE p.state='pending' AND c.due_date<=? ORDER BY c.due_date,p.id""",(day,)).fetchall()
 def export_statement(self,customer_id,path):
  rows=self.statement(customer_id)
  path=Path(path)
  with path.open('w',newline='',encoding='utf-8-sig') as out:
   writer=csv.writer(out,delimiter=';');writer.writerow(['invoice_id','date','due_date','total_cents','collected_cents','pending_cheques_cents','unpaid_cents'])
   for r in rows:writer.writerow(list(r.values()))
  return len(rows)
