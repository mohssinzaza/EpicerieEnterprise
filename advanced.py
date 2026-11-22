"""V7: audited partial returns, stock adjustments and operational reports."""
import json
from engine import stamp
from enterprise import EnterpriseStore

class AdvancedStore(EnterpriseStore):
    def __init__(self,path):
        super().__init__(path)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS partial_returns(id INTEGER PRIMARY KEY,sale_id INTEGER NOT NULL REFERENCES sales(id),created_at TEXT NOT NULL,refund_cents INTEGER NOT NULL CHECK(refund_cents>0));
        CREATE TABLE IF NOT EXISTS partial_return_lines(id INTEGER PRIMARY KEY,return_id INTEGER NOT NULL REFERENCES partial_returns(id),sale_line_id INTEGER NOT NULL REFERENCES sale_lines(id),quantity INTEGER NOT NULL CHECK(quantity>0));
        CREATE TABLE IF NOT EXISTS inventory_adjustments(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,product_id INTEGER NOT NULL REFERENCES products(id),delta INTEGER NOT NULL,reason TEXT NOT NULL);
        ''')
        cols={r[1] for r in self.db.execute('PRAGMA table_info(partial_returns)')}
        if 'refund_method' not in cols:
            self.db.execute("ALTER TABLE partial_returns ADD COLUMN refund_method TEXT NOT NULL DEFAULT 'unknown'")
    def return_items(self,sale_id,quantities,refund_method='unknown'):
        """quantities maps sale_line_id to returned units; prevents cumulative overreturns."""
        if refund_method not in ('unknown','cash','bank','cheque'):
            raise ValueError('Invalid refund method')
        if not quantities: raise ValueError('No return lines')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT 1 FROM sale_returns WHERE sale_id=?',(sale_id,)).fetchone(): raise ValueError('Sale fully returned already')
            if not self.db.execute('SELECT 1 FROM sales WHERE id=?',(sale_id,)).fetchone(): raise ValueError('Unknown sale')
            prepared=[];refund=0
            for line_id,qty in quantities.items():
                if type(qty) is not int or qty<=0: raise ValueError('Quantity must be positive integer')
                row=self.db.execute('SELECT product_id,quantity,unit_price_cents FROM sale_lines WHERE id=? AND sale_id=?',(line_id,sale_id)).fetchone()
                if not row: raise ValueError('Line does not belong to sale')
                returned=self.db.execute('SELECT COALESCE(SUM(prl.quantity),0) FROM partial_return_lines prl JOIN partial_returns pr ON pr.id=prl.return_id WHERE prl.sale_line_id=?',(line_id,)).fetchone()[0]
                if qty+returned>row[1]: raise ValueError('Return exceeds quantity sold')
                prepared.append((line_id,row[0],qty));refund+=qty*row[2]
            cur=self.db.execute('INSERT INTO partial_returns(sale_id,created_at,refund_cents,refund_method) VALUES(?,?,?,?)',(sale_id,stamp(),refund,refund_method))
            for line_id,product_id,qty in prepared:
                self.db.execute('INSERT INTO partial_return_lines(return_id,sale_line_id,quantity) VALUES(?,?,?)',(cur.lastrowid,line_id,qty))
                self.db.execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,product_id))
                self.db.execute('INSERT INTO stock_ledger(created_at,product_id,delta,reason,reference) VALUES(?,?,?,?,?)',(stamp(),product_id,qty,'partial_return',str(cur.lastrowid)))
            self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'partial_return',str(cur.lastrowid),json.dumps({'sale_id':sale_id,'refund_cents':refund,'refund_method':refund_method})))
            self.db.execute('COMMIT');return cur.lastrowid,refund
        except BaseException:
            self.db.execute('ROLLBACK');raise
    def return_full_sale(self,sale_id,refund_method='unknown'):
        if self.db.execute('SELECT 1 FROM partial_returns WHERE sale_id=?',(sale_id,)).fetchone():raise ValueError('Partial return exists; return remaining items through partial returns')
        return super().return_full_sale(sale_id,refund_method)
    def adjust_stock(self,barcode,delta,reason):
        if type(delta) is not int or delta==0 or not reason.strip():raise ValueError('Invalid adjustment')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT id,stock FROM products WHERE barcode=?',(barcode,)).fetchone()
            if not row:raise ValueError('Unknown product')
            if row[1]+delta<0:raise ValueError('Stock cannot be negative')
            self.db.execute('UPDATE products SET stock=stock+? WHERE id=?',(delta,row[0]))
            cur=self.db.execute('INSERT INTO inventory_adjustments(created_at,product_id,delta,reason) VALUES(?,?,?,?)',(stamp(),row[0],delta,reason.strip()))
            self.db.execute('INSERT INTO stock_ledger(created_at,product_id,delta,reason,reference) VALUES(?,?,?,?,?)',(stamp(),row[0],delta,'adjustment',str(cur.lastrowid)))
            self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'stock_adjustment',str(cur.lastrowid),json.dumps({'delta':delta,'reason':reason})))
            self.db.execute('COMMIT');return row[1]+delta
        except BaseException:
            self.db.execute('ROLLBACK');raise
    def overview(self):
        scalar=lambda sql:self.db.execute(sql).fetchone()[0]
        gross=scalar('SELECT COALESCE(SUM(total_cents),0) FROM sales')
        full=scalar('SELECT COALESCE(SUM(refund_cents),0) FROM sale_returns')
        partial=scalar('SELECT COALESCE(SUM(refund_cents),0) FROM partial_returns')
        expenses=scalar('SELECT COALESCE(SUM(amount_cents),0) FROM expenses')
        cost=scalar('SELECT COALESCE(SUM(quantity*unit_cost_cents),0) FROM sale_lines')
        returned_cost=scalar('SELECT COALESCE(SUM(sl.quantity*sl.unit_cost_cents),0) FROM sale_lines sl JOIN sale_returns sr ON sr.sale_id=sl.sale_id') + scalar('SELECT COALESCE(SUM(prl.quantity*sl.unit_cost_cents),0) FROM partial_return_lines prl JOIN sale_lines sl ON sl.id=prl.sale_line_id')
        return {'net_sales_cents':gross-full-partial,'estimated_gross_profit_cents':gross-full-partial-cost+returned_cost,'expenses_cents':expenses,'supplier_outstanding_cents':scalar('SELECT COALESCE(SUM(total_cents-paid_cents),0) FROM purchases'),'low_stock_count':scalar('SELECT COUNT(*) FROM products WHERE stock<=5')}
