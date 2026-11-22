import tempfile
import unittest
from pathlib import Path
from enterprise import EnterpriseStore
from inventory_reconciliation import reconcile_stock,export_stock_differences

class InventoryReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=EnterpriseStore(Path(self.tmp.name)/'test.db')
        self.store.require=lambda permission: None
        self.store.add_product('100','Rice',10,5,12)
    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()
    def test_balanced_opening(self):
        self.assertEqual(reconcile_stock(self.store),[])
    def test_detects_mismatch_without_mutation(self):
        self.store.db.execute("UPDATE products SET stock=stock+3 WHERE barcode='100'")
        issues=reconcile_stock(self.store)
        self.assertEqual((issues[0].stock,issues[0].ledger_stock,issues[0].difference),(15,12,3))
        self.assertEqual(reconcile_stock(self.store),issues)
    def test_purchase_sale_remain_balanced(self):
        self.store.sale('unique',[('100',2)],'20')
        self.assertEqual(reconcile_stock(self.store),[])
    def test_export_no_overwrite(self):
        target=Path(self.tmp.name)/'audit.csv'
        export_stock_differences(reconcile_stock(self.store),target)
        with self.assertRaises(FileExistsError):export_stock_differences([],target)
    def test_permissions(self):
        self.store.require=lambda permission: (_ for _ in ()).throw(PermissionError(permission))
        with self.assertRaises(PermissionError):reconcile_stock(self.store)

if __name__=='__main__':unittest.main()
