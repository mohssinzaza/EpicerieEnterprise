"""Read-only cash audit export with explicit limitations."""
import csv
from pathlib import Path
from cash_audit import snapshot

FIELDS = [
    ('session_id', 'Session / جلسة'),
    ('opening_cents', 'Opening / افتتاح'),
    ('cash_sales_cents', 'Cash sales / مبيعات نقدية'),
    ('customer_cash_cents', 'Customer receipts / تحصيل الزبائن'),
    ('supplier_cash_cents', 'Supplier payments / أداء الموردين'),
    ('expenses_cents', 'Expenses / مصاريف'),
    ('refunds_cents', 'Refunds / مرتجعات'),
    ('expected_cents', 'Advisory cash / الرصيد التقديري'),
]
DISCLAIMER = 'ADVISORY ONLY: historical cash methods, partial returns and some legacy transactions may be missing; not an accounting close.'

def report_rows(store):
    result=snapshot(store)
    return [(label, getattr(result, key)) for key,label in FIELDS]

def export_csv(store, destination):
    destination=Path(destination)
    if destination.exists():
        raise FileExistsError('Refusing to overwrite existing report')
    if destination.suffix.lower()!='.csv':
        raise ValueError('Report must use .csv extension')
    rows=report_rows(store)  # validate access and open session before touching file
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('x',encoding='utf-8-sig',newline='') as output:
        writer=csv.writer(output)
        writer.writerow(['Field / البيان','Centimes / سنتيم'])
        writer.writerows(rows)
        writer.writerow(['Notice / تنبيه',DISCLAIMER])
    return destination
