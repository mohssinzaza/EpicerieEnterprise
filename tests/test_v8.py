import tempfile,unittest
from pathlib import Path
from advanced import AdvancedStore
from receipts import receipt_html,save_receipt
class ReceiptTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=AdvancedStore(Path(self.tmp.name)/'data.db')
  self.store.add_product('123','<milk & sugar>',12.5,8,10)
  self.sale_id,_,_=self.store.sale('sale-1',[('123',2)],30)
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def test_receipt_escapes_html(self):
  html=receipt_html(self.store,self.sale_id,'<script>bad</script>')
  self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html)
  self.assertIn('&lt;milk &amp; sugar&gt;',html)
 def test_amounts(self):
  html=receipt_html(self.store,self.sale_id)
  self.assertIn('25.00 DH',html);self.assertIn('5.00 DH',html)
 def test_missing_sale(self):
  with self.assertRaises(ValueError):receipt_html(self.store,999)
 def test_save(self):
  path=save_receipt(self.store,self.sale_id,Path(self.tmp.name)/'tickets')
  self.assertTrue(path.is_file());self.assertIn('charset="utf-8"',path.read_text(encoding='utf-8'))
if __name__=='__main__':unittest.main()
