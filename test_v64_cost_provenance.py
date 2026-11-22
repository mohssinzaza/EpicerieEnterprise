import tempfile
import unittest
from pathlib import Path
from enterprise import EnterpriseStore
from cost_provenance import inspect_sale_costs,export_cost_findings

class CostProvenanceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.store=EnterpriseStore(Path(self.temp.name)/'db.sqlite')
  self.store.require=lambda p:None
  self.store.add_product('101','Flour',10,5,10)
 def tearDown(self):
  self.store.close();self.temp.cleanup()
 def test_opening_stock_without_invoice_is_flagged(self):
  self.store.sale('one',[('101',1)],'10')
  self.assertEqual(inspect_sale_costs(self.store)[0].status,'no_prior_purchase_invoice')
 def test_matching_purchase_cost_not_flagged(self):
  supplier=self.store.supplier('Supplier')
  self.store.purchase('INV1',supplier,[('101',3,5)])
  self.store.sale('two',[('101',1)],'10')
  self.assertEqual(inspect_sale_costs(self.store),[])
 def test_different_purchase_cost_flagged(self):
  supplier=self.store.supplier('Supplier')
  self.store.purchase('INV2',supplier,[('101',3,7)])
  self.store.db.execute("UPDATE products SET cost_cents=500 WHERE barcode='101'")
  self.store.sale('three',[('101',1)],'10')
  self.assertEqual(inspect_sale_costs(self.store)[0].status,'differs_from_latest_purchase')
 def test_export_refuses_overwrite(self):
  target=Path(self.temp.name)/'cost.csv'
  export_cost_findings([],target)
  with self.assertRaises(FileExistsError):export_cost_findings([],target)
 def test_permissions(self):
  self.store.require=lambda p:(_ for _ in ()).throw(PermissionError(p))
  with self.assertRaises(PermissionError):inspect_sale_costs(self.store)
