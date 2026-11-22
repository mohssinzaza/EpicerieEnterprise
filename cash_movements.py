"""Read-only, session-scoped cash movement register, centimes; not a general ledger."""
import csv
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from cash_audit import snapshot
from cash_reconciliation import inspect

@dataclass(frozen=True)
class Movement:
    source: str
    reference: int
    occurred_at: str
    amount_cents: int

def movements(store):
    store.require('finance')
    db=store.db
    current=snapshot(store)
    start=db.execute('SELECT opened_at FROM cash_sessions WHERE id=?',(current.session_id,)).fetchone()[0]
    items=[Movement('opening',current.session_id,start,current.opening_cents)]
    sources=(
      ('cash_sale', '''SELECT s.id,s.created_at,s.total_cents FROM sales s LEFT JOIN customer_invoices i ON i.sale_id=s.id WHERE i.id IS NULL AND s.created_at>=?''',1),
      ('customer_cash', "SELECT id,created_at,amount_cents FROM customer_payments WHERE method='cash' AND state='collected' AND created_at>=?",1),
      ('supplier_cash', "SELECT id,settled_at,amount_cents FROM supplier_settlements WHERE method='cash' AND state='collected' AND settled_at>=?",-1),
      ('purchase_initial_cash', "SELECT id,created_at,paid_cents FROM purchases WHERE created_at>=? AND initial_payment_method='cash' AND paid_cents>0",-1),
      ('expense', "SELECT id,created_at,amount_cents FROM expenses WHERE created_at>=? AND payment_method IN ('cash','unknown')",-1),
      ('full_refund', "SELECT id,created_at,refund_cents FROM sale_returns WHERE created_at>=? AND refund_method IN ('cash','unknown')",-1),
      ('partial_refund', "SELECT id,created_at,refund_cents FROM partial_returns WHERE created_at>=? AND refund_method IN ('cash','unknown')",-1),
    )
    for name,query,sign in sources:
        items.extend(Movement(name,ident,when,sign*value) for ident,when,value in db.execute(query,(start,)))
    items.sort(key=lambda x:(x.occurred_at,x.source,x.reference))
    if sum(item.amount_cents for item in items)!=current.expected_cents:
        raise ValueError('Cash movements do not reconcile with snapshot')
    return tuple(items)

def export_movements_csv(store,destination):
    """Export a balanced running register without leaving partial CSV files.

    The temporary report is fully written before an atomic no-overwrite publish.
    """
    destination=Path(destination)
    if destination.suffix.lower()!='.csv':
        raise ValueError('CSV extension required')
    if destination.exists():
        raise FileExistsError('Refusing to overwrite cash report')
    entries=movements(store)
    readiness=inspect(store)
    if sum(entry.amount_cents for entry in entries)!=readiness.expected_cents:
        raise ValueError('Cash readiness and movement register disagree')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temp_path=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8-sig',newline='',
                dir=destination.parent,prefix='.cash-export-',suffix='.tmp',delete=False) as output:
            temp_path=Path(output.name)
            writer=csv.writer(output)
            writer.writerow(['Source / المصدر','Reference / المرجع','Date',
                             'Signed centimes / سنتيم','Running balance / الرصيد بالسنتيم'])
            running=0
            for item in entries:
                running+=item.amount_cents
                writer.writerow([item.source,item.reference,item.occurred_at,item.amount_cents,running])
            writer.writerow(['EXPECTED / المتوقع','','',readiness.expected_cents,running])
            writer.writerow(['READY / جاهز','','',str(readiness.ready_for_close),''])
            for warning in readiness.warnings:
                writer.writerow(['WARNING / تنبيه',warning,'','',''])
            writer.writerow(['NOTICE','Advisory cash register, not a complete accounting ledger','','',''])
            output.flush()
            os.fsync(output.fileno())
        # Hard-link publication is atomic and fails if another process created the target.
        os.link(temp_path,destination)
        return destination
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
