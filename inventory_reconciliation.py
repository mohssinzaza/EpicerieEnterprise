"""Read-only stock/ledger consistency check; does not alter inventory."""
import csv
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class StockDifference:
    product_id: int
    barcode: str
    name: str
    stock: int
    ledger_stock: int
    difference: int

def reconcile_stock(store):
    """Return discrepancies between stock snapshot and signed movement history."""
    store.require('reports')
    rows=store.db.execute("""
        SELECT p.id,p.barcode,p.name,p.stock,COALESCE(SUM(l.delta),0)
        FROM products p LEFT JOIN stock_ledger l ON l.product_id=p.id
        GROUP BY p.id,p.barcode,p.name,p.stock ORDER BY p.id
    """).fetchall()
    return [StockDifference(pid,barcode,name,stock,ledger,stock-ledger)
            for pid,barcode,name,stock,ledger in rows if stock!=ledger]

def export_stock_differences(rows,target):
    """Write a complete audit atomically; never overwrite an existing report.

    A temporary file is created in the destination directory and linked to
    the final name only after the CSV has been flushed to disk. This prevents
    truncated reports when serialization fails midway.
    """
    target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        raise FileExistsError(str(target))
    fd,temp_name=tempfile.mkstemp(prefix='.stock_audit_',suffix='.tmp',dir=target.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8-sig',newline='') as f:
            writer=csv.writer(f)
            writer.writerow(['product_id','barcode','name','stock','ledger_stock','difference'])
            for row in rows:
                writer.writerow([row.product_id,row.barcode,row.name,row.stock,row.ledger_stock,row.difference])
            f.flush()
            os.fsync(f.fileno())
        os.link(temp_name,target)  # atomic, fails if destination exists
    finally:
        Path(temp_name).unlink(missing_ok=True)
    return target
