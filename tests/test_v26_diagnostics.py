import tempfile,unittest
from pathlib import Path
from engine import Store
from diagnostics import inspect,save_json
class DiagnosticTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'store.db';self.store=Store(self.path);self.store.add_product('111','Sucre',10,7,20)
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def test_clean(self):self.assertEqual(inspect(self.path)['total_findings'],0)
 def test_missing_does_not_create(self):
  missing=Path(self.tmp.name)/'missing.db'
  with self.assertRaises(FileNotFoundError):inspect(missing)
  self.assertFalse(missing.exists())
 def test_detects_sale_mismatch(self):
  self.store.sale('one',[('111',2)],20)
  self.store.db.execute('UPDATE sales SET total_cents=1 WHERE request_key=?',('one',))
  self.assertEqual(inspect(self.path)['checks']['sale_total_mismatches'],1)
 def test_json_never_overwrites(self):
  p=Path(self.tmp.name)/'report.json';save_json(inspect(self.path),p)
  with self.assertRaises(FileExistsError):save_json(inspect(self.path),p)
 def test_readonly(self):
  before=self.store.db.execute('SELECT COUNT(*) FROM audit').fetchone()[0];inspect(self.path)
  self.assertEqual(before,self.store.db.execute('SELECT COUNT(*) FROM audit').fetchone()[0])
