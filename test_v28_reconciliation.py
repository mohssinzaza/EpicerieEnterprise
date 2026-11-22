import datetime
import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from profit_reports import reconcile_product_profits,export_reconciliation_csv

class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=CommercialStore(Path(self.tmp.name)/'test.db')
        self.store.bootstrap('admin','ThisIsALongTestPassword!')
        self.store.login('admin','ThisIsALongTestPassword!')
        self.store.add_product('111','Sugar',10,6,20)
    def tearDown(self):
        self.store.close();self.tmp.cleanup()
    def today(self):
        return datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    def test_empty_balanced(self):
        r=reconcile_product_profits(self.store,'day','2020-01-01','UTC')
        self.assertTrue(r.balanced)
    def test_sale_balanced(self):
        self.store.sale('recon1',[('111',2)],20)
        r=reconcile_product_profits(self.store,'day',self.today(),'UTC')
        self.assertEqual((r.booked_gross_profit_cents,r.products_gross_profit_cents),(800,800))
        self.assertTrue(r.balanced)
    def test_full_return_balanced(self):
        sid,_,_=self.store.sale('recon2',[('111',2)],20)
        self.store.return_full_sale(sid)
        self.assertTrue(reconcile_product_profits(self.store,'day',self.today(),'UTC').balanced)
    def test_discrepancy_detected(self):
        self.store.sale('recon3',[('111',2)],20)
        self.store.db.execute('UPDATE sales SET total_cents=total_cents-100')
        r=reconcile_product_profits(self.store,'day',self.today(),'UTC')
        self.assertFalse(r.balanced)
        self.assertEqual(r.revenue_difference_cents,-100)
        self.assertEqual(r.gross_profit_difference_cents,-100)
    def test_export(self):
        r=reconcile_product_profits(self.store,'day','2020-01-01','UTC')
        path=Path(self.tmp.name)/'reconciliation.csv'
        export_reconciliation_csv(r,path)
        self.assertIn('gross_profit_difference_cents',path.read_text(encoding='utf-8-sig'))
    def test_invalid_period(self):
        with self.assertRaises(ValueError):
            reconcile_product_profits(self.store,'year',self.today(),'UTC')
