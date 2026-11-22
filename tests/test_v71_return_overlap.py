import datetime as dt
import tempfile
import unittest
from pathlib import Path
from security import SecureStore
from engine import stamp
from lot_costing import verified_period_profit, record_lot_cost

class ReturnOverlapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=SecureStore(str(Path(self.tmp.name)/'db.sqlite'))
        self.store.bootstrap('admin','SafePassword!123')
        self.store.login('admin','SafePassword!123')
        self.store.add_product('A','Article',10,4,0)
        self.store.enable_lot_tracking('A')
        lot=self.store.receive_lot('A',5,'INV','LOT','2099-12-31')
        record_lot_cost(self.store,lot,'3','INV')
        self.store.sale('S1',[('A',2)],'20')
        self.sale_id=self.store.db.execute("SELECT id FROM sales WHERE request_key='S1'").fetchone()[0]
        self.line_id=self.store.db.execute('SELECT id FROM sale_lines WHERE sale_id=?',(self.sale_id,)).fetchone()[0]
    def tearDown(self):
        self.store.close();self.tmp.cleanup()
    def report(self):
        return verified_period_profit(self.store,'month',dt.date.today(),'UTC')
    def test_normal_sale_verified(self):
        r=self.report()
        self.assertTrue(r.complete)
        self.assertEqual(r.net_profit_cents,1400)
    def test_full_and_partial_return_same_line_is_unverified(self):
        db=self.store.db
        db.execute('INSERT INTO sale_returns(sale_id,created_at,refund_cents) VALUES(?,?,?)',(self.sale_id,stamp(),2000))
        ret=db.execute('INSERT INTO partial_returns(sale_id,created_at,refund_cents) VALUES(?,?,?)',(self.sale_id,stamp(),1000)).lastrowid
        db.execute('INSERT INTO partial_return_lines(return_id,sale_line_id,quantity) VALUES(?,?,?)',(ret,self.line_id,1))
        r=self.report()
        self.assertFalse(r.complete)
        self.assertIsNone(r.net_profit_cents)
        self.assertTrue(any('overlapping' in issue for issue in r.issues))
