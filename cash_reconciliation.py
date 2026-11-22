"""Read-only cash close readiness checks. Never silently certify a legacy session."""
from dataclasses import dataclass
from cash_audit import snapshot

@dataclass(frozen=True)
class CashReadiness:
    session_id: int
    expected_cents: int
    warnings: tuple
    ready_for_close: bool

def inspect(store):
    store.require('finance')
    current = snapshot(store)
    db = store.db
    start = db.execute('SELECT opened_at FROM cash_sessions WHERE id=?',(current.session_id,)).fetchone()[0]
    warnings=[]
    def count(sql):
        return db.execute(sql,(start,)).fetchone()[0]
    # Do not certify cash totals if historical sale headers and their lines disagree.
    # Parameterized by session start; all amounts remain integer centimes.
    mismatches = count("""SELECT COUNT(*) FROM sales s
        LEFT JOIN (SELECT sale_id, SUM(quantity * unit_price_cents) AS line_total,
                          COUNT(*) AS line_count FROM sale_lines GROUP BY sale_id) l
        ON l.sale_id=s.id
        WHERE s.created_at>=? AND (COALESCE(l.line_count,0)=0
          OR COALESCE(l.line_total,0)<>s.total_cents)""")
    if mismatches:
        warnings.append(f'{mismatches} sale(s) have missing lines or totals inconsistent with line items; reconcile before closing')
    # A zero/negative quantity or price can make a numerically balanced invoice
    # look valid while silently corrupting inventory and profit reporting.
    invalid_lines = count("""SELECT COUNT(*) FROM sale_lines l JOIN sales s ON s.id=l.sale_id
        WHERE s.created_at>=? AND (l.quantity<=0 OR l.unit_price_cents<0
          OR l.unit_cost_cents<0)""")
    if invalid_lines:
        warnings.append(f'{invalid_lines} sale line(s) contain invalid quantity, price or cost; reconcile before closing')
    # Imported/orphaned sale lines are not included in any invoice total.
    orphan_lines = db.execute("""SELECT COUNT(*) FROM sale_lines l
        LEFT JOIN sales s ON s.id=l.sale_id WHERE s.id IS NULL""").fetchone()[0]
    if orphan_lines:
        warnings.append(f'{orphan_lines} orphan sale line(s) are not attached to an invoice; reconcile before closing')
    # Validate partial-return line ownership and cumulative returned quantities.
    # A refund line must refer to a sale line on its own invoice; repeated returns
    # must never exceed the original sold quantity, even across several refunds.
    invalid_return_links = count("""SELECT COUNT(*) FROM partial_return_lines rl
        JOIN partial_returns r ON r.id=rl.return_id
        LEFT JOIN sale_lines sl ON sl.id=rl.sale_line_id
        WHERE r.created_at>=? AND (sl.id IS NULL OR sl.sale_id<>r.sale_id
          OR rl.quantity<=0)""")
    if invalid_return_links:
        warnings.append(f'{invalid_return_links} partial return line(s) have invalid sale ownership or quantity; reconcile before closing')
    over_returned = count("""SELECT COUNT(*) FROM (
        SELECT sl.id FROM sale_lines sl
        JOIN partial_return_lines rl ON rl.sale_line_id=sl.id
        JOIN partial_returns r ON r.id=rl.return_id
        GROUP BY sl.id HAVING SUM(rl.quantity)>MAX(sl.quantity)
        ) excessive
        WHERE EXISTS (
            SELECT 1 FROM partial_return_lines recent_rl
            JOIN partial_returns recent_r ON recent_r.id=recent_rl.return_id
            WHERE recent_rl.sale_line_id=excessive.id AND recent_r.created_at>=?
        )""")
    if over_returned:
        warnings.append(f'{over_returned} sale line(s) have returned quantities exceeding units sold; reconcile before closing')
    missing_return_lines = count("""SELECT COUNT(*) FROM partial_returns r
        WHERE r.created_at>=? AND NOT EXISTS (SELECT 1 FROM partial_return_lines rl WHERE rl.return_id=r.id)""")
    if missing_return_lines:
        warnings.append(f'{missing_return_lines} partial return(s) have no item lines; reconcile before closing')
    # Refund value must match returned sale-line quantities at the original
    # unit prices. A mismatch can distort cash and profit even when quantities
    # remain within the originally sold amounts.
    mismatched_partial_values = count("""SELECT COUNT(*) FROM partial_returns r
        LEFT JOIN (
            SELECT rl.return_id, SUM(rl.quantity * sl.unit_price_cents) AS value_cents,
                   COUNT(*) AS linked_count
            FROM partial_return_lines rl
            JOIN sale_lines sl ON sl.id=rl.sale_line_id
            GROUP BY rl.return_id
        ) detail ON detail.return_id=r.id
        WHERE r.created_at>=? AND detail.linked_count>0
          AND detail.value_cents<>r.refund_cents""")
    if mismatched_partial_values:
        warnings.append(f'{mismatched_partial_values} partial refund(s) do not match returned item values; reconcile before closing')
    # Verify the payment header separately from line-item accounting. A cash sale
    # must not have negative tender/change or a tender-minus-change discrepancy.
    payment_errors = count("""SELECT COUNT(*) FROM sales s
        LEFT JOIN customer_invoices i ON i.sale_id=s.id
        WHERE s.created_at>=? AND i.id IS NULL AND
        (s.total_cents<0 OR s.received_cents<0 OR s.change_cents<0
         OR s.received_cents-s.change_cents<>s.total_cents)""")
    if payment_errors:
        warnings.append(f'{payment_errors} cash sale(s) have inconsistent received/change amounts; reconcile before closing')
    # Refunds larger than the original invoice indicate corrupt/duplicated data.
    excessive_refunds = count("""SELECT COUNT(*) FROM sales s
        WHERE (s.created_at>=?1 OR EXISTS (SELECT 1 FROM sale_returns recent_r WHERE recent_r.sale_id=s.id AND recent_r.created_at>=?1)
          OR EXISTS (SELECT 1 FROM partial_returns recent_p WHERE recent_p.sale_id=s.id AND recent_p.created_at>=?1)) AND
        (COALESCE((SELECT SUM(r.refund_cents) FROM sale_returns r WHERE r.sale_id=s.id),0)
        +COALESCE((SELECT SUM(p.refund_cents) FROM partial_returns p WHERE p.sale_id=s.id),0))>s.total_cents""")
    if excessive_refunds:
        warnings.append(f'{excessive_refunds} sale(s) have refunds exceeding the original total; reconcile before closing')
    # Purchase headers must reconcile to their inventory lines. A balanced cash
    # drawer alone cannot certify a malformed supplier invoice.
    purchase_mismatches = count("""SELECT COUNT(*) FROM purchases p LEFT JOIN
        (SELECT purchase_id, COUNT(*) AS n, SUM(quantity*unit_cost_cents) AS total
         FROM purchase_lines GROUP BY purchase_id) l ON l.purchase_id=p.id
        WHERE p.created_at>=? AND (COALESCE(l.n,0)=0
          OR COALESCE(l.total,0)<>p.total_cents)""")
    if purchase_mismatches:
        warnings.append(f'{purchase_mismatches} purchase invoice(s) have missing lines or incorrect totals')
    invalid_purchase_lines = count("""SELECT COUNT(*) FROM purchase_lines l
        JOIN purchases p ON p.id=l.purchase_id WHERE p.created_at>=?
        AND (l.quantity<=0 OR l.unit_cost_cents<0)""")
    if invalid_purchase_lines:
        warnings.append(f'{invalid_purchase_lines} purchase line(s) have invalid quantity or cost')
    orphan_purchase_lines = db.execute("""SELECT COUNT(*) FROM purchase_lines l
        LEFT JOIN purchases p ON p.id=l.purchase_id WHERE p.id IS NULL""").fetchone()[0]
    if orphan_purchase_lines:
        warnings.append(f'{orphan_purchase_lines} orphan purchase line(s) need review')
    invalid_purchase_payments = count("""SELECT COUNT(*) FROM purchases
        WHERE created_at>=? AND (paid_cents<0 OR paid_cents>total_cents
        OR initial_payment_method NOT IN ('unknown','cash','bank','cheque'))""")
    if invalid_purchase_payments:
        warnings.append(f'{invalid_purchase_payments} purchase invoice(s) have invalid initial payment data')
    # Legacy records may have no settlement timestamp. Such payments are omitted
    # from the session snapshot, even if marked collected: never certify closure.
    undated_supplier = count("""SELECT COUNT(*) FROM supplier_settlements
        WHERE created_at>=? AND method='cash' AND state='collected'
          AND settled_at IS NULL""")
    if undated_supplier:
        warnings.append(f'{undated_supplier} collected supplier cash payment(s) lack settlement timestamps; reconcile before closing')
    # Expenses have no payment-method field in the current schema. The snapshot
    # assumes cash, which cannot be independently verified.
    unattributed_expenses = count("SELECT COUNT(*) FROM expenses WHERE created_at>=? AND payment_method='unknown'")
    if unattributed_expenses:
        warnings.append(f'{unattributed_expenses} expense(s) lack verified payment method; cash is assumed')
    invalid_methods = count("SELECT COUNT(*) FROM expenses WHERE created_at>=? AND payment_method NOT IN ('unknown','cash','bank','cheque')")
    if invalid_methods:
        warnings.append(f'{invalid_methods} expense(s) have invalid payment method')
    opening = db.execute('SELECT opening_cents FROM cash_sessions WHERE id=?',(current.session_id,)).fetchone()[0]
    if opening < 0:
        warnings.append('Cash session opening balance is negative; reconcile before closing')
    # Protect the cash close against malformed historical rows, including
    # non-cash entries that would otherwise be invisible to the cash snapshot.
    if db.execute("SELECT COUNT(*) FROM cash_sessions WHERE closed_at IS NULL").fetchone()[0] != 1:
        warnings.append('Multiple open cash sessions detected; reconcile before closing')
    if count("SELECT COUNT(*) FROM expenses WHERE created_at>=? AND amount_cents<=0"):
        warnings.append('Expenses with zero or negative amounts require review')
    if count("SELECT COUNT(*) FROM sale_returns WHERE created_at>=? AND (refund_cents<=0 OR refund_method NOT IN ('unknown','cash','bank','cheque'))"):
        warnings.append('Full refunds contain invalid amounts or payment methods')
    if count("SELECT COUNT(*) FROM partial_returns WHERE created_at>=? AND refund_cents<=0"):
        warnings.append('Partial refunds contain zero or negative amounts')
    # Snapshot sums only collected cash. Invalid legacy payment states or amounts
    # must not silently disappear from the reconciliation.
    invalid_customer_cash = count("""SELECT COUNT(*) FROM customer_payments
        WHERE created_at>=? AND method='cash'
          AND (state<>'collected' OR amount_cents<=0)""")
    if invalid_customer_cash:
        warnings.append(f'{invalid_customer_cash} customer cash payment(s) have invalid state or amount; reconcile before closing')
    invalid_supplier_cash = count("""SELECT COUNT(*) FROM supplier_settlements
        WHERE COALESCE(settled_at,created_at)>=? AND method='cash'
          AND (state<>'collected' OR amount_cents<=0)""")
    if invalid_supplier_cash:
        warnings.append(f'{invalid_supplier_cash} supplier cash payment(s) have invalid state or amount; reconcile before closing')
    invalid_expenses = count("SELECT COUNT(*) FROM expenses WHERE created_at>=? AND payment_method='unknown' AND amount_cents<0")
    if invalid_expenses:
        warnings.append(f'{invalid_expenses} expense(s) have negative amounts; reconcile before closing')
    if count("SELECT COUNT(*) FROM purchases WHERE paid_cents>0 AND initial_payment_method='unknown' AND created_at>=?"):
        warnings.append('Purchase invoice initial payments lack verified cash/bank method; reconcile manually')
    if count("SELECT COUNT(*) FROM audit WHERE action='supplier_payment' AND created_at>=?"):
        warnings.append('Legacy supplier payments lack verified payment method; reconcile manually')
    if count("SELECT COUNT(*) FROM sale_returns WHERE created_at>=? AND refund_method='unknown'"):
        warnings.append('Full returns lack verified refund method; cash refund is assumed')
    if count("SELECT COUNT(*) FROM partial_returns WHERE created_at>=? AND refund_method='unknown'"):
        warnings.append('Partial returns lack verified refund method; cash refund is assumed')
    if count("SELECT COUNT(*) FROM partial_returns WHERE created_at>=? AND refund_method NOT IN ('unknown','cash','bank','cheque')"):
        warnings.append('Partial returns contain invalid refund methods')
    if count("SELECT COUNT(*) FROM customer_payments WHERE method='cheque' AND state='pending' AND created_at>=?"):
        warnings.append('Pending customer cheques are not cash; confirm bank collection separately')
    if count("SELECT COUNT(*) FROM supplier_settlements WHERE method='cheque' AND state='pending' AND settled_at>=?"):
        warnings.append('Pending supplier cheques are not cash; confirm bank debit separately')
    return CashReadiness(current.session_id,current.expected_cents,tuple(warnings),not warnings)
