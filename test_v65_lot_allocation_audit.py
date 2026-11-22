import tempfile, unittest
from pathlib import Path
from lot_control import ControlledStore
from lot_allocation_audit import audit_lot_allocations,export_lot_issues

class LotAllocationAuditTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.store=ControlledStore(Path(self.tmp.name)/'test.db')
  self.store.require=lambda permission:None
  self.store.add_product('100','Oil',10,4,0)
  self.store.enable_lot_tracking('100')
  self.lot=self.store.receive_lot('100',5,'receipt','LOT1','2099-01-01')
 def tearDown(self):
  self.store.close();self.tmp.cleanup()
 def test_valid_lot_and_sale(self):
  self.store.sale('sale1',[('100',2)],'20')
  self.assertEqual(audit_lot_allocations(self.store),[])
 def test_lot_balance_corruption(self):
  self.store.db.execute('UPDATE lot_balances SET remaining_qty=4 WHERE lot_id=?',(self.lot,))
  self.assertIn('lot_balance_mismatch',[x.kind for x in audit_lot_allocations(self.store)])
 def test_missing_sale_allocation(self):
  self.store.sale('sale1',[('100',2)],'20')
  self.store.db.execute('DELETE FROM sale_lot_allocations')
  self.assertIn('sale_allocation_mismatch',[x.kind for x in audit_lot_allocations(self.store)])
 def test_missing_balance(self):
  self.store.db.execute('DELETE FROM lot_balances WHERE lot_id=?',(self.lot,))
  self.assertIn('missing_lot_balance',[x.kind for x in audit_lot_allocations(self.store)])
 def test_export_no_overwrite(self):
  path=Path(self.tmp.name)/'lots.csv'
  export_lot_issues([],path)
  with self.assertRaises(FileExistsError):export_lot_issues([],path)
 def test_permissions(self):
  self.store.require=lambda p:(_ for _ in ()).throw(PermissionError(p))
  with self.assertRaises(PermissionError):audit_lot_allocations(self.store)
