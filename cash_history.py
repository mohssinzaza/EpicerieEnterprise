"""Read-only historical cash-session report with audit-friendly CSV export."""
import csv
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass(frozen=True)
class ClosedSession:
    session_id: int
    opened_at: str
    closed_at: str
    opening_cents: int
    expected_cents: int
    actual_cents: int
    variance_cents: int

def closed_sessions(store, limit=100):
    store.require('finance')
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError('Invalid history limit')
    rows = store.db.execute('''SELECT id,opened_at,closed_at,opening_cents,
        expected_cents,actual_cents,variance_cents FROM cash_sessions
        WHERE closed_at IS NOT NULL ORDER BY id DESC LIMIT ?''', (limit,)).fetchall()
    result = []
    for row in rows:
        if any(value is None for value in row):
            raise ValueError('Incomplete historical cash session')
        session = ClosedSession(*row)
        if any(type(v) is not int for v in (session.opening_cents, session.expected_cents,
                                             session.actual_cents, session.variance_cents)):
            raise ValueError('Invalid historical cash monetary fields: ' + str(session.session_id))
        if min(session.opening_cents, session.expected_cents, session.actual_cents) < 0:
            raise ValueError('Negative historical cash balance: ' + str(session.session_id))
        try:
            opened = datetime.fromisoformat(session.opened_at)
            closed = datetime.fromisoformat(session.closed_at)
            if (opened.tzinfo is None) != (closed.tzinfo is None):
                raise ValueError('Inconsistent cash session timezones')
            if closed < opened:
                raise ValueError('Cash session closed before opening')
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid cash session timestamps: ' + str(session.session_id)) from exc
        if session.actual_cents - session.expected_cents != session.variance_cents:
            raise ValueError('Historical cash variance mismatch: ' + str(session.session_id))
        result.append(session)
    # Detect overlapping historical sessions, including corrupted imported records.
    # Compare in chronological order rather than assuming IDs imply chronology.
    intervals = []
    for session in result:
        opened = datetime.fromisoformat(session.opened_at)
        closed = datetime.fromisoformat(session.closed_at)
        intervals.append((opened, closed, session.session_id))
    try:
        intervals.sort(key=lambda item: item[0])
        for previous, current in zip(intervals, intervals[1:]):
            if current[0] < previous[1]:
                raise ValueError('Overlapping historical cash sessions: '
                                 + str(previous[2]) + ' / ' + str(current[2]))
    except TypeError as exc:
        raise ValueError('Inconsistent historical cash session timezones') from exc
    return tuple(result)

def export_cash_history(store, destination, limit=10000):
    target = Path(destination)
    if target.suffix.lower() != '.csv':
        raise ValueError('CSV extension required')
    if target.exists():
        raise FileExistsError('Refusing to overwrite cash history')
    rows = closed_sessions(store, limit)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='',
                dir=target.parent, prefix='.cash-history-', suffix='.tmp', delete=False) as output:
            temp = Path(output.name)
            writer = csv.writer(output)
            writer.writerow(['Session ID', 'Opened at', 'Closed at', 'Opening centimes',
                             'Expected centimes', 'Actual centimes', 'Variance centimes'])
            for r in rows:
                writer.writerow([r.session_id,r.opened_at,r.closed_at,r.opening_cents,
                                 r.expected_cents,r.actual_cents,r.variance_cents])
            output.flush()
            os.fsync(output.fileno())
        os.link(temp, target)
        return target
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
