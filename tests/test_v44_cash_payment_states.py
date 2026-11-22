import tempfile, unittest
from pathlib import Path
from supplier_accounts import CommercialStore
from cash_reconciliation import inspect
from verified_close import close_verified
from engine import stamp

class PaymentStateReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=CommercialStore(Path(self.tmp.name)/'db.sqlite')
        self.store.bootstrap('admin','very-secure-password-2026')
        self.store.login('admin','very-secure-password-2026')
        self.store.add_product('A','Sugar','10','4',30)
        self.store.open_cash('100')
        self.store.sale('s1',[('A',1)],'10')
    def tearDown(self):
        self.store.close();self.tmp.cleanup()
    def test_normal_session_remains_ready(self):
        self.assertTrue(inspect(self.store).ready_for_close)
    def test_pending_customer_cash_blocks(self):
        db=self.store.db
        db.execute("INSERT INTO customers(name) VALUES('Customer')")
        cid=db.execute('SELECT id FROM customers ORDER BY id DESC LIMIT 1').fetchone()[0]
        sid=db.execute('SELECT id FROM sales LIMIT 1').fetchone()[0]
        db.execute('INSERT INTO customer_invoices(sale_id,customer_id,total_cents,created_at) VALUES(?,?,?,?)',(sid,cid,1000,stamp()))
        iid=db.execute('SELECT id FROM customer_invoices LIMIT 1').fetchone()[0]
        db.execute("INSERT INTO customer_payments(request_key,invoice_id,amount_cents,method,created_at,state) VALUES(?,?,?,?,?,?)",('badcash',iid,100,'cash',stamp(),'pending'))
        self.assertTrue(any('customer cash payment' in w for w in inspect(self.store).warnings))
        with self.assertRaises(ValueError):close_verified(self.store,'100')
    def test_pending_supplier_cash_blocks(self):
        db=self.store.db
        db.execute("INSERT INTO suppliers(name) VALUES('Supplier')")
        supplier=db.execute('SELECT id FROM suppliers LIMIT 1').fetchone()[0]
        db.execute('INSERT INTO purchases(reference,supplier_id,created_at,total_cents,paid_cents) VALUES(?,?,?,?,?)',('p1',supplier,stamp(),1000,0))
        pid=db.execute('SELECT id FROM purchases LIMIT 1').fetchone()[0]
        db.execute("INSERT INTO supplier_settlements(request_key,purchase_id,amount_cents,method,state,created_at,settled_at) VALUES(?,?,?,?,?,?,?)",('bad-supplier',pid,100,'cash','pending',stamp(),stamp()))
        self.assertTrue(any('supplier cash payment' in w for w in inspect(self.store).warnings))
    def test_read_only(self):
        before=self.store.db.total_changes
        inspect(self.store)
        self.assertEqual(before,self.store.db.total_changes)
