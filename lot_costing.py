"""Explicit, immutable lot acquisition cost and read-only FEFO costing report.
Historical lots without an entered invoice cost are UNKNOWN, never estimated.
"""
from dataclasses import dataclass
from engine import cents, stamp

@dataclass(frozen=True)
class CostedAllocation:
    sale_line_id:int
    lot_id:int
    quantity:int
    unit_cost_cents:int|None
    total_cost_cents:int|None

def ensure_cost_schema(store):
    store.db.execute("""CREATE TABLE IF NOT EXISTS lot_acquisition_costs (
      lot_id INTEGER PRIMARY KEY REFERENCES expiry_lots(id),
      unit_cost_cents INTEGER NOT NULL CHECK(unit_cost_cents>=0),
      source_reference TEXT NOT NULL CHECK(length(trim(source_reference))>0),
      recorded_at TEXT NOT NULL)""")

def record_lot_cost(store,lot_id,unit_cost,invoice_reference):
    store.require('inventory')
    if type(lot_id) is not int or lot_id<=0:raise ValueError('Invalid lot ID')
    if not isinstance(invoice_reference,str) or not invoice_reference.strip():raise ValueError('Invoice reference required')
    amount=cents(unit_cost)
    ensure_cost_schema(store)
    store.db.execute('BEGIN IMMEDIATE')
    try:
        if not store.db.execute('SELECT 1 FROM expiry_lots WHERE id=?',(lot_id,)).fetchone():
            raise ValueError('Unknown lot')
        if store.db.execute('SELECT 1 FROM lot_acquisition_costs WHERE lot_id=?',(lot_id,)).fetchone():
            raise ValueError('Lot cost already recorded; correction requires audited workflow')
        store.db.execute('INSERT INTO lot_acquisition_costs VALUES(?,?,?,?)',
                         (lot_id,amount,invoice_reference.strip(),stamp()))
        store.db.execute('COMMIT')
    except BaseException:
        store.db.execute('ROLLBACK');raise

def allocation_costs(store):
    store.require('reports')
    ensure_cost_schema(store)
    rows=store.db.execute("""SELECT a.sale_line_id,a.lot_id,a.quantity,c.unit_cost_cents
        FROM sale_lot_allocations a LEFT JOIN lot_acquisition_costs c ON c.lot_id=a.lot_id
        ORDER BY a.sale_line_id,a.id""").fetchall()
    return [CostedAllocation(line,lot,qty,cost,None if cost is None else qty*cost)
            for line,lot,qty,cost in rows]

def costing_summary(store):
    rows=allocation_costs(store)
    return {'costed_quantity':sum(r.quantity for r in rows if r.total_cost_cents is not None),
            'unknown_quantity':sum(r.quantity for r in rows if r.total_cost_cents is None),
            'known_cost_cents':sum(r.total_cost_cents or 0 for r in rows),
            'complete':all(r.total_cost_cents is not None for r in rows)}


@dataclass(frozen=True)
class PeriodCostCoverage:
    """Sale-period FEFO cost coverage; NOT a profit statement (returns excluded)."""
    sale_lines: int
    sold_quantity: int
    allocated_quantity: int
    known_cost_quantity: int
    unknown_cost_quantity: int
    missing_allocation_quantity: int
    excess_allocation_quantity: int
    known_cost_cents: int
    complete: bool


def period_cost_coverage(store, period='day', day=None, timezone_name='Africa/Casablanca'):
    """Count every sold unit, including sales without any lot allocation.

    This read-only diagnostic deliberately does not substitute product costs or
    include refunds; only a fully covered sale can be costed from actual lots.
    """
    from profit_reports import utc_query_bounds
    store.require('reports')
    ensure_cost_schema(store)
    start,end=utc_query_bounds(period,day,timezone_name)
    rows=store.db.execute("""SELECT l.id,l.quantity,
        COALESCE(SUM(a.quantity),0),
        COALESCE(SUM(CASE WHEN c.unit_cost_cents IS NOT NULL THEN a.quantity ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN c.unit_cost_cents IS NULL THEN a.quantity ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN c.unit_cost_cents IS NOT NULL THEN a.quantity*c.unit_cost_cents ELSE 0 END),0)
        FROM sale_lines l JOIN sales s ON s.id=l.sale_id
        LEFT JOIN sale_lot_allocations a ON a.sale_line_id=l.id
        LEFT JOIN lot_acquisition_costs c ON c.lot_id=a.lot_id
        WHERE s.created_at>=? AND s.created_at<?
        GROUP BY l.id,l.quantity""",(start,end)).fetchall()
    sold=sum(r[1] for r in rows)
    allocated=sum(r[2] for r in rows)
    known=sum(r[3] for r in rows)
    unknown=sum(r[4] for r in rows)
    missing=sum(max(0,r[1]-r[2]) for r in rows)
    excess=sum(max(0,r[2]-r[1]) for r in rows)
    return PeriodCostCoverage(len(rows),sold,allocated,known,unknown,missing,excess,
        sum(r[5] for r in rows),bool(rows) and missing==0 and excess==0 and unknown==0)


