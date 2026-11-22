"""Transactional POS foundation; Python 3.10+, standard library only."""
from contextlib import closing
import sqlite3, datetime, hashlib, json, os
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

def cents(value):
    d=Decimal(str(value))
    if not d.is_finite() or d<0: raise ValueError('Invalid nonnegative amount')
    return int((d*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))

def stamp(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

class Store:
    def __init__(self, path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path,timeout=20,isolation_level=None)
        self.db.execute('PRAGMA foreign_keys=ON');self.db.execute('PRAGMA busy_timeout=20000');self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,barcode TEXT NOT NULL UNIQUE,name TEXT NOT NULL,price_cents INTEGER NOT NULL CHECK(price_cents>=0),cost_cents INTEGER NOT NULL CHECK(cost_cents>=0),stock INTEGER NOT NULL CHECK(stock>=0));
        CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY,request_key TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL,total_cents INTEGER NOT NULL,received_cents INTEGER NOT NULL,change_cents INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sale_lines(id INTEGER PRIMARY KEY,sale_id INTEGER NOT NULL REFERENCES sales(id),product_id INTEGER NOT NULL REFERENCES products(id),quantity INTEGER NOT NULL CHECK(quantity>0),unit_price_cents INTEGER NOT NULL,unit_cost_cents INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS stock_ledger(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,product_id INTEGER NOT NULL REFERENCES products(id),delta INTEGER NOT NULL,reason TEXT NOT NULL,reference TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,action TEXT NOT NULL,reference TEXT NOT NULL,payload TEXT NOT NULL);
        ''')
    def close(self):self.db.close()
    def add_product(self,barcode,name,price,cost,stock=0):
        if not barcode.strip() or not name.strip() or not isinstance(stock,int) or stock<0:raise ValueError('Invalid product')
        with self.db:
            cur=self.db.execute('INSERT INTO products(barcode,name,price_cents,cost_cents,stock) VALUES(?,?,?,?,?)',(barcode.strip(),name.strip(),cents(price),cents(cost),stock))
            if stock:self.db.execute('INSERT INTO stock_ledger(created_at,product_id,delta,reason,reference) VALUES(?,?,?,?,?)',(stamp(),cur.lastrowid,stock,'opening','initial'))
            return cur.lastrowid
    def receive(self,barcode,qty,reference):
        if not isinstance(qty,int) or qty<=0 or not reference:raise ValueError('Invalid receipt')
        with self.db:
            p=self.db.execute('SELECT id FROM products WHERE barcode=?',(barcode,)).fetchone()
            if not p:raise ValueError('Unknown barcode')
            self.db.execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,p[0]))
            self.db.execute('INSERT INTO stock_ledger(created_at,product_id,delta,reason,reference) VALUES(?,?,?,?,?)',(stamp(),p[0],qty,'receipt',reference))
    def sale(self,request_key,lines,received):
        if not request_key or not lines:raise ValueError('Missing sale key or lines')
        received_cents=cents(received)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            prior=self.db.execute('SELECT id,total_cents,change_cents FROM sales WHERE request_key=?',(request_key,)).fetchone()
            if prior:
                self.db.execute('COMMIT');return prior
            quantities={}
            for barcode,qty in lines:
                if not isinstance(qty,int) or qty<=0:raise ValueError('Positive integer quantities only')
                quantities[barcode]=quantities.get(barcode,0)+qty
            prepared=[];total=0
            for barcode,qty in quantities.items():
                p=self.db.execute('SELECT id,price_cents,cost_cents,stock FROM products WHERE barcode=?',(barcode,)).fetchone()
                if not p:raise ValueError('Unknown barcode: '+barcode)
                if p[3]<qty:raise ValueError('Insufficient stock: '+barcode)
                total+=p[1]*qty;prepared.append((p,qty))
            if received_cents<total:raise ValueError('Insufficient payment')
            cur=self.db.execute('INSERT INTO sales(request_key,created_at,total_cents,received_cents,change_cents) VALUES(?,?,?,?,?)',(request_key,stamp(),total,received_cents,received_cents-total))
            sale_id=cur.lastrowid
            for p,qty in prepared:
                self.db.execute('UPDATE products SET stock=stock-? WHERE id=?',(qty,p[0]))
                self.db.execute('INSERT INTO sale_lines(sale_id,product_id,quantity,unit_price_cents,unit_cost_cents) VALUES(?,?,?,?,?)',(sale_id,p[0],qty,p[1],p[2]))
                self.db.execute('INSERT INTO stock_ledger(created_at,product_id,delta,reason,reference) VALUES(?,?,?,?,?)',(stamp(),p[0],-qty,'sale',str(sale_id)))
            self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'sale',str(sale_id),json.dumps({'request_key':request_key,'total_cents':total})))
            self.db.execute('COMMIT');return sale_id,total,received_cents-total
        except BaseException:
            self.db.execute('ROLLBACK');raise
    def backup(self,target):
        target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
        if target.resolve()==self.path.resolve():raise ValueError('Backup path equals active DB')
        temp=target.with_suffix(target.suffix+'.partial')
        if temp.exists():temp.unlink()
        try:
            with closing(sqlite3.connect(temp)) as out:self.db.backup(out)
            with closing(sqlite3.connect(temp)) as verify:
                if verify.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Backup integrity failed')
            os.replace(temp,target)
        finally:
            if temp.exists():temp.unlink()
        return target
