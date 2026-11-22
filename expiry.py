"""V9 expiry-aware receipt register; advisory only, not lot-level stock allocation."""
import datetime
from engine import stamp
from advanced import AdvancedStore

class ExpiryStore(AdvancedStore):
    def __init__(self,path):
        super().__init__(path)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS expiry_lots (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id),
            lot_code TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            received_qty INTEGER NOT NULL CHECK(received_qty>0),
            received_at TEXT NOT NULL,
            supplier_reference TEXT NOT NULL,
            UNIQUE(product_id,lot_code,supplier_reference)
        );
        CREATE INDEX IF NOT EXISTS expiry_lots_by_date ON expiry_lots(expiry_date);
        ''')
    def receive_lot(self,barcode,qty,reference,lot_code,expiry_date):
        if type(qty) is not int or qty<=0: raise ValueError('Positive integer quantity required')
        if not all(isinstance(x,str) and x.strip() for x in (barcode,reference,lot_code,expiry_date)):
            raise ValueError('Barcode, reference, lot and expiry date required')
        try: date=datetime.date.fromisoformat(expiry_date)
        except ValueError: raise ValueError('Expiry date must be YYYY-MM-DD')
        if date.isoformat()!=expiry_date: raise ValueError('Expiry date must be YYYY-MM-DD')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            product=self.db.execute('SELECT id FROM products WHERE barcode=?',(barcode.strip(),)).fetchone()
            if not product: raise ValueError('Unknown barcode')
            cur=self.db.execute('INSERT INTO expiry_lots(product_id,lot_code,expiry_date,received_qty,received_at,supplier_reference) VALUES(?,?,?,?,?,?)',
                (product[0],lot_code.strip(),expiry_date,qty,stamp(),reference.strip()))
            self.db.execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,product[0]))
            self.db.execute('INSERT INTO stock_ledger(created_at,product_id,delta,reason,reference) VALUES(?,?,?,?,?)',
                (stamp(),product[0],qty,'lot_receipt',str(cur.lastrowid)))
            self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',
                (stamp(),'lot_receipt',str(cur.lastrowid),'{}'))
            self.db.execute('COMMIT')
            return cur.lastrowid
        except BaseException:
            self.db.execute('ROLLBACK');raise
    def expiry_alerts(self,days=30,as_of=None):
        if type(days) is not int or days<0 or days>3650: raise ValueError('Invalid alert horizon')
        today=as_of or datetime.date.today()
        if not isinstance(today,datetime.date): raise ValueError('Invalid date')
        horizon=(today+datetime.timedelta(days=days)).isoformat()
        return self.db.execute('''SELECT l.id,p.barcode,p.name,l.lot_code,l.expiry_date,l.received_qty,
            CASE WHEN l.expiry_date<? THEN 'EXPIRED' ELSE 'SOON' END
            FROM expiry_lots l JOIN products p ON p.id=l.product_id
            WHERE l.expiry_date<=? ORDER BY l.expiry_date,l.id''',(today.isoformat(),horizon)).fetchall()
