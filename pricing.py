"""V13 tiered sales. Quantities in base units (piece); stock FEFO preserved."""
import datetime,json
from engine import cents,stamp
from security import SecureStore
TIERS=('detail','demi_gros','gros')
class PricingStore(SecureStore):
 def __init__(self,path):
  super().__init__(path)
  self.db.executescript("""CREATE TABLE IF NOT EXISTS product_tiers(product_id INTEGER NOT NULL REFERENCES products(id),tier TEXT NOT NULL CHECK(tier IN ('detail','demi_gros','gros')),price_cents INTEGER NOT NULL CHECK(price_cents>=0),min_qty INTEGER NOT NULL CHECK(min_qty>0),PRIMARY KEY(product_id,tier));
  CREATE TABLE IF NOT EXISTS product_units(product_id INTEGER NOT NULL REFERENCES products(id),unit_name TEXT NOT NULL,units_per_pack INTEGER NOT NULL CHECK(units_per_pack>0),PRIMARY KEY(product_id,unit_name));
  CREATE TABLE IF NOT EXISTS sale_tier_info(sale_line_id INTEGER PRIMARY KEY REFERENCES sale_lines(id),tier TEXT NOT NULL,unit_name TEXT NOT NULL,pack_count INTEGER NOT NULL);""")
 def set_tier(self,barcode,tier,price,min_qty=1):
  self.require('products')
  if tier not in TIERS or type(min_qty)!=int or min_qty<1:raise ValueError('Invalid tier/quantity')
  p=self.db.execute('SELECT id FROM products WHERE barcode=?',(barcode,)).fetchone()
  if not p:raise ValueError('Unknown barcode')
  with self.db:self.db.execute('INSERT INTO product_tiers VALUES(?,?,?,?) ON CONFLICT(product_id,tier) DO UPDATE SET price_cents=excluded.price_cents,min_qty=excluded.min_qty',(p[0],tier,cents(price),min_qty))
 def set_unit(self,barcode,unit_name,units_per_pack):
  self.require('products')
  if not unit_name.strip() or type(units_per_pack)!=int or units_per_pack<1:raise ValueError('Invalid unit')
  p=self.db.execute('SELECT id FROM products WHERE barcode=?',(barcode,)).fetchone()
  if not p:raise ValueError('Unknown barcode')
  with self.db:self.db.execute('INSERT INTO product_units VALUES(?,?,?) ON CONFLICT(product_id,unit_name) DO UPDATE SET units_per_pack=excluded.units_per_pack',(p[0],unit_name.strip(),units_per_pack))
 def tier_catalog(self):
  return self.db.execute('SELECT p.barcode,p.name,t.tier,t.price_cents,t.min_qty FROM product_tiers t JOIN products p ON p.id=t.product_id ORDER BY p.name,t.tier').fetchall()
 def sale_tiered(self,key,lines,received):
  """lines: (barcode, pack_count, unit_name, tier). No mixed-tier consolidation; all changes atomic."""
  self.require('sales')
  if not isinstance(key,str) or not key.strip() or not lines:raise ValueError('Invalid sale')
  paid=cents(received)
  self.db.execute('BEGIN IMMEDIATE')
  try:
   old=self.db.execute('SELECT id,total_cents,change_cents FROM sales WHERE request_key=?',(key,)).fetchone()
   if old:self.db.execute('COMMIT');return old
   prepared=[];total=0;requested={};today=datetime.date.today().isoformat()
   for barcode,count,unit,tier in lines:
    if tier not in TIERS or type(count)!=int or count<1:raise ValueError('Invalid sale line')
    p=self.db.execute('SELECT id,price_cents,cost_cents,stock FROM products WHERE barcode=?',(barcode,)).fetchone()
    if not p:raise ValueError('Unknown barcode')
    if unit=='piece':factor=1
    else:
     u=self.db.execute('SELECT units_per_pack FROM product_units WHERE product_id=? AND unit_name=?',(p[0],unit)).fetchone()
     if not u:raise ValueError('Unknown unit')
     factor=u[0]
    qty=count*factor
    if tier=='detail':
     t=self.db.execute('SELECT price_cents,min_qty FROM product_tiers WHERE product_id=? AND tier=?',(p[0],tier)).fetchone()
     unitprice=t[0] if t else p[1];minimum=t[1] if t else 1
    else:
     t=self.db.execute('SELECT price_cents,min_qty FROM product_tiers WHERE product_id=? AND tier=?',(p[0],tier)).fetchone()
     if not t:raise ValueError('Price tier not configured')
     unitprice,minimum=t
    if qty<minimum:raise ValueError('Minimum quantity for tier not met')
    requested[p[0]]=requested.get(p[0],0)+qty
    prepared.append((p,qty,count,unit,tier,unitprice))
    total+=qty*unitprice
   for pid,qty in requested.items():
    stock=self.db.execute('SELECT stock FROM products WHERE id=?',(pid,)).fetchone()[0]
    if qty>stock:raise ValueError('Insufficient stock')
   if paid<total:raise ValueError('Insufficient payment')
   allocations={}
   for pid,qty in requested.items():
    if not self.db.execute('SELECT 1 FROM tracked_products WHERE product_id=?',(pid,)).fetchone():continue
    remain=qty;selected=[]
    for lot_id,available in self.db.execute('SELECT l.id,b.remaining_qty FROM expiry_lots l JOIN lot_balances b ON b.lot_id=l.id WHERE l.product_id=? AND l.expiry_date>=? AND b.remaining_qty>0 ORDER BY l.expiry_date,l.id',(pid,today)):
     take=min(remain,available)
     if take:selected.append([lot_id,take]);remain-=take
     if remain==0:break
    if remain:raise ValueError('Insufficient non-expired lot stock')
    allocations[pid]=selected
   sid=self.db.execute('INSERT INTO sales(request_key,created_at,total_cents,received_cents,change_cents) VALUES(?,?,?,?,?)',(key,stamp(),total,paid,paid-total)).lastrowid
   for p,qty,count,unit,tier,unitprice in prepared:
    pid=p[0]
    self.db.execute('UPDATE products SET stock=stock-? WHERE id=?',(qty,pid))
    lineid=self.db.execute('INSERT INTO sale_lines(sale_id,product_id,quantity,unit_price_cents,unit_cost_cents) VALUES(?,?,?,?,?)',(sid,pid,qty,unitprice,p[2])).lastrowid
    self.db.execute('INSERT INTO sale_tier_info VALUES(?,?,?,?)',(lineid,tier,unit,count))
    pending=qty
    for entry in allocations.get(pid,[]):
     take=min(pending,entry[1]);pending-=take;entry[1]-=take
     if take:
      self.db.execute('UPDATE lot_balances SET remaining_qty=remaining_qty-? WHERE lot_id=?',(take,entry[0]))
      self.db.execute('INSERT INTO sale_lot_allocations(sale_line_id,lot_id,quantity) VALUES(?,?,?)',(lineid,entry[0],take))
     if pending==0:break
    self.db.execute('INSERT INTO stock_ledger(created_at,product_id,delta,reason,reference) VALUES(?,?,?,?,?)',(stamp(),pid,-qty,'sale_tiered',str(sid)))
   self.db.execute('INSERT INTO audit(created_at,action,reference,payload) VALUES(?,?,?,?)',(stamp(),'sale_tiered',str(sid),json.dumps({'total_cents':total})))
   self.db.execute('COMMIT');return sid,total,paid-total
  except BaseException:
   self.db.execute('ROLLBACK');raise
