import csv, tempfile, unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_movements import movements, export_movements_csv
from cash_audit import snapshot

class MovementTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.store=CommercialStore(Path(self.tmp.name)/'db.sqlite')
  self.store.bootstrap('admin','very-secure-password-2026')
  self.store.login('admin','very-secure-password-2026')
  self.store.add_product('A','Sugar','10','4',30)
  self.store.open_cash('100')
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def test_opening_only(self):
  rows=movements(self.store)
  self.assertEqual(len(rows),1)
  self.assertEqual(rows[0].amount_cents,10000)
 def test_sale_reconciles(self):
  self.store.sale('s1',[('A',2)],'20')
  self.assertEqual(sum(x.amount_cents for x in movements(self.store)),snapshot(self.store).expected_cents)
  self.assertEqual([x.amount_cents for x in movements(self.store) if x.source=='cash_sale'],[2000])
 def test_export_and_no_overwrite(self):
  target=Path(self.tmp.name)/'cash.csv'
  export_movements_csv(self.store,target)
  with target.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.reader(f))
  self.assertTrue(any(r[0]=='EXPECTED / المتوقع' for r in rows))
  with self.assertRaises(FileExistsError):export_movements_csv(self.store,target)
 def test_read_only(self):
  before=self.store.db.total_changes
  movements(self.store)
  self.assertEqual(self.store.db.total_changes,before)
 def test_invalid_extension(self):
  with self.assertRaises(ValueError):export_movements_csv(self.store,Path(self.tmp.name)/'cash.txt')
