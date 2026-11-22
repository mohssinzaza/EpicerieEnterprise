import datetime as dt
import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from profit_quality import check_profit_quality, export_quality_csv

class ProfitQualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=CommercialStore(Path(self.tmp.name)/'test.sqlite')
        self.store.bootstrap('admin','ThisIsALongTestPassword!')
        self.store.login('admin','ThisIsALongTestPassword!')
        self.day=dt.datetime.now(dt.timezone.utc).date()
    def tearDown(self):
        self.store.close();self.tmp.cleanup()
    def test_empty_period(self):
        q=check_profit_quality(self.store,'day',self.day,'UTC')
        self.assertTrue(q.ready_for_review)
        self.assertEqual(q.operating_profit_cents,0)
    def test_normal_sale(self):
        self.store.add_product('100','Sugar',10,6,20)
        self.store.sale('sale-normal',[('100',2)],20)
        q=check_profit_quality(self.store,'day',self.day,'UTC')
        self.assertTrue(q.ready_for_review)
        self.assertEqual(q.operating_profit_cents,800)
    def test_zero_cost_flag(self):
        self.store.add_product('101','Gift',10,0,20)
        self.store.sale('sale-free',[('101',1)],10)
        q=check_profit_quality(self.store,'day',self.day,'UTC')
        self.assertEqual(q.zero_cost_lines,1)
        self.assertFalse(q.ready_for_review)
    def test_negative_margin_warning(self):
        self.store.add_product('102','Loss',5,7,20)
        self.store.sale('sale-loss',[('102',2)],10)
        q=check_profit_quality(self.store,'day',self.day,'UTC')
        self.assertEqual(q.negative_margin_lines,1)
        self.assertEqual(q.negative_margin_loss_cents,400)
        self.assertTrue(q.ready_for_review)
    def test_missing_lines(self):
        self.store.db.execute("INSERT INTO sales(request_key,created_at,total_cents,received_cents,change_cents) VALUES ('orphan',?,100,100,0)",(dt.datetime.now(dt.timezone.utc).isoformat(),))
        q=check_profit_quality(self.store,'day',self.day,'UTC')
        self.assertEqual(q.missing_line_sales,1)
        self.assertFalse(q.ready_for_review)
    def test_read_only_and_csv_no_overwrite(self):
        before=self.store.db.total_changes
        q=check_profit_quality(self.store,'day',self.day,'UTC')
        self.assertEqual(self.store.db.total_changes,before)
        path=Path(self.tmp.name)/'quality.csv'
        export_quality_csv(q,path)
        self.assertIn('ready_for_review',path.read_text(encoding='utf-8-sig'))
        with self.assertRaises(FileExistsError):export_quality_csv(q,path)
