from test_v71_return_overlap import ReturnOverlapTests
from engine import stamp

class ReturnLineCoverageTests(ReturnOverlapTests):
    def test_partial_refund_without_lines_is_unverified(self):
        self.store.db.execute('INSERT INTO partial_returns(sale_id,created_at,refund_cents) VALUES(?,?,?)',
                              (self.sale_id,stamp(),100))
        report=self.report()
        self.assertFalse(report.complete)
        self.assertIsNone(report.net_profit_cents)
        self.assertTrue(any('missing itemized' in issue for issue in report.issues))

    def test_partial_refund_with_itemized_line_is_not_flagged_as_missing(self):
        rid=self.store.db.execute('INSERT INTO partial_returns(sale_id,created_at,refund_cents) VALUES(?,?,?)',
                                  (self.sale_id,stamp(),100)).lastrowid
        self.store.db.execute('INSERT INTO partial_return_lines(return_id,sale_line_id,quantity) VALUES(?,?,?)',
                              (rid,self.line_id,1))
        report=self.report()
        self.assertFalse(any('missing itemized' in issue for issue in report.issues))
