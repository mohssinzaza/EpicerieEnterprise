import tempfile,unittest,datetime as dt
from pathlib import Path
from lot_control import ControlledStore
from lot_costing import period_cost_coverage,record_lot_cost

class PeriodCoverageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.store=ControlledStore(Path(self.tmp.name)/'db.sqlite')
  self.store.require=lambda p:None
  self.store.add_product('A','Product',10,4,0)
  self.store.enable_lot_tracking('A')
  self.lot=self.store.receive_lot('A',10,'receipt','LOT','2099-12-31')
 def tearDown(self):
  self.store.close();self.tmp.cleanup()
 def coverage(self):return period_cost_coverage(self.store,'month',dt.date.today(),'UTC')
 def test_known_cost(self):
  record_lot_cost(self.store,self.lot,'3.25','INV')
  self.store.sale('S1',[('A',2)],'20')
  r=self.coverage()
  self.assertEqual((r.sold_quantity,r.known_cost_quantity,r.known_cost_cents,r.complete),(2,2,650,True))
 def test_unknown_cost(self):
  self.store.sale('S1',[('A',2)],'20')
  r=self.coverage();self.assertEqual(r.unknown_cost_quantity,2);self.assertFalse(r.complete)
 def test_missing_allocation(self):
  self.store.sale('S1',[('A',2)],'20')
  self.store.db.execute('DELETE FROM sale_lot_allocations')
  r=self.coverage();self.assertEqual(r.missing_allocation_quantity,2);self.assertFalse(r.complete)
 def test_excess_allocation(self):
  self.store.sale('S1',[('A',2)],'20')
  self.store.db.execute('UPDATE sale_lot_allocations SET quantity=3')
  r=self.coverage();self.assertEqual(r.excess_allocation_quantity,1);self.assertFalse(r.complete)
 def test_empty_is_not_complete(self):
  self.assertFalse(self.coverage().complete)
 def test_permission(self):
  self.store.require=lambda p:(_ for _ in ()).throw(PermissionError(p))
  with self.assertRaises(PermissionError):self.coverage()
