"""V11: traceable quarantine of lot-tracked customer returns.
No automatic refund or resale: finance and quality decisions remain separate.
"""
import json
from engine import stamp
from lot_control import ControlledStore

class QuarantineStore(ControlledStore):
    def __init__(self,path):
        super().__init__(path)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS quarantine_returns(
          id INTEGER PRIMARY KEY, request_key TEXT NOT NULL UNIQUE,
          sale_id INTEGER NOT NULL REFERENCES sales(id), created_at TEXT NOT NULL,
          reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'QUARANTINED'
          CHECK(status IN ('QUARANTINED','DISPOSED')));
        CREATE TABLE IF NOT EXISTS quarantine_return_lines(
          id INTEGER PRIMARY KEY, return_id INTEGER NOT NULL REFERENCES quarantine_returns(id),
          sale_line_id INTEGER NOT NULL REFERENCES sale_lines(id),
          lot_id INTEGER NOT NULL REFERENCES expiry_lots(id),
          quantity INTEGER NOT NULL CHECK(quantity>0));
        CREATE INDEX IF NOT EXISTS idx_quarantine_line ON quarantine_return_lines(sale_line_id);
        ''')
    def quarantine_return(self,request_key,sale_id,quantities,reason):
        """quantities: {sale_line_id: quantity}; allocate against original sold lots.
        This is a physical intake into quarantine, NOT a financial refund.
        """
        if not isinstance(request_key,str) or not request_key.strip() or not isinstance(reason,str) or not reason.strip() or not quantities:
            raise ValueError('Request key, reason and quantities required')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            prior=self.db.execute('SELECT id FROM quarantine_returns WHERE request_key=?',(request_key,)).fetchone()
            if prior:
                self.db.execute('COMMIT');return prior[0]
            if not self.db.execute('SELECT 1 FROM sales WHERE id=?',(sale_id,)).fetchone():raise ValueError('Unknown sale')
            allocations=[]
            for line_id,qty in quantities.items():
                if type(line_id) is not int or type(qty) is not int or qty<=0:raise ValueError('Invalid line or quantity')
                line=self.db.execute('''SELECT sl.quantity FROM sale_lines sl JOIN tracked_products tp ON tp.product_id=sl.product_id WHERE sl.id=? AND sl.sale_id=?''',(line_id,sale_id)).fetchone()
                if not line:raise ValueError('Line is not a tracked item in this sale')
                already=self.db.execute('SELECT COALESCE(SUM(quantity),0) FROM quarantine_return_lines WHERE sale_line_id=?',(line_id,)).fetchone()[0]
                if already+qty>line[0]:raise ValueError('Return exceeds quantity sold')
                remaining=qty
                for lot_id,sold in self.db.execute('SELECT lot_id,quantity FROM sale_lot_allocations WHERE sale_line_id=? ORDER BY id',(line_id,)):
                    used=self.db.execute('SELECT COALESCE(SUM(quantity),0) FROM quarantine_return_lines WHERE sale_line_id=? AND lot_id=?',(line_id,lot_id)).fetchone()[0]
                    take=min(remaining,sold-used)
                    if take:allocations.append((line_id,lot_id,take));remaining-=take
                    if remaining==0:break
                if remaining:raise ValueError('Insufficient allocated lot quantity')
            cur=self.db.execute('INSERT INTO quarantine_returns(request_key,sale_id,created_at,reason) VALUES(?,?,?,?)',(request_key,sale_id,stamp(),reason.strip()))
            for line_id,lot_id,qty in allocations:
                self.db.execute('INSERT INTO quarantine_return_lines(return_id,sale_line_id,lot_id,quantity) VALUES(?,?,?,?)',(cur.lastrowid,line_id,lot_id,qty))
            self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'quarantine_return',str(cur.lastrowid),json.dumps({'sale_id':sale_id,'quantities':quantities})))
            self.db.execute('COMMIT');return cur.lastrowid
        except BaseException:
            self.db.execute('ROLLBACK');raise
    def dispose_quarantine(self,return_id):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT status FROM quarantine_returns WHERE id=?',(return_id,)).fetchone()
            if not row:raise ValueError('Unknown quarantine return')
            if row[0]!='QUARANTINED':raise ValueError('Already disposed')
            self.db.execute("UPDATE quarantine_returns SET status='DISPOSED' WHERE id=?",(return_id,))
            self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'quarantine_disposed',str(return_id),'{}'))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise
    def quarantine_report(self):
        return self.db.execute('''SELECT qr.id,qr.sale_id,qr.created_at,qr.reason,qr.status,
          COALESCE(SUM(qrl.quantity),0) FROM quarantine_returns qr
          LEFT JOIN quarantine_return_lines qrl ON qrl.return_id=qr.id
          GROUP BY qr.id ORDER BY qr.id DESC''').fetchall()