@dataclass(frozen=True)
class VerifiedSalesMargin:
    """Sales-only FEFO margin. Not a net profit report; returns and expenses excluded."""
    sales_cents: int
    known_cogs_cents: int
    gross_margin_cents: int | None
    sold_quantity: int
    uncosted_quantity: int
    complete: bool


def verified_sales_margin(store, period='day', day=None, timezone_name='Africa/Casablanca'):
    """Only publish a margin if EVERY sale line has fully costed lot allocations.

    Never fall back to a mutable product cost or mistake unknown COGS for zero.
    Excludes returns, expenses and any sale-level discount allocation.
    """
    from profit_reports import utc_query_bounds
    store.require('reports')
    coverage=period_cost_coverage(store,period,day,timezone_name)
    start,end=utc_query_bounds(period,day,timezone_name)
    sales=int(store.db.execute(
        'SELECT COALESCE(SUM(total_cents),0) FROM sales WHERE created_at>=? AND created_at<?',
        (start,end)).fetchone()[0] or 0)
    complete=coverage.complete
    return VerifiedSalesMargin(sales,coverage.known_cost_cents,
        sales-coverage.known_cost_cents if complete else None,
        coverage.sold_quantity,coverage.unknown_cost_quantity+coverage.missing_allocation_quantity,
        complete)


@dataclass(frozen=True)
class VerifiedPeriodProfit:
    """Period net result using documented lot costs; None means unverified.

    Partial returns spanning different-cost lots are deliberately ambiguous.
    """
    sales_cents: int
    refunds_cents: int
    expenses_cents: int
    known_sold_cost_cents: int
    known_returned_cost_cents: int
    net_profit_cents: int | None
    complete: bool
    issues: tuple[str, ...]


