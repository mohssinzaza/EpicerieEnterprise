import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_reconciliation import inspect
from engine import stamp

class HistoricalReturnChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=CommercialStore(Path(self.tmp.name)/'shop.db')
        self.addCleanup(self.store.close)
        self.store.bootstrap('admin','very-secure-password-2026')
        self.store.login('admin','very-secure-password-2026')
        self.store.add_product('A','Sugar','10','4',30)
        self.store.open_cash('100')
        self.sale_id,_,_=self.store.sale('sale1',[('A',2)],'20')
        self.line_id=self.store.db.execute('SELECT id FROM sale_lines WHERE sale_id=?',(self.sale_id,)).fetchone()[0]
        # Simulate a sale from a previous cash session.
        self.store.db.execute("UPDATE sales SET created_at='2020-01-01T00:00:00+00:00' WHERE id=?",(self.sale_id,))
    def test_old_sale_over_returned_in_current_session(self):
        db=self.store.db
        db.execute('INSERT INTO partial_returns(sale_id,created_at,refund_cents,refund_method) VALUES(?,?,3000,?)',(self.sale_id,stamp(),'cash'))
        rid=db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO partial_return_lines(return_id,sale_line_id,quantity) VALUES(?,?,?)',(rid,self.line_id,3))
        warnings=inspect(self.store).warnings
        self.assertTrue(any('returned quantities exceeding' in w for w in warnings))
        self.assertTrue(any('refunds exceeding' in w for w in warnings))
    def test_old_sale_valid_partial_return_not_flagged(self):
        db=self.store.db
        db.execute('INSERT INTO partial_returns(sale_id,created_at,refund_cents,refund_method) VALUES(?,?,1000,?)',(self.sale_id,stamp(),'cash'))
        rid=db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO partial_return_lines(return_id,sale_line_id,quantity) VALUES(?,?,?)',(rid,self.line_id,1))
        warnings=inspect(self.store).warnings
        self.assertFalse(any('returned quantities exceeding' in w for w in warnings))
        self.assertFalse(any('refunds exceeding' in w for w in warnings))
