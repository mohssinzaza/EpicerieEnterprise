"""Period-based operational profit (UTC), amounts in integer centimes.

Accrual-style revenue: credit sales counted at sale date, not collection date.
Return revenue and original line cost reversed at return date.
Cost is the unit_cost_cents captured on each sale line, not live product cost.
This is NOT a statutory accounting statement; taxes, shrinkage and overhead allocations
are not fully modelled in the current application.
"""
import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

@dataclass(frozen=True)
class ProfitReport:
    start: str
    end: str
    sales_cents: int
    returned_revenue_cents: int
    cogs_cents: int
    returned_cost_cents: int
    expenses_cents: int
    net_revenue_cents: int
    gross_profit_cents: int
    operating_profit_cents: int
    sale_count: int
    timezone_name: str = 'UTC'

def bounds(period, day=None):
    day = day or dt.datetime.now(dt.timezone.utc).date()
    if isinstance(day,str): day=dt.date.fromisoformat(day)
    if not isinstance(day,dt.date): raise ValueError('Invalid report date')
    if period=='day': start=day;end=day+dt.timedelta(days=1)
    elif period=='week':
        start=day-dt.timedelta(days=day.weekday());end=start+dt.timedelta(days=7)
    elif period=='month':
        start=day.replace(day=1)
        end=dt.date(start.year+1,1,1) if start.month==12 else dt.date(start.year,start.month+1,1)
    else:raise ValueError('Period must be day, week or month')
    return start.isoformat(),end.isoformat()

def utc_query_bounds(period, day, timezone_name='Africa/Casablanca'):
    """Return UTC ISO timestamps delimiting a local calendar period.

    Convert both boundaries independently: Moroccan DST transitions can
    change the UTC duration of a local day.
    """
    start, end = bounds(period, day)
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError('Timezone data unavailable: install/bundle tzdata') from exc
    def convert(value):
        local = dt.datetime.combine(dt.date.fromisoformat(value), dt.time.min, tzinfo=zone)
        return local.astimezone(dt.timezone.utc).isoformat()
    return convert(start), convert(end)

def calculate(store,period='day',day=None,timezone_name='UTC'):
    store.require('reports')
    start,end=bounds(period,day)
    query_start,query_end = utc_query_bounds(period,day,timezone_name)
    db=store.db
    # ISO-8601 UTC timestamps sort correctly within this application's UTC stamp format.
    def sumq(sql):return int(db.execute(sql,(query_start,query_end)).fetchone()[0] or 0)
    sales=sumq('SELECT COALESCE(SUM(total_cents),0) FROM sales WHERE created_at>=? AND created_at<?')
    cogs=sumq('SELECT COALESCE(SUM(l.quantity*l.unit_cost_cents),0) FROM sale_lines l JOIN sales s ON s.id=l.sale_id WHERE s.created_at>=? AND s.created_at<?')
    full=sumq('SELECT COALESCE(SUM(refund_cents),0) FROM sale_returns WHERE created_at>=? AND created_at<?')
    partial=sumq('SELECT COALESCE(SUM(refund_cents),0) FROM partial_returns WHERE created_at>=? AND created_at<?')
    full_cost=sumq('SELECT COALESCE(SUM(l.quantity*l.unit_cost_cents),0) FROM sale_lines l JOIN sale_returns r ON r.sale_id=l.sale_id WHERE r.created_at>=? AND r.created_at<?')
    partial_cost=sumq('SELECT COALESCE(SUM(rl.quantity*l.unit_cost_cents),0) FROM partial_return_lines rl JOIN sale_lines l ON l.id=rl.sale_line_id JOIN partial_returns r ON r.id=rl.return_id WHERE r.created_at>=? AND r.created_at<?')
    expenses=sumq('SELECT COALESCE(SUM(amount_cents),0) FROM expenses WHERE created_at>=? AND created_at<?')
    count=sumq('SELECT COUNT(*) FROM sales WHERE created_at>=? AND created_at<?')
    net=sales-full-partial; gross=net-cogs+full_cost+partial_cost
    return ProfitReport(start,end,sales,full+partial,cogs,full_cost+partial_cost,expenses,net,gross,gross-expenses,count,timezone_name)