def verified_period_profit(store, period='day', day=None, timezone_name='Africa/Casablanca'):
    """Read-only FEFO net profit; refuse to guess when original lots are unknown.

    A returned unit has a verifiable cost only if its original sale line
    was fully allocated and all its allocated lots share one unit cost,
    or the entire line is returned. No stock-restocking cost is inferred.
    """
    from profit_reports import utc_query_bounds
    store.require('reports')
    ensure_cost_schema(store)
    start,end=utc_query_bounds(period,day,timezone_name)
    db=store.db
    def amount(sql):
        return int(db.execute(sql,(start,end)).fetchone()[0] or 0)
    sales=amount('SELECT COALESCE(SUM(total_cents),0) FROM sales WHERE created_at>=? AND created_at<?')
    full_refunds=amount('SELECT COALESCE(SUM(refund_cents),0) FROM sale_returns WHERE created_at>=? AND created_at<?')
    partial_refunds=amount('SELECT COALESCE(SUM(refund_cents),0) FROM partial_returns WHERE created_at>=? AND created_at<?')
    expenses=amount('SELECT COALESCE(SUM(amount_cents),0) FROM expenses WHERE created_at>=? AND created_at<?')
    issues=[]
    # Check the financial validity of refunds affecting this period, including
    # refunds booked in earlier periods for the same original sale.
    affected_sales=db.execute("""SELECT DISTINCT sale_id FROM (
        SELECT sale_id FROM sale_returns WHERE created_at>=? AND created_at<?
        UNION ALL SELECT sale_id FROM partial_returns WHERE created_at>=? AND created_at<?
    )""",(start,end,start,end)).fetchall()
    for (sale_id,) in affected_sales:
        original=db.execute('SELECT total_cents FROM sales WHERE id=?',(sale_id,)).fetchone()
        if original is None:
            issues.append(f'sale {sale_id}: refund references missing sale')
            continue
        refunded=db.execute("""SELECT
          (SELECT COALESCE(SUM(refund_cents),0) FROM sale_returns WHERE sale_id=?) +
          (SELECT COALESCE(SUM(refund_cents),0) FROM partial_returns WHERE sale_id=?)""",
          (sale_id,sale_id)).fetchone()[0]
        if refunded>original[0]:
            issues.append(f'sale {sale_id}: cumulative refund exceeds original sale total')
        mismatches=db.execute("""SELECT COUNT(*) FROM partial_return_lines prl
          JOIN partial_returns pr ON pr.id=prl.return_id
          JOIN sale_lines sl ON sl.id=prl.sale_line_id
          WHERE pr.sale_id=? AND sl.sale_id<>pr.sale_id""",(sale_id,)).fetchone()[0]
        if mismatches:
            issues.append(f'sale {sale_id}: return lines reference a different sale')
    # A refund without itemized returned quantities has no defensible FEFO
    # cost reversal. Do not silently report it as a verified net result.
    partials=db.execute("""SELECT id,sale_id FROM partial_returns
        WHERE created_at>=? AND created_at<?""",(start,end)).fetchall()
    for return_id,sale_id in partials:
        detail=db.execute("""SELECT COUNT(*),COALESCE(SUM(prl.quantity),0),
            COALESCE(SUM(CASE WHEN sl.id IS NULL OR sl.sale_id<>? THEN 1 ELSE 0 END),0)
            FROM partial_return_lines prl
            LEFT JOIN sale_lines sl ON sl.id=prl.sale_line_id
            WHERE prl.return_id=?""",(sale_id,return_id)).fetchone()
        if detail[0]==0 or detail[1]<=0:
            issues.append(f'partial return {return_id}: missing itemized return quantities')
        if detail[2]:
            issues.append(f'partial return {return_id}: lines reference missing or different sale')
    # Include original sale lines from older periods when returned now.
    lines=db.execute("""SELECT DISTINCT l.id,l.quantity,l.sale_id FROM sale_lines l
        JOIN sales s ON s.id=l.sale_id
        WHERE (s.created_at>=? AND s.created_at<?)
        OR EXISTS (SELECT 1 FROM sale_returns r WHERE r.sale_id=s.id AND r.created_at>=? AND r.created_at<?)
        OR EXISTS (SELECT 1 FROM partial_return_lines prl JOIN partial_returns pr ON pr.id=prl.return_id
                   WHERE prl.sale_line_id=l.id AND pr.created_at>=? AND pr.created_at<?)""",
        (start,end,start,end,start,end)).fetchall()
    sold_cost=returned_cost=0
    for line_id,qty,sale_id in lines:
        allocations=db.execute("""SELECT a.quantity,c.unit_cost_cents FROM sale_lot_allocations a
            LEFT JOIN lot_acquisition_costs c ON c.lot_id=a.lot_id
            WHERE a.sale_line_id=?""",(line_id,)).fetchall()
        if sum(a[0] for a in allocations)!=qty or any(a[1] is None or a[0]<=0 for a in allocations):
            issues.append(f'sale line {line_id}: missing or uncosted lot allocation')
            continue
        cost=sum(a[0]*a[1] for a in allocations)
        sold_now=bool(db.execute('SELECT 1 FROM sales WHERE id=? AND created_at>=? AND created_at<?',
                                 (sale_id,start,end)).fetchone())
        if sold_now: sold_cost+=cost
        full=db.execute('SELECT 1 FROM sale_returns WHERE sale_id=? AND created_at>=? AND created_at<?',
                        (sale_id,start,end)).fetchone()
        if full:
            returned_cost+=cost
        partial_qty=int(db.execute("""SELECT COALESCE(SUM(prl.quantity),0) FROM partial_return_lines prl
            JOIN partial_returns pr ON pr.id=prl.return_id
            WHERE prl.sale_line_id=? AND pr.created_at>=? AND pr.created_at<?""",
            (line_id,start,end)).fetchone()[0] or 0)
        # Validate return history across ALL periods, not just this report window.
        # Otherwise a prior-month partial refund followed by a full refund this
        # month (or the reverse) would falsely produce a verified profit.
        historical_full=bool(db.execute(
            'SELECT 1 FROM sale_returns WHERE sale_id=? LIMIT 1',(sale_id,)).fetchone())
        historical_partial_qty=int(db.execute('''SELECT COALESCE(SUM(prl.quantity),0)
            FROM partial_return_lines prl JOIN partial_returns pr ON pr.id=prl.return_id
            WHERE prl.sale_line_id=?''',(line_id,)).fetchone()[0] or 0)
        if historical_full and historical_partial_qty:
            issues.append(f'sale line {line_id}: overlapping full and partial returns across periods')
            continue
        if historical_partial_qty>qty:
            issues.append(f'sale line {line_id}: cumulative returns exceed sold quantity')
            continue
        if partial_qty:
            if partial_qty>qty:
                issues.append(f'sale line {line_id}: return exceeds sold quantity')
            elif len({a[1] for a in allocations})==1:
                returned_cost+=partial_qty*allocations[0][1]
            elif partial_qty==qty:
                returned_cost+=cost
            else:
                issues.append(f'sale line {line_id}: partial return spans mixed-cost lots')
    complete=not issues
    return VerifiedPeriodProfit(sales,full_refunds+partial_refunds,expenses,sold_cost,returned_cost,
        sales-full_refunds-partial_refunds-sold_cost+returned_cost-expenses if complete else None,
        complete,tuple(issues))
