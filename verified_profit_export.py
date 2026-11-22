"""Fail-closed CSV export of a verified FEFO profit snapshot.

An incomplete result remains explicitly UNVERIFIED; no net figure is invented.
"""
import csv
import os
import tempfile
from pathlib import Path
from lot_costing import verified_period_profit
from profit_reports import utc_query_bounds


def safe_spreadsheet_cell(value):
    """Prevent CSV formula execution when a report is opened in spreadsheet apps."""
    if not isinstance(value, str):
        return value
    # Excel/LibreOffice may treat leading whitespace or control chars before
    # formula markers as part of an executable formula.
    if value.lstrip('\t\r\n ').startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def export_verified_profit(store, target, period='day', day=None, timezone_name='Africa/Casablanca'):
    store.require('reports')
    # Validate the interval before touching the target path.
    start, end = utc_query_bounds(period, day, timezone_name)
    report = verified_period_profit(store, period, day, timezone_name)
    path = Path(target)
    if not path.name or path.suffix.lower() != '.csv':
        raise ValueError('A .csv destination is required')
    if path.exists():
        raise FileExistsError('Existing report will not be overwritten')
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        ('period', period), ('start_utc', start), ('end_utc', end),
        ('timezone', timezone_name), ('status', 'VERIFIED' if report.complete else 'UNVERIFIED'),
        ('sales_cents', report.sales_cents), ('refunds_cents', report.refunds_cents),
        ('expenses_cents', report.expenses_cents),
        ('known_sold_cost_cents', report.known_sold_cost_cents),
        ('known_returned_cost_cents', report.known_returned_cost_cents),
        ('net_profit_cents', report.net_profit_cents if report.complete else ''),
    ]
    fields.extend(('issue', issue) for issue in report.issues)
    fd, temporary = tempfile.mkstemp(prefix='.verified_profit_', suffix='.tmp', dir=path.parent)
    created_target = False
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as out:
            writer = csv.writer(out)
            writer.writerow(['field', 'value'])
            writer.writerows((safe_spreadsheet_cell(k), safe_spreadsheet_cell(v)) for k, v in fields)
            out.flush()
            os.fsync(out.fileno())
        # Exclusive creation prevents silently replacing an existing file.
        with open(path, 'xb') as output, open(temporary, 'rb') as source:
            created_target = True
            while True:
                chunk = source.read(65536)
                if not chunk:
                    break
                output.write(chunk)
    except BaseException:
        # Never leave a partial report mistaken for a valid export.
        if created_target and path.exists():
            path.unlink()
        raise
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path
