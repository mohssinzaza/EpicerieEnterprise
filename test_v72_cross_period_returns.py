import datetime as dt
from test_v71_return_overlap import ReturnOverlapTests
from engine import stamp

class CrossPeriodReturnTests(ReturnOverlapTests):
    def test_previous_month_partial_then_current_full(self):
        db=self.store.db
        old='2025-01-01T12:00:00+00:00'
        ret=db.execute('INSERT INTO partial_returns(sale_id,created_at,refund_cents) VALUES(?,?,?)',(self.sale_id,old,1000)).lastrowid
        db.execute('INSERT INTO partial_return_lines(return_id,sale_line_id,quantity) VALUES(?,?,?)',(ret,self.line_id,1))
        db.execute('INSERT INTO sale_returns(sale_id,created_at,refund_cents) VALUES(?,?,?)',(self.sale_id,stamp(),2000))
        r=self.report()
        self.assertFalse(r.complete)
        self.assertTrue(any('across periods' in x for x in r.issues))

    def test_previous_month_full_then_current_partial(self):
        db=self.store.db
        db.execute('INSERT INTO sale_returns(sale_id,created_at,refund_cents) VALUES(?,?,?)',(self.sale_id,'2025-01-01T12:00:00+00:00',2000))
        ret=db.execute('INSERT INTO partial_returns(sale_id,created_at,refund_cents) VALUES(?,?,?)',(self.sale_id,stamp(),1000)).lastrowid
        db.execute('INSERT INTO partial_return_lines(return_id,sale_line_id,quantity) VALUES(?,?,?)',(ret,self.line_id,1))
        r=self.report()
        self.assertFalse(r.complete)

    def test_cumulative_partial_returns_exceed_quantity(self):
        db=self.store.db
        for when,quantity in [('2025-01-01T12:00:00+00:00',2),(stamp(),1)]:
            ret=db.execute('INSERT INTO partial_returns(sale_id,created_at,refund_cents) VALUES(?,?,?)',(self.sale_id,when,1000)).lastrowid
            db.execute('INSERT INTO partial_return_lines(return_id,sale_line_id,quantity) VALUES(?,?,?)',(ret,self.line_id,quantity))
        r=self.report()
        self.assertFalse(r.complete)
        self.assertTrue(any('cumulative' in x for x in r.issues))
