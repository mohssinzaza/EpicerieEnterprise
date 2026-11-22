import tempfile
import unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_reconciliation import inspect
from engine import stamp

class ReturnQuantityIntegrityTests(unittest.TestCase):
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
    def insert_return(self,qty,ref='1'):
        db=self.store.db
        db.execute("INSERT INTO partial_returns(sale_id,created_at,refund_cents,refund_method) VALUES(?,?,100,'cash')",(self.sale_id,stamp()))
        rid=db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO partial_return_lines(return_id,sale_line_id,quantity) VALUES(?,?,?)',(rid,self.line_id,qty))
        return rid
    def test_over_returned_quantity(self):
        self.insert_return(3)
        self.assertTrue(any('returned quantities exceeding' in w for w in inspect(self.store).warnings))
    def test_multiple_returns_cumulative(self):
        self.insert_return(1)
        self.insert_return(2)
        self.assertFalse(inspect(self.store).ready_for_close)
    def test_valid_return_quantity(self):
        self.insert_return(1)
        self.assertFalse(any('returned quantities exceeding' in w for w in inspect(self.store).warnings))
    def test_missing_return_lines(self):
        self.store.db.execute("INSERT INTO partial_returns(sale_id,created_at,refund_cents,refund_method) VALUES(?,?,100,'cash')",(self.sale_id,stamp()))
        self.assertTrue(any('have no item lines' in w for w in inspect(self.store).warnings))
