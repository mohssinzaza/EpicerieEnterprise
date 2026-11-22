import tempfile,unittest
from pathlib import Path
from lot_control import ControlledStore
from lot_costing import record_lot_cost,allocation_costs,costing_summary

class LotCostTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.store=ControlledStore(Path(self.tmp.name)/'cost.db')
  self.store.require=lambda permission:None
  self.store.add_product('A','Article',10,4,0)
  self.store.enable_lot_tracking('A')
  self.lot=self.store.receive_lot('A',5,'R1','L1','2099-12-31')
 def tearDown(self):
  self.store.close();self.tmp.cleanup()
 def test_missing_cost_is_unknown(self):
  self.store.sale('S1',[('A',2)],'20')
  self.assertEqual(costing_summary(self.store)['unknown_quantity'],2)
  self.assertFalse(costing_summary(self.store)['complete'])
 def test_explicit_cost_applies_to_allocations(self):
  record_lot_cost(self.store,self.lot,'3.25','INV-1')
  self.store.sale('S1',[('A',2)],'20')
  self.assertEqual(allocation_costs(self.store)[0].total_cost_cents,650)
  self.assertEqual(costing_summary(self.store)['known_cost_cents'],650)
 def test_cost_is_immutable(self):
  record_lot_cost(self.store,self.lot,'3','INV-1')
  with self.assertRaises(ValueError):record_lot_cost(self.store,self.lot,'4','INV-2')
 def test_invalid_reference_and_lot(self):
  with self.assertRaises(ValueError):record_lot_cost(self.store,self.lot,'3',' ')
  with self.assertRaises(ValueError):record_lot_cost(self.store,999,'3','INV')
 def test_permissions(self):
  self.store.require=lambda p:(_ for _ in ()).throw(PermissionError(p))
  with self.assertRaises(PermissionError):record_lot_cost(self.store,self.lot,'3','INV')
  with self.assertRaises(PermissionError):allocation_costs(self.store)
