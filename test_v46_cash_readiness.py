import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_reconciliation import inspect

class CashReadinessV46(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=CommercialStore(Path(self.tmp.name)/'test.db')
        self.store.bootstrap('admin','very-secure-password-2026')
        self.store.login('admin','very-secure-password-2026')
        self.store.open_cash('100')
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def test_clean_session_ready(self):
        self.assertTrue(inspect(self.store).ready_for_close)
    def test_expense_without_payment_method_blocks(self):
        self.store.expense('rent','rent','5')
        report=inspect(self.store)
        self.assertFalse(report.ready_for_close)
        self.assertTrue(any('expense(s) lack verified payment method' in w for w in report.warnings))
    def test_negative_legacy_opening_blocks(self):
        self.store.db.execute('UPDATE cash_sessions SET opening_cents=-100 WHERE closed_at IS NULL')
        self.assertFalse(inspect(self.store).ready_for_close)
    def test_undated_collected_supplier_cash_blocks(self):
        db=self.store.db
        db.execute("INSERT INTO suppliers(name) VALUES('Supplier')")
        supplier=db.execute('SELECT id FROM suppliers ORDER BY id DESC LIMIT 1').fetchone()[0]
        # Use a valid purchase fixture to satisfy foreign-key constraints.
        db.execute("INSERT INTO purchases(supplier_id,reference,created_at,total_cents,paid_cents) VALUES(?,?,?,?,?)",(supplier,'P46','2099-01-01T00:00:00',1000,0))
        purchase=db.execute('SELECT id FROM purchases ORDER BY id DESC LIMIT 1').fetchone()[0]
        db.execute("""INSERT INTO supplier_settlements(request_key,purchase_id,amount_cents,method,state,created_at,settled_at)
                    VALUES(?,?,?,?,?,?,NULL)""",('v46',purchase,100,'cash','collected','2099-01-01T00:00:00'))
        self.assertTrue(any('lack settlement timestamps' in w for w in inspect(self.store).warnings))
