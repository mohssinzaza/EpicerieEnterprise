from test_v71_return_overlap import ReturnOverlapTests
from engine import stamp

class RefundIntegrityTests(ReturnOverlapTests):
    def test_full_refund_exceeding_sale_is_unverified(self):
        self.store.db.execute('INSERT INTO sale_returns(sale_id,created_at,refund_cents) VALUES(?,?,?)',(self.sale_id,stamp(),2500))
        report=self.report()
        self.assertFalse(report.complete)
        self.assertIsNone(report.net_profit_cents)
        self.assertTrue(any('cumulative refund' in issue for issue in report.issues))

    def test_partial_refund_exceeding_sale_is_unverified(self):
        db=self.store.db
        rid=db.execute('INSERT INTO partial_returns(sale_id,created_at,refund_cents) VALUES(?,?,?)',(self.sale_id,stamp(),2100)).lastrowid
        db.execute('INSERT INTO partial_return_lines(return_id,sale_line_id,quantity) VALUES(?,?,?)',(rid,self.line_id,1))
        report=self.report()
        self.assertFalse(report.complete)
        self.assertTrue(any('cumulative refund' in issue for issue in report.issues))

    def test_cross_sale_return_line_is_unverified(self):
        db=self.store.db
        self.store.sale('S2',[('A',1)],'10')
        second=db.execute("SELECT id FROM sales WHERE request_key='S2'").fetchone()[0]
        rid=db.execute('INSERT INTO partial_returns(sale_id,created_at,refund_cents) VALUES(?,?,?)',(second,stamp(),100)).lastrowid
        db.execute('INSERT INTO partial_return_lines(return_id,sale_line_id,quantity) VALUES(?,?,?)',(rid,self.line_id,1))
        report=self.report()
        self.assertFalse(report.complete)
        self.assertTrue(any('different sale' in issue for issue in report.issues))
