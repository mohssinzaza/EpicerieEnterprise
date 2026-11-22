"""Verified cash close: the persisted expected balance equals the audited preview."""
from engine import cents, stamp
from cash_reconciliation import inspect

def close_verified(store, actual):
    store.require('finance')
    actual_cents = cents(actual)
    if actual_cents < 0:
        raise ValueError('Counted cash cannot be negative')
    db = store.db
    db.execute('BEGIN IMMEDIATE')
    try:
        readiness = inspect(store)
        if not readiness.ready_for_close:
            raise ValueError('Cash close blocked: ' + '; '.join(readiness.warnings))
        expected = readiness.expected_cents
        variance = actual_cents - expected
        cursor = db.execute('''UPDATE cash_sessions SET closed_at=?,expected_cents=?,actual_cents=?,variance_cents=?
            WHERE id=? AND closed_at IS NULL''', (stamp(),expected,actual_cents,variance,readiness.session_id))
        if cursor.rowcount != 1:
            raise RuntimeError('Cash session changed during closing')
        db.execute('COMMIT')
        return expected,variance
    except BaseException:
        db.execute('ROLLBACK')
        raise
