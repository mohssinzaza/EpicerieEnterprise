import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_audit import snapshot
from cash_movements import movements
from cash_reconciliation import inspect

class PurchasePaymentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.s=CommercialStore(Path(self.temp.name)/'shop.db')
        self.s.bootstrap('admin','VeryStrongPassword123!')
        self.s.login('admin','VeryStrongPassword123!')
        self.s.add_product('P','Produit','10','4',10)
        self.supplier=self.s.supplier('Fournisseur')
        self.s.open_cash('100')
    def tearDown(self):
        self.s.close();self.temp.cleanup()
    def purchase(self,ref,method):
        return self.s.purchase(ref,self.supplier,[('P',2,'3')],'4',method)
    def test_cash_purchase_reduces_drawer(self):
        self.purchase('cash','cash')
        self.assertEqual(snapshot(self.s).expected_cents,9600)
        self.assertEqual(sum(m.amount_cents for m in movements(self.s)),9600)
        self.assertTrue(inspect(self.s).ready_for_close)
    def test_bank_and_cheque_do_not_reduce_drawer(self):
        self.purchase('bank','bank');self.purchase('cheque','cheque')
        self.assertEqual(snapshot(self.s).expected_cents,10000)
        self.assertTrue(inspect(self.s).ready_for_close)
    def test_unknown_legacy_payment_blocks_close(self):
        self.purchase('old','unknown')
        self.assertFalse(inspect(self.s).ready_for_close)
    def test_invalid_method_is_atomic(self):
        with self.assertRaises(ValueError):self.purchase('invalid','card')
        self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM purchases').fetchone()[0],0)
    def test_method_persists(self):
        self.purchase('cash','cash')
        self.assertEqual(self.s.db.execute('SELECT initial_payment_method FROM purchases').fetchone()[0],'cash')

if __name__=='__main__':unittest.main()
