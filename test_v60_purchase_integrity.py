import unittest
from test_v59_purchase_payments import PurchasePaymentTests
from cash_reconciliation import inspect

class PurchaseIntegrityTests(PurchasePaymentTests):
    def test_purchase_total_mismatch_blocks_close(self):
        pid,_=self.purchase('bad-total','cash')
        self.s.db.execute('UPDATE purchases SET total_cents=total_cents+1 WHERE id=?',(pid,))
        self.assertFalse(inspect(self.s).ready_for_close)
        self.assertTrue(any('purchase invoice' in w for w in inspect(self.s).warnings))
    def test_missing_purchase_lines_blocks_close(self):
        pid,_=self.purchase('missing','bank')
        self.s.db.execute('DELETE FROM purchase_lines WHERE purchase_id=?',(pid,))
        self.assertFalse(inspect(self.s).ready_for_close)
    def test_invalid_legacy_payment_method_blocks_close(self):
        pid,_=self.purchase('method','bank')
        self.s.db.execute("UPDATE purchases SET initial_payment_method='invalid' WHERE id=?",(pid,))
        self.assertFalse(inspect(self.s).ready_for_close)

if __name__=='__main__': unittest.main()
