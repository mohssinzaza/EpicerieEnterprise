"""Read-only SQLite and transaction consistency diagnostics."""
from contextlib import closing
import sqlite3, json
from pathlib import Path
from datetime import datetime, timezone

def inspect(path):
    path=Path(path)
    if not path.is_file(): raise FileNotFoundError(path)
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'products','sales','sale_lines','stock_ledger','audit'}<=tables:
            raise ValueError('Not an Epicerie Enterprise database')
        checks={}
        checks['sqlite_integrity']=int(db.execute('PRAGMA integrity_check').fetchone()[0]!='ok')
        checks['foreign_key_errors']=len(db.execute('PRAGMA foreign_key_check').fetchall())
        checks['negative_stock']=db.execute('SELECT COUNT(*) FROM products WHERE stock<0').fetchone()[0]
        checks['sale_total_mismatches']=db.execute('''SELECT COUNT(*) FROM sales s WHERE s.total_cents != COALESCE((SELECT SUM(l.quantity*l.unit_price_cents) FROM sale_lines l WHERE l.sale_id=s.id),0)''').fetchone()[0]
        if 'customer_invoices' in tables:
            checks['invoice_total_mismatches']=db.execute('''SELECT COUNT(*) FROM customer_invoices i JOIN sales s ON s.id=i.sale_id WHERE i.total_cents != s.total_cents''').fetchone()[0]
        if {'purchases','purchase_lines'}<=tables:
            checks['purchase_total_mismatches']=db.execute('''SELECT COUNT(*) FROM purchases p WHERE p.total_cents != COALESCE((SELECT SUM(l.quantity*l.unit_cost_cents) FROM purchase_lines l WHERE l.purchase_id=p.id),0)''').fetchone()[0]
        return {'checked_at_utc':datetime.now(timezone.utc).isoformat(),'database':str(path.resolve()),'products':db.execute('SELECT COUNT(*) FROM products').fetchone()[0],'sales':db.execute('SELECT COUNT(*) FROM sales').fetchone()[0],'checks':checks,'total_findings':sum(checks.values()),'note':'Read-only technical checks, not a complete financial audit. Discounts and historical adjustments may need manual review.'}

def save_json(report,target):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    return target
