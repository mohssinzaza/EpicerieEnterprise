import datetime as dt
import tempfile,unittest
from pathlib import Path
from lot_control import ControlledStore
from lot_costing import record_lot_cost,verified_sales_margin

class VerifiedMarginTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.store=ControlledStore(Path(self.temp.name)/'db.sqlite')
  self.store.require=lambda permission:None
  self.store.add_product('A','Product',10,4,0)
  self.store.enable_lot_tracking('A')
  self.lot=self.store.receive_lot('A',10,'R1','L1','2099-12-31')
 def tearDown(self):
  self.store.close();self.temp.cleanup()
 def report(self):return verified_sales_margin(self.store,'month',dt.date.today(),'UTC')
 def test_margin_from_actual_cost(self):
  record_lot_cost(self.store,self.lot,'3.25','INV')
  self.store.sale('S1',[('A',2)],'20')
  r=self.report()
  self.assertTrue(r.complete)
  self.assertEqual((r.sales_cents,r.known_cogs_cents,r.gross_margin_cents),(2000,650,1350))
 def test_unknown_cost_never_claims_profit(self):
  self.store.sale('S1',[('A',2)],'20')
  self.assertIsNone(self.report().gross_margin_cents)
 def test_missing_allocation_never_claims_profit(self):
  record_lot_cost(self.store,self.lot,'3','INV')
  self.store.sale('S1',[('A',2)],'20')
  self.store.db.execute('DELETE FROM sale_lot_allocations')
  self.assertIsNone(self.report().gross_margin_cents)
 def test_no_sales_not_verified(self):
  self.assertFalse(self.report().complete)
 def test_permission(self):
  self.store.require=lambda p:(_ for _ in ()).throw(PermissionError(p))
  with self.assertRaises(PermissionError):self.report()
