"""V10 opt-in lot control: FEFO allocation and expiry blocking for tracked items.
Untracked items retain V9 behaviour. Returns of tracked sales require manual quarantine workflow.
"""
import datetime, json
from engine import cents, stamp
from expiry import ExpiryStore

class ControlledStore(ExpiryStore):
    def __init__(self,path):
        super().__init__(path)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS tracked_products(product_id INTEGER PRIMARY KEY REFERENCES products(id));
        CREATE TABLE IF NOT EXISTS lot_balances(lot_id INTEGER PRIMARY KEY REFERENCES expiry_lots(id),remaining_qty INTEGER NOT NULL CHECK(remaining_qty>=0));
        CREATE TABLE IF NOT EXISTS sale_lot_allocations(id INTEGER PRIMARY KEY,sale_line_id INTEGER NOT NULL REFERENCES sale_lines(id),lot_id INTEGER NOT NULL REFERENCES expiry_lots(id),quantity INTEGER NOT NULL CHECK(quantity>0));
        CREATE INDEX IF NOT EXISTS idx_lot_alloc_line ON sale_lot_allocations(sale_line_id);
        ''')
    def enable_lot_tracking(self,barcode):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            p=self.db.execute('SELECT id,stock FROM products WHERE barcode=?',(barcode,)).fetchone()
            if not p: raise ValueError('Unknown barcode')
            if p[1]!=0: raise ValueError('Lot tracking requires zero stock; reconcile existing stock first')
            if self.db.execute('SELECT 1 FROM expiry_lots WHERE product_id=?',(p[0],)).fetchone():
                raise ValueError('Existing V9 lots must be reconciled before enabling tracking')
            self.db.execute('INSERT OR IGNORE INTO tracked_products(product_id) VALUES(?)',(p[0],))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise
    def receive_lot(self,barcode,qty,reference,lot_code,expiry_date):
        # V9 method is transactional; initialise balance only for explicitly tracked products.
        lot_id=super().receive_lot(barcode,qty,reference,lot_code,expiry_date)
        p=self.db.execute('SELECT product_id FROM expiry_lots WHERE id=?',(lot_id,)).fetchone()
        if self.db.execute('SELECT 1 FROM tracked_products WHERE product_id=?',(p[0],)).fetchone():
            self.db.execute('INSERT INTO lot_balances(lot_id,remaining_qty) VALUES(?,?)',(lot_id,qty))
        return lot_id
    def receive(self,barcode,qty,reference):
        p=self.db.execute('SELECT id FROM products WHERE barcode=?',(barcode,)).fetchone()
        if p and self.db.execute('SELECT 1 FROM tracked_products WHERE product_id=?',(p[0],)).fetchone():
            raise ValueError('Tracked product must be received with lot and expiry date')
        return super().receive(barcode,qty,reference)
    def purchase(self,reference,supplier_id,lines,paid='0',payment_method='unknown'):
        for barcode,qty,cost in lines:
            p=self.db.execute('SELECT id FROM products WHERE barcode=?',(barcode,)).fetchone()
            if p and self.db.execute('SELECT 1 FROM tracked_products WHERE product_id=?',(p[0],)).fetchone():
                raise ValueError('Tracked products must be received through lot receipts; purchase integration pending')
        return super().purchase(reference,supplier_id,lines,paid,payment_method)
    def sale(self,request_key,lines,received):
        if not isinstance(request_key,str) or not request_key.strip() or not lines:raise ValueError('Missing sale key or lines')
        paid=cents(received)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            prior=self.db.execute('SELECT id,total_cents,change_cents FROM sales WHERE request_key=?',(request_key,)).fetchone()
            if prior:self.db.execute('COMMIT');return prior
            quantities={}
            for barcode,qty in lines:
                if type(qty) is not int or qty<=0:raise ValueError('Positive integer quantities only')
                quantities[barcode]=quantities.get(barcode,0)+qty
            prepared=[];total=0;today=datetime.date.today().isoformat()
            for barcode,qty in quantities.items():
                p=self.db.execute('SELECT id,price_cents,cost_cents,stock FROM products WHERE barcode=?',(barcode,)).fetchone()
                if not p:raise ValueError('Unknown barcode: '+str(barcode))
                if p[3]<qty:raise ValueError('Insufficient stock: '+str(barcode))
                allocations=[]
                if self.db.execute('SELECT 1 FROM tracked_products WHERE product_id=?',(p[0],)).fetchone():
                    lots=self.db.execute('''SELECT l.id,b.remaining_qty FROM expiry_lots l JOIN lot_balances b ON b.lot_id=l.id
                        WHERE l.product_id=? AND l.expiry_date>=? AND b.remaining_qty>0 ORDER BY l.expiry_date,l.id''',(p[0],today)).fetchall()
                    remaining=qty
                    for lot_id,available in lots:
                        take=min(remaining,available)
                        if take:allocations.append((lot_id,take));remaining-=take
                        if not remaining:break
                    if remaining:raise ValueError('Insufficient non-expired lot stock: '+str(barcode))
                prepared.append((p,qty,allocations));total+=p[1]*qty
            if paid<total:raise ValueError('Insufficient payment')
            cur=self.db.execute('INSERT INTO sales(request_key,created_at,total_cents,received_cents,change_cents) VALUES(?,?,?,?,?)',(request_key,stamp(),total,paid,paid-total))
            sid=cur.lastrowid
            for p,qty,allocations in prepared:
                self.db.execute('UPDATE products SET stock=stock-? WHERE id=?',(qty,p[0]))
                line=self.db.execute('INSERT INTO sale_lines(sale_id,product_id,quantity,unit_price_cents,unit_cost_cents) VALUES(?,?,?,?,?)',(sid,p[0],qty,p[1],p[2]))
                for lot_id,take in allocations:
                    self.db.execute('UPDATE lot_balances SET remaining_qty=remaining_qty-? WHERE lot_id=?',(take,lot_id))
                    self.db.execute('INSERT INTO sale_lot_allocations(sale_line_id,lot_id,quantity) VALUES(?,?,?)',(line.lastrowid,lot_id,take))
                self.db.execute('INSERT INTO stock_ledger(created_at,product_id,delta,reason,reference) VALUES(?,?,?,?,?)',(stamp(),p[0],-qty,'sale',str(sid)))
            self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'sale_fefo',str(sid),json.dumps({'total_cents':total})))
            self.db.execute('COMMIT');return sid,total,paid-total
        except BaseException:
            self.db.execute('ROLLBACK');raise
    def _has_tracked_sale(self,sale_id):
        return bool(self.db.execute('''SELECT 1 FROM sale_lines sl JOIN tracked_products tp ON tp.product_id=sl.product_id WHERE sl.sale_id=? LIMIT 1''',(sale_id,)).fetchone())
    def return_items(self,sale_id,quantities,refund_method='unknown'):
        if self._has_tracked_sale(sale_id):raise ValueError('Tracked-item returns require quarantine workflow; not yet supported')
        return super().return_items(sale_id,quantities,refund_method)
    def return_full_sale(self,sale_id,refund_method='unknown'):
        if self._has_tracked_sale(sale_id):raise ValueError('Tracked-item returns require quarantine workflow; not yet supported')
        return super().return_full_sale(sale_id,refund_method)
    def adjust_stock(self,barcode,delta,reason):
        p=self.db.execute('SELECT id FROM products WHERE barcode=?',(barcode,)).fetchone()
        if p and self.db.execute('SELECT 1 FROM tracked_products WHERE product_id=?',(p[0],)).fetchone():
            raise ValueError('Tracked-item adjustments require lot-level reconciliation; not yet supported')
        return super().adjust_stock(barcode,delta,reason)
    def lot_inventory(self):
        return self.db.execute('''SELECT p.barcode,p.name,l.lot_code,l.expiry_date,b.remaining_qty FROM lot_balances b JOIN expiry_lots l ON l.id=b.lot_id JOIN products p ON p.id=l.product_id ORDER BY l.expiry_date,l.id''').fetchall()
