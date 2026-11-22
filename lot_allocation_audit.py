"""Read-only integrity audit of FEFO tracked-lot quantities; not a costing engine."""
from dataclasses import dataclass
import csv, os, tempfile
from pathlib import Path

@dataclass(frozen=True)
class LotIssue:
    kind: str
    reference_id: int
    barcode: str
    expected: int
    actual: int


def audit_lot_allocations(store):
    store.require('reports')
    db=store.db
    issues=[]
    tracked=db.execute('''SELECT p.id,p.barcode,p.stock FROM tracked_products t
        JOIN products p ON p.id=t.product_id ORDER BY p.id''').fetchall()
    for product_id,barcode,stock in tracked:
        lots=db.execute('''SELECT l.id,l.received_qty,b.remaining_qty FROM expiry_lots l
            LEFT JOIN lot_balances b ON b.lot_id=l.id WHERE l.product_id=? ORDER BY l.id''',(product_id,)).fetchall()
        remaining_sum=0
        for lot_id,received,remaining in lots:
            if remaining is None:
                issues.append(LotIssue('missing_lot_balance',lot_id,barcode,received,-1))
                continue
            allocated=db.execute('''SELECT COALESCE(SUM(a.quantity),0) FROM sale_lot_allocations a
                WHERE a.lot_id=?''',(lot_id,)).fetchone()[0]
            expected=received-allocated
            if remaining!=expected:
                issues.append(LotIssue('lot_balance_mismatch',lot_id,barcode,expected,remaining))
            remaining_sum+=remaining
        if stock!=remaining_sum:
            issues.append(LotIssue('product_stock_mismatch',product_id,barcode,remaining_sum,stock))
        lines=db.execute('''SELECT sl.id,sl.quantity,COALESCE(SUM(a.quantity),0)
            FROM sale_lines sl JOIN sales s ON s.id=sl.sale_id
            LEFT JOIN sale_lot_allocations a ON a.sale_line_id=sl.id
            WHERE sl.product_id=? GROUP BY sl.id ORDER BY sl.id''',(product_id,)).fetchall()
        for line_id,quantity,allocated in lines:
            if quantity!=allocated:
                issues.append(LotIssue('sale_allocation_mismatch',line_id,barcode,quantity,allocated))
    orphan=db.execute('''SELECT a.id,a.quantity,p.barcode FROM sale_lot_allocations a
        JOIN sale_lines sl ON sl.id=a.sale_line_id
        JOIN products p ON p.id=sl.product_id
        JOIN expiry_lots l ON l.id=a.lot_id
        WHERE l.product_id!=sl.product_id ORDER BY a.id''').fetchall()
    for alloc_id,qty,barcode in orphan:
        issues.append(LotIssue('cross_product_allocation',alloc_id,barcode,0,qty))
    return issues


def export_lot_issues(issues,target):
    target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise FileExistsError(str(target))
    fd,tmp=tempfile.mkstemp(prefix='.lot_audit_',suffix='.tmp',dir=target.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8-sig',newline='') as out:
            writer=csv.writer(out)
            writer.writerow(['kind','reference_id','barcode','expected','actual'])
            for issue in issues:writer.writerow([issue.kind,issue.reference_id,issue.barcode,issue.expected,issue.actual])
            out.flush();os.fsync(out.fileno())
        os.link(tmp,target)
    finally:Path(tmp).unlink(missing_ok=True)
    return target
