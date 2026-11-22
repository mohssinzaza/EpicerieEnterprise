"""Read-only preflight checks for trustworthy profit reports.

Flags anomalies; does not change invoices or claim statutory accounting accuracy.
"""
from dataclasses import dataclass
from pathlib import Path
import csv
from profit_reports import calculate, reconcile_product_profits, utc_query_bounds

@dataclass(frozen=True)
class ProfitQuality:
    period: str
    start_utc: str
    end_utc: str
    zero_cost_lines: int
    zero_cost_units: int
    negative_margin_lines: int
    negative_margin_loss_cents: int
    missing_line_sales: int
    reconciliation_balanced: bool
    reconciliation_difference_cents: int
    operating_profit_cents: int
    warnings: tuple
    ready_for_review: bool

def check_profit_quality(store, period='day', day=None, timezone_name='Africa/Casablanca'):
    """No writes. Flag suspicious unit costs, loss-making lines and missing lines.

    Negative-margin sales can be legitimate and are warnings rather than blockers.
    Zero-cost items may be legitimate promotional goods; manual review required.
    """
    store.require('reports')
    start,end=utc_query_bounds(period,day,timezone_name)
    db=store.db
    zero=db.execute('''SELECT COUNT(*),COALESCE(SUM(l.quantity),0) FROM sale_lines l
        JOIN sales s ON s.id=l.sale_id WHERE s.created_at>=? AND s.created_at<?
        AND l.unit_cost_cents=0''',(start,end)).fetchone()
    negative=db.execute('''SELECT COUNT(*),COALESCE(SUM(l.quantity*(l.unit_cost_cents-l.unit_price_cents)),0)
        FROM sale_lines l JOIN sales s ON s.id=l.sale_id
        WHERE s.created_at>=? AND s.created_at<? AND l.unit_price_cents<l.unit_cost_cents''',(start,end)).fetchone()
    missing=db.execute('''SELECT COUNT(*) FROM sales s WHERE s.created_at>=? AND s.created_at<?
        AND NOT EXISTS (SELECT 1 FROM sale_lines l WHERE l.sale_id=s.id)''',(start,end)).fetchone()[0]
    recon=reconcile_product_profits(store,period,day,timezone_name)
    report=calculate(store,period,day,timezone_name)
    warnings=[]
    if zero[0]: warnings.append(f'{zero[0]} sale lines have zero recorded cost; review margins')
    if negative[0]: warnings.append(f'{negative[0]} sale lines have negative unit margin; review pricing')
    if missing: warnings.append(f'{missing} sales have no item lines')
    if not recon.balanced: warnings.append('Product and aggregate profit reports do not reconcile')
    ready=not zero[0] and not missing and recon.balanced
    return ProfitQuality(period,start,end,int(zero[0]),int(zero[1]),int(negative[0]),
        int(negative[1]),int(missing),recon.balanced,int(recon.gross_profit_difference_cents),
        int(report.operating_profit_cents),tuple(warnings),ready)

def export_quality_csv(report,target):
    """Create new Excel-compatible file; never overwrite an earlier audit."""
    target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f)
        w.writerow(['Indicator / المؤشر','Value / القيمة'])
        for key in report.__dataclass_fields__:
            value=getattr(report,key)
            w.writerow([key,' | '.join(value) if key=='warnings' else value])
    return target