def export_csv(report,target):
    target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['Metric / البيان','Centimes / سنتيم'])
        for key in report.__dataclass_fields__:
            writer.writerow([key,getattr(report,key)])
    return target


def previous_period_date(period, day):
    """Same reporting granularity, immediately preceding local calendar period."""
    if isinstance(day, str):
        day = dt.date.fromisoformat(day)
    if not isinstance(day, dt.date) or isinstance(day, dt.datetime):
        raise ValueError('Invalid report date')
    start, _ = bounds(period, day)
    return dt.date.fromisoformat(start) - dt.timedelta(days=1)


def compare_periods(store, period='day', day=None, timezone_name='Africa/Casablanca'):
    """Two complete, adjacent calendar windows; integer centime differences.

    Percentage is None when the prior profit is zero or negative, because a
    percentage growth rate would be misleading for a loss or break-even base.
    """
    if day is None:
        day = dt.datetime.now(ZoneInfo(timezone_name)).date()
    if isinstance(day, str):
        day = dt.date.fromisoformat(day)
    current = calculate(store, period, day, timezone_name)
    previous = calculate(store, period, previous_period_date(period, day), timezone_name)
    delta = current.operating_profit_cents - previous.operating_profit_cents
    growth_percent = (delta * 100 / previous.operating_profit_cents) if previous.operating_profit_cents > 0 else None
    return current, previous, delta, growth_percent


@dataclass(frozen=True)
class ProductProfit:
    product_id: int
    barcode: str
    name: str
    quantity_sold: int
    quantity_returned: int
    revenue_cents: int
    returned_revenue_cents: int
    cost_cents: int
    returned_cost_cents: int
    gross_profit_cents: int

def product_profit_report(store, period='day', day=None, timezone_name='Africa/Casablanca'):
    """Read-only per-product gross margin. Returns are allocated by original sale-line price.

    Full returns are valued from the sale lines. Partial returns use the original
    line unit price and cost; any sale-level discounts/refund rounding can cause
    a difference versus the aggregate financial report. Such differences must
    be reconciled rather than silently adjusted.
    """
    store.require('reports')
    start, end = utc_query_bounds(period, day, timezone_name)
    db = store.db
    rows = db.execute("""
        SELECT p.id,p.barcode,p.name,
               COALESCE(SUM(CASE WHEN s.created_at>=? AND s.created_at<? THEN l.quantity ELSE 0 END),0),
               COALESCE(SUM(CASE WHEN s.created_at>=? AND s.created_at<? THEN l.quantity*l.unit_price_cents ELSE 0 END),0),
               COALESCE(SUM(CASE WHEN s.created_at>=? AND s.created_at<? THEN l.quantity*l.unit_cost_cents ELSE 0 END),0)
        FROM products p
        LEFT JOIN sale_lines l ON l.product_id=p.id
        LEFT JOIN sales s ON s.id=l.sale_id
        GROUP BY p.id,p.barcode,p.name
    """,(start,end,start,end,start,end)).fetchall()
    full = {r[0]:r[1:] for r in db.execute("""
        SELECT l.product_id,SUM(l.quantity),SUM(l.quantity*l.unit_price_cents),SUM(l.quantity*l.unit_cost_cents)
        FROM sale_returns r JOIN sale_lines l ON l.sale_id=r.sale_id
        WHERE r.created_at>=? AND r.created_at<? GROUP BY l.product_id
    """,(start,end))}
    partial = {r[0]:r[1:] for r in db.execute("""
        SELECT l.product_id,SUM(rl.quantity),SUM(rl.quantity*l.unit_price_cents),SUM(rl.quantity*l.unit_cost_cents)
        FROM partial_returns r JOIN partial_return_lines rl ON rl.return_id=r.id
        JOIN sale_lines l ON l.id=rl.sale_line_id
        WHERE r.created_at>=? AND r.created_at<? GROUP BY l.product_id
    """,(start,end))}
    result=[]
    for pid,barcode,name,qty,revenue,cost in rows:
        f=full.get(pid,(0,0,0)); q=partial.get(pid,(0,0,0))
        ret_qty=f[0]+q[0]; ret_rev=f[1]+q[1]; ret_cost=f[2]+q[2]
        if qty or ret_qty:
            result.append(ProductProfit(pid,barcode,name,qty,ret_qty,revenue,ret_rev,cost,ret_cost,revenue-ret_rev-cost+ret_cost))
    return sorted(result,key=lambda x:(-x.gross_profit_cents,x.name,x.product_id))

