"""Read-only advisory cash reconciliation, in integer centimes."""
from dataclasses import dataclass

@dataclass(frozen=True)
class CashSnapshot:
    session_id:int
    opening_cents:int
    cash_sales_cents:int
    customer_cash_cents:int
    supplier_cash_cents:int
    expenses_cents:int
    refunds_cents:int
    expected_cents:int
    initial_purchase_cash_cents:int=0

def snapshot(store):
    store.require('finance')
    db=store.db
    row=db.execute('SELECT id,opened_at,opening_cents FROM cash_sessions WHERE closed_at IS NULL').fetchone()
    if row is None:raise ValueError('No open cash session')
    sid,start,opening=row
    def amount(query):return db.execute(query,(start,)).fetchone()[0]
    sales=amount("SELECT COALESCE(SUM(s.total_cents),0) FROM sales s LEFT JOIN customer_invoices i ON i.sale_id=s.id WHERE i.id IS NULL AND s.created_at>=?")
    customer=amount("SELECT COALESCE(SUM(amount_cents),0) FROM customer_payments WHERE method='cash' AND state='collected' AND created_at>=?")
    supplier=amount("SELECT COALESCE(SUM(amount_cents),0) FROM supplier_settlements WHERE method='cash' AND state='collected' AND settled_at>=?")
    initial_purchase_cash=amount("SELECT COALESCE(SUM(paid_cents),0) FROM purchases WHERE created_at>=? AND initial_payment_method='cash'")
    expenses=amount("SELECT COALESCE(SUM(amount_cents),0) FROM expenses WHERE created_at>=? AND payment_method IN ('cash','unknown')")
    refunds=amount("SELECT COALESCE(SUM(refund_cents),0) FROM sale_returns WHERE created_at>=? AND refund_method IN ('cash','unknown')")
    refunds+=amount("SELECT COALESCE(SUM(refund_cents),0) FROM partial_returns WHERE created_at>=? AND refund_method IN ('cash','unknown')")
    return CashSnapshot(sid,opening,sales,customer,supplier,expenses,refunds,opening+sales+customer-supplier-initial_purchase_cash-expenses-refunds,initial_purchase_cash)
