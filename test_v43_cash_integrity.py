import tempfile, unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_reconciliation import inspect
from verified_close import close_verified

class CashPaymentIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=CommercialStore(Path(self.temp.name)/'db.sqlite')
        self.store.bootstrap('admin','very-secure-password-2026')
        self.store.login('admin','very-secure-password-2026')
        self.store.add_product('A','Sugar','10','4',30)
        self.store.open_cash('100')
        self.sale_id,_,_=self.store.sale('s1',[('A',2)],'30')
    def tearDown(self):
        self.store.close();self.temp.cleanup()
    def test_correct_tender_change(self):
        self.assertTrue(inspect(self.store).ready_for_close)
    def test_tender_change_mismatch_blocks_close(self):
        self.store.db.execute('UPDATE sales SET change_cents=0 WHERE id=?',(self.sale_id,))
        self.assertTrue(any('received/change' in x for x in inspect(self.store).warnings))
        with self.assertRaisesRegex(ValueError,'received/change'):
            close_verified(self.store,'120')
    def test_negative_tender_detected(self):
        self.store.db.execute('UPDATE sales SET received_cents=-1 WHERE id=?',(self.sale_id,))
        self.assertFalse(inspect(self.store).ready_for_close)
    def test_excessive_refund_detected(self):
        self.store.db.execute("INSERT INTO partial_returns(sale_id,created_at,refund_cents) VALUES(?,datetime('now'),?)",(self.sale_id,2100))
        self.assertTrue(any('refunds exceeding' in x for x in inspect(self.store).warnings))
    def test_read_only(self):
        before=self.store.db.total_changes
        inspect(self.store)
        self.assertEqual(before,self.store.db.total_changes)
