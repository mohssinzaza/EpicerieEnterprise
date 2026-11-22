"""Read-only sale-cost provenance audit; does not claim FIFO/FEFO costing."""
from dataclasses import dataclass
from inventory_reconciliation import export_stock_differences  # shared package compatibility
import csv
import os
import tempfile
from pathlib import Path

@dataclass(frozen=True)
class CostFinding:
    sale_line_id: int
    sale_id: int
    barcode: str
    quantity: int
    booked_cost_cents: int
    latest_purchase_cost_cents: int | None
    status: str

def inspect_sale_costs(store):
    """Identify booked sale costs not traceable to a prior purchase invoice.

    A matching prior invoice is only evidence, not proof of actual lot consumption.
    Opening stock and stock adjustments may legitimately lack a purchase invoice.
    """
    store.require('reports')
    rows=store.db.execute("""
      SELECT sl.id,sl.sale_id,p.barcode,sl.quantity,sl.unit_cost_cents,
       (SELECT pl.unit_cost_cents FROM purchase_lines pl
        JOIN purchases pu ON pu.id=pl.purchase_id
        WHERE pl.product_id=sl.product_id AND pu.created_at<=s.created_at
        ORDER BY pu.created_at DESC,pu.id DESC,pl.id DESC LIMIT 1)
      FROM sale_lines sl JOIN sales s ON s.id=sl.sale_id
      JOIN products p ON p.id=sl.product_id ORDER BY sl.id
    """).fetchall()
    findings=[]
    for line_id,sale_id,barcode,qty,booked,latest in rows:
        if booked is None or booked<0:
            status='invalid_booked_cost'
        elif latest is None:
            status='no_prior_purchase_invoice'
        elif booked!=latest:
            status='differs_from_latest_purchase'
        else:
            continue
        findings.append(CostFinding(line_id,sale_id,barcode,qty,booked,latest,status))
    return findings

def export_cost_findings(findings,target):
    """Atomic no-overwrite CSV export with a clear non-FIFO disclaimer."""
    target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise FileExistsError(str(target))
    fd,tmp=tempfile.mkstemp(prefix='.cost_audit_',suffix='.tmp',dir=target.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8-sig',newline='') as out:
            writer=csv.writer(out)
            writer.writerow(['sale_line_id','sale_id','barcode','quantity','booked_cost_cents','latest_prior_purchase_cost_cents','status'])
            for f in findings:
                writer.writerow([f.sale_line_id,f.sale_id,f.barcode,f.quantity,f.booked_cost_cents,f.latest_purchase_cost_cents if f.latest_purchase_cost_cents is not None else '',f.status])
            out.flush();os.fsync(out.fileno())
        os.link(tmp,target)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return target