def export_product_profit_csv(rows,target):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(list(ProductProfit.__dataclass_fields__))
        for row in rows:writer.writerow([getattr(row,key) for key in ProductProfit.__dataclass_fields__])
    return target

@dataclass(frozen=True)
class ProfitReconciliation:
    """Difference between booked period totals and product-level breakdown.

    A zero difference is a consistency check, not proof of correct purchase-lot costs.
    """
    start: str
    end: str
    booked_net_revenue_cents: int
    products_net_revenue_cents: int
    revenue_difference_cents: int
    booked_net_cost_cents: int
    products_net_cost_cents: int
    cost_difference_cents: int
    booked_gross_profit_cents: int
    products_gross_profit_cents: int
    gross_profit_difference_cents: int
    balanced: bool


def reconcile_product_profits(store, period='day', day=None, timezone_name='Africa/Casablanca'):
    """Read-only reconciliation; discrepancies are exposed, never silently allocated."""
    report = calculate(store, period, day, timezone_name)
    products = product_profit_report(store, period, day, timezone_name)
    revenue = sum(p.revenue_cents-p.returned_revenue_cents for p in products)
    cost = sum(p.cost_cents-p.returned_cost_cents for p in products)
    gross = sum(p.gross_profit_cents for p in products)
    booked_cost = report.cogs_cents-report.returned_cost_cents
    return ProfitReconciliation(
        report.start,report.end,report.net_revenue_cents,revenue,
        report.net_revenue_cents-revenue,booked_cost,cost,booked_cost-cost,
        report.gross_profit_cents,gross,report.gross_profit_cents-gross,
        report.net_revenue_cents==revenue and booked_cost==cost and report.gross_profit_cents==gross
    )


def export_reconciliation_csv(reconciliation,target):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['Field / البيان','Value / القيمة'])
        for key in reconciliation.__dataclass_fields__:
            writer.writerow([key,getattr(reconciliation,key)])
    return target


@dataclass(frozen=True)
class MonthlyTrend:
    month: str
    net_revenue_cents: int
    net_cost_cents: int
    gross_profit_cents: int
    expenses_cents: int
    operating_profit_cents: int
    sale_count: int


def monthly_profit_trend(store, year, timezone_name='Africa/Casablanca'):
    """Twelve complete calendar-month profit snapshots, read-only.

    Do not annualize partial months or silently omit loss-making months.
    Each month uses local calendar boundaries, independently converted to UTC.
    """
    if isinstance(year, bool) or not isinstance(year, int) or year < 1900 or year > 9999:
        raise ValueError('Year must be an integer between 1900 and 9999')
    result=[]
    for month in range(1,13):
        date=dt.date(year,month,1)
        r=calculate(store,'month',date,timezone_name)
        result.append(MonthlyTrend(date.strftime('%Y-%m'),r.net_revenue_cents,
                                   r.cogs_cents-r.returned_cost_cents,r.gross_profit_cents,
                                   r.expenses_cents,r.operating_profit_cents,r.sale_count))
    return result


def export_monthly_trend_csv(rows, target):
    """Excel-compatible UTF-8 CSV; refuse to overwrite an existing export."""
    target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['month / الشهر','net_revenue_cents','net_cost_cents',
                         'gross_profit_cents','expenses_cents','operating_profit_cents','sale_count'])
        for r in rows:
            writer.writerow([r.month,r.net_revenue_cents,r.net_cost_cents,
                             r.gross_profit_cents,r.expenses_cents,r.operating_profit_cents,r.sale_count])
    return target
