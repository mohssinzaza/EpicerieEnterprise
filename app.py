# Windows packaged executable smoke check, before any GUI or shop database opens.
import sys as _startup_sys
if len(_startup_sys.argv) == 3 and _startup_sys.argv[1] == '--self-test':
    from runtime_selftest import run_self_test as _run_self_test
    raise SystemExit(_run_self_test(_startup_sys.argv[2]))
from receipts import save_receipt
"""Épicerie Enterprise V14: standard-library Windows POS demonstration."""
import os, uuid, datetime, tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog
from engine import cents
from security import PERMISSIONS
from supplier_accounts import CommercialStore
from customer_reports import CustomerReports
from profit_quality import check_profit_quality, export_quality_csv
from profit_reports import reconcile_product_profits, export_reconciliation_csv, calculate as calculate_profit, export_csv as export_profit_csv, compare_periods, product_profit_report, export_product_profit_csv, monthly_profit_trend, export_monthly_trend_csv

DATA = Path(os.getenv('LOCALAPPDATA') or Path.home()) / 'EpicerieEnterpriseV11'
DATA.mkdir(parents=True, exist_ok=True)
store = CommercialStore(DATA/'enterprise_v14.db')
customer_reports=CustomerReports(store)
root=tk.Tk();root.title('Épicerie Enterprise V97 | نظام تسيير المواد الغذائية');root.geometry('1080x740');root.minsize(900,620)
root.withdraw()
from tkinter import simpledialog
try:
 if not store.has_users():
  messagebox.showinfo('First setup / الإعداد الأول','Create the first administrator account. Password: at least 12 characters.')
  username=simpledialog.askstring('Admin / المدير','Administrator username:',parent=root)
  password=simpledialog.askstring('Admin / المدير','New password (12+ characters):',show='*',parent=root)
  if username is None or password is None:raise SystemExit('Setup cancelled')
  store.bootstrap(username,password)
 username=simpledialog.askstring('Connexion / دخول','Username / اسم المستخدم:',parent=root)
 password=simpledialog.askstring('Connexion / دخول','Password / كلمة المرور:',show='*',parent=root)
 if username is None or password is None:raise SystemExit('Login cancelled')
 store.login(username,password)
except Exception as exc:
 messagebox.showerror('Access / الدخول',str(exc));store.close();root.destroy();raise SystemExit(1)
root.deiconify()
style=ttk.Style();style.theme_use('clam');style.configure('Treeview',rowheight=29);style.configure('TButton',padding=7)
lang=tk.StringVar(value='العربية');top=ttk.Frame(root,padding=12);top.pack(fill='x');ttk.Label(top,text='ÉPICERIE ENTERPRISE V97',font=('Segoe UI',20,'bold')).pack(side='left');ttk.Combobox(top,textvariable=lang,values=['العربية','Français'],state='readonly',width=15).pack(side='right')
def change_my_password():
 try:
  old=simpledialog.askstring('Sécurité / الأمان','Current password / كلمة المرور الحالية:',show='*',parent=root)
  if old is None:return
  new=simpledialog.askstring('Sécurité / الأمان','New password (12+ characters):',show='*',parent=root)
  if new is None:return
  store.change_own_password(old,new)
  messagebox.showinfo('OK','Password changed / تم تغيير كلمة المرور')
 except Exception as exc:messagebox.showerror('Erreur / خطأ',str(exc))
ttk.Button(top,text='تغيير كلمة المرور / Mot de passe',command=change_my_password).pack(side='right',padx=8)

# V33: lock the entire GUI without ending the application. The session is
# invalidated in the store before the password prompt is shown.
def lock_session():
 username=store.current_user[1] if store.current_user else None
 store.logout()
 root.withdraw()
 while True:
  password=simpledialog.askstring('Verrouillé / مقفل',
   'Password for '+str(username)+' / كلمة مرور '+str(username),
   show='*',parent=root)
  if password is None:
   store.close();root.destroy();raise SystemExit('Session closed')
  try:
   role=store.login(username,password)
   if role not in ('admin','cashier'):
    store.logout();raise PermissionError('Unauthorized role')
   root.deiconify()
   root.lift()
   return
  except Exception as exc:
   messagebox.showerror('Accès refusé / الدخول مرفوض',str(exc),parent=root)

ttk.Button(top,text='قفل الجلسة / Verrouiller',command=lock_session).pack(side='right',padx=8)

notebook=ttk.Notebook(root);notebook.pack(fill='both',expand=True,padx=10,pady=6)
names=[('catalog','المنتجات','Produits'),('pos','الصندوق','Caisse'),('receipt','المشتريات / الاستلام','Réceptions'),('history','سجل العمليات','Historique'),('suppliers','الموردون والمشتريات','Fournisseurs / Achats'),('finance','المالية والصندوق','Finances / Caisse'),('inventory','الجرد والمرتجعات','Inventaire / Retours'),('expiry','دفعات الصلاحية','Lots / Péremption'),('reports','التقارير','Rapports'),('profits','الأرباح','Bénéfices'),('backup','النسخ الاحتياطي','Sauvegarde')]
pages={}
for key,ar,fr in names:
 f=ttk.Frame(notebook,padding=12);pages[key]=f;notebook.add(f,text=ar)
def translate(*_):
 for i,(_,ar,fr) in enumerate(names):notebook.tab(i,text=ar if lang.get()=='العربية' else fr)
lang.trace_add('write',translate)
def field(parent,title,default='',width=20):
 f=ttk.Frame(parent);f.pack(side='left',padx=5,pady=5);ttk.Label(f,text=title).pack(anchor='w');v=tk.StringVar(value=default);ttk.Entry(f,textvariable=v,width=width).pack();return v
def grid(parent,columns):
 frame=ttk.Frame(parent);frame.pack(fill='both',expand=True,pady=9);t=ttk.Treeview(frame,columns=columns,show='headings');sb=ttk.Scrollbar(frame,command=t.yview);t.configure(yscrollcommand=sb.set)
 for col in columns:t.heading(col,text=col);t.column(col,width=130,anchor='center')
 t.pack(side='left',fill='both',expand=True);sb.pack(side='right',fill='y');return t
def fill(tree,rows):
 tree.delete(*tree.get_children())
 for row in rows:tree.insert('','end',values=row)
def show_error(ex):messagebox.showerror('Erreur / خطأ',str(ex))
def money(n):return f'{n/100:.2f}'
# Products
f=pages['catalog'];r=ttk.Frame(f);r.pack(fill='x');barcode=field(r,'Barcode');name=field(r,'Nom / الاسم');price=field(r,'Prix vente DH','0');cost=field(r,'Coût achat DH','0');stock=field(r,'Stock initial','0',12)
product_table=grid(f,['ID','Barcode','Nom','Vente DH','Achat DH','Stock'])
def refresh_products():
 # Never fetch purchase costs for a cashier session.
 if store.current_user[2]=='cashier':
  fill(product_table,[(p[0],p[1],p[2],money(p[3]),'***',p[4]) for p in store.db.execute('SELECT id,barcode,name,price_cents,stock FROM products ORDER BY name')])
 else:
  fill(product_table,[(p[0],p[1],p[2],money(p[3]),money(p[4]),p[5]) for p in store.db.execute('SELECT id,barcode,name,price_cents,cost_cents,stock FROM products ORDER BY name')])
def add_product():
 try:
  store.add_product(barcode.get(),name.get(),price.get(),cost.get(),int(stock.get()));refresh_products();barcode.set('');name.set('');messagebox.showinfo('OK','Produit ajouté / تمت إضافة السلعة')
 except Exception as e:show_error(e)
ttk.Button(r,text='إضافة / Ajouter',command=add_product).pack(side='left',padx=7,pady=12)
# POS
f=pages['pos'];r=ttk.Frame(f);r.pack(fill='x');sale_code=field(r,'Barcode',width=30);sale_qty=field(r,'Quantité / الكمية','1',10);basket={};basket_table=grid(f,['Barcode','Nom','Qté','Prix DH','Total DH']);total_label=tk.StringVar(value='Total: 0.00 DH')
def refresh_basket():
 rows=[];total=0
 for code,qty in basket.items():
  p=store.db.execute('SELECT name,price_cents FROM products WHERE barcode=?',(code,)).fetchone()
  if p:rows.append((code,p[0],qty,money(p[1]),money(p[1]*qty)));total+=p[1]*qty
 fill(basket_table,rows);total_label.set(f'Total: {money(total)} DH')
def scan(_=None):
 try:
  code=sale_code.get().strip();q=int(sale_qty.get())
  if q<=0:raise ValueError('Quantité positive requise')
  if not store.db.execute('SELECT 1 FROM products WHERE barcode=?',(code,)).fetchone():raise ValueError('Barcode inconnu / باركود غير موجود')
  basket[code]=basket.get(code,0)+q;sale_code.set('');refresh_basket()
 except Exception as e:show_error(e)
ttk.Button(r,text='إضافة / Ajouter',command=scan).pack(side='left',padx=8,pady=12)
sale_entry=r.winfo_children()[0].winfo_children()[1];sale_entry.bind('<Return>',scan)
bottom=ttk.Frame(f);bottom.pack(fill='x');ttk.Label(bottom,textvariable=total_label,font=('Segoe UI',18,'bold')).pack(side='left',padx=10);received=field(bottom,'Reçu / المستلم DH','0',12)
def finish_sale():
 try:
  if not basket:raise ValueError('Panier vide / السلة فارغة')
  sale_id,total,change=store.sale(str(uuid.uuid4()),list(basket.items()),received.get());basket.clear();ticket_id.set(str(sale_id));refresh_basket();refresh_products();refresh_history();messagebox.showinfo('Vente validée',f'Facture #{sale_id}\nTotal: {money(total)} DH\nMonnaie / الباقي: {money(change)} DH')
 except Exception as e:show_error(e)
def remove_line():
 selection=basket_table.selection()
 if selection:
  code=basket_table.item(selection[0],'values')[0];basket.pop(code,None);refresh_basket()
ttk.Button(bottom,text='Supprimer ligne / حذف',command=remove_line).pack(side='left',padx=5);ttk.Button(bottom,text='تأكيد البيع / Valider',command=finish_sale).pack(side='right',padx=8)
# Printable offline tickets (browser print / Save as PDF)
receipt_controls=ttk.Frame(pages['pos']);receipt_controls.pack(fill='x',pady=6)
ticket_id=field(receipt_controls,'N° ticket / رقم الوصل','1',10)
def print_ticket():
 try:
  import webbrowser
  output=Path.home()/'Documents'/'EpicerieEnterprise'/'Tickets'
  path=save_receipt(store,int(ticket_id.get()),output)
  webbrowser.open(path.as_uri())
  messagebox.showinfo('Ticket / وصل',f'{path}\nImprimer avec Ctrl+P / اطبع بواسطة Ctrl+P')
 except Exception as e:show_error(e)
ttk.Button(receipt_controls,text='طباعة الوصل / Imprimer ticket',command=print_ticket).pack(side='left',padx=8)
# Receipts
f=pages['receipt'];r=ttk.Frame(f);r.pack(fill='x');rec_code=field(r,'Barcode');rec_qty=field(r,'Quantité','1',10);rec_ref=field(r,'Référence facture / رقم الفاتورة')
def receive():
 try:store.receive(rec_code.get().strip(),int(rec_qty.get()),rec_ref.get().strip());refresh_products();refresh_history();messagebox.showinfo('OK','Réception enregistrée / تم الاستلام')
 except Exception as e:show_error(e)
ttk.Button(r,text='استلام / Réceptionner',command=receive).pack(side='left',padx=5,pady=12)
ttk.Label(f,text='تسجيل دخول البضائع مع مرجع فاتورة المورد. لا يُنشئ هذا القسم بعد حسابات دائنية للموردين.').pack(anchor='w',pady=12)
# History
f=pages['history'];history_table=grid(f,['ID','Date UTC','Barcode','Variation','Motif','Référence'])
def refresh_history():
 fill(history_table,store.db.execute('SELECT l.id,l.created_at,p.barcode,l.delta,l.reason,l.reference FROM stock_ledger l JOIN products p ON p.id=l.product_id ORDER BY l.id DESC LIMIT 500').fetchall())
# Supplier purchasing and finance — V6
f=pages['suppliers'];r=ttk.Frame(f);r.pack(fill='x');supplier_name=field(r,'المورد / Fournisseur');supplier_phone=field(r,'Téléphone',width=15)
def create_supplier():
 try:store.supplier(supplier_name.get(),supplier_phone.get());refresh_suppliers();messagebox.showinfo('OK','Fournisseur enregistré')
 except Exception as e:show_error(e)
ttk.Button(r,text='إضافة مورد / Ajouter',command=create_supplier).pack(side='left',padx=5)
supplier_table=grid(f,['ID','Fournisseur','Téléphone'])
def refresh_suppliers():fill(supplier_table,store.db.execute('SELECT id,name,phone FROM suppliers ORDER BY id DESC').fetchall())
r=ttk.Frame(f);r.pack(fill='x');purchase_ref=field(r,'Référence');purchase_supplier=field(r,'ID fournisseur','1',10);purchase_barcode=field(r,'Barcode');purchase_qty=field(r,'Qté','1',7);purchase_cost=field(r,'Coût DH','0',9);purchase_paid=field(r,'Payé DH','0',9);purchase_method=ttk.Combobox(r,values=['cash','bank','cheque'],state='readonly',width=9);purchase_method.set('cash');purchase_method.pack(side='left',padx=5)
def create_purchase():
 try:
  pid,total=store.purchase(purchase_ref.get(),int(purchase_supplier.get()),[(purchase_barcode.get(),int(purchase_qty.get()),purchase_cost.get())],purchase_paid.get(),purchase_method.get());refresh_products();refresh_history();messagebox.showinfo('OK',f'Achat #{pid}: {money(total)} DH')
 except Exception as e:show_error(e)
ttk.Button(r,text='تسجيل الشراء / Acheter',command=create_purchase).pack(side='left',padx=5)
f=pages['finance'];r=ttk.Frame(f);r.pack(fill='x');expense_category=field(r,'Catégorie','Loyer');expense_description=field(r,'Description');expense_amount=field(r,'Montant DH','0',12);expense_method=ttk.Combobox(r,values=['cash','bank','cheque'],state='readonly',width=10);expense_method.set('cash');expense_method.pack(side='left',padx=5)
def create_expense():
 try:store.expense(expense_category.get(),expense_description.get(),expense_amount.get(),expense_method.get());messagebox.showinfo('OK','Dépense enregistrée')
 except Exception as e:show_error(e)
ttk.Button(r,text='مصروف / Dépense',command=create_expense).pack(side='left',padx=5)
r=ttk.Frame(f);r.pack(fill='x');cash_amount=field(r,'Montant DH','0',15)
def open_session():
 try:store.open_cash(cash_amount.get());messagebox.showinfo('OK','Caisse ouverte')
 except Exception as e:show_error(e)
def close_session():
 try:
  from cash_reconciliation import inspect
  from engine import cents
  readiness=inspect(store)
  actual=cents(cash_amount.get())
  # Never silently close a session with unresolved attribution warnings.
  if readiness.warnings:
   messagebox.showwarning('Clôture suspendue / إغلاق موقوف',
    'إغلاق الصندوق موقوف بسبب عمليات تحتاج إلى مراجعة:\n\n' +
    '\n'.join('• '+w for w in readiness.warnings) +
    '\n\nراجع وسائل الدفع والشيكات والمرتجعات قبل الإغلاق.')
   return
  variance=actual-readiness.expected_cents
  if not messagebox.askyesno('Confirmation / تأكيد',
   f'رصيد المراجعة التقديري: {money(readiness.expected_cents)} DH\n'
   f'المبلغ المعدود: {money(actual)} DH\n'
   f'الفرق التقديري: {money(variance)} DH\n\n'
   'تنبيه: وظيفة الإغلاق القديمة قد تستخدم حساباً مختلفاً؛ يجب مراجعة النتائج. هل تؤكد الإغلاق؟'):
   return
  from verified_close import close_verified
  expected,variance=close_verified(store,cash_amount.get())
  messagebox.showinfo('Clôture',f'الرصيد المتوقع المسجل: {money(expected)} DH\nالفرق المسجل: {money(variance)} DH')
 except Exception as e:show_error(e)
ttk.Button(r,text='فتح الصندوق / Ouvrir',command=open_session).pack(side='left',padx=5)
ttk.Button(r,text='إغلاق الصندوق / Clôturer',command=close_session).pack(side='left',padx=5)
def preview_cash():
 try:
  from cash_audit import snapshot
  x=snapshot(store)
  rows=[('Opening / الافتتاح',x.opening_cents),('Cash sales / مبيعات نقدية',x.cash_sales_cents),('Customer cash / تحصيل نقدي',x.customer_cash_cents),('Supplier cash / أداء نقدي',-x.supplier_cash_cents),('Expenses / المصاريف',-x.expenses_cents),('Full refunds / مرتجعات كاملة',-x.refunds_cents),('Advisory total / المجموع التقديري',x.expected_cents)]
  messagebox.showinfo('Audit caisse / مراجعة الصندوق','\n'.join(f'{name}: {money(value)} DH' for name,value in rows)+'\n\nتنبيه: بعض الأداءات والمرتجعات القديمة غير مشمولة. تقرير تقديري فقط.')
 except Exception as e:show_error(e)
ttk.Button(r,text='مراجعة نقدية / Audit caisse',command=preview_cash).pack(side='left',padx=5)

def export_cash_audit():
 try:
  from tkinter import filedialog
  from cash_report import export_csv
  filename=filedialog.asksaveasfilename(title='Export audit caisse / تصدير مراجعة الصندوق',defaultextension='.csv',filetypes=[('CSV','*.csv')])
  if not filename:return
  export_csv(store,filename)
  messagebox.showinfo('Export','Cash advisory report exported / تم تصدير التقرير التقديري')
 except Exception as e:show_error(e)
ttk.Button(r,text='تصدير مراجعة الصندوق / Export audit',command=export_cash_audit).pack(side='left',padx=5)
def export_cash_movements():
 try:
  from tkinter import filedialog
  from cash_movements import export_movements_csv
  filename=filedialog.asksaveasfilename(title='Cash movements / حركات الصندوق',defaultextension='.csv',filetypes=[('CSV','*.csv')])
  if not filename:return
  export_movements_csv(store,filename)
  messagebox.showinfo('Export','Cash movements exported / تم تصدير حركات الصندوق')
 except Exception as e:show_error(e)
ttk.Button(r,text='حركات الصندوق / Mouvements',command=export_cash_movements).pack(side='left',padx=5)
def export_closed_cash_history():
 try:
  from cash_history import export_cash_history
  filename=filedialog.asksaveasfilename(title='Cash closing history / سجل إغلاقات الصندوق',defaultextension='.csv',filetypes=[('CSV','*.csv')])
  if not filename:return
  export_cash_history(store,filename)
  messagebox.showinfo('Export','Closed cash sessions exported / تم تصدير سجل الإغلاقات')
 except Exception as e:show_error(e)
ttk.Button(r,text='سجل الإغلاقات / Historique caisse',command=export_closed_cash_history).pack(side='left',padx=5)




r=ttk.Frame(f);r.pack(fill='x');return_sale=field(r,'N° vente à retourner','1',14)
refund_method=ttk.StringVar(value='cash')
ttk.Label(r,text='طريقة رد المبلغ / Remboursement').pack(side='left')
ttk.Combobox(r,textvariable=refund_method,values=('cash','bank','cheque'),state='readonly',width=9).pack(side='left',padx=4)
def do_return():
 if not messagebox.askyesno('Confirmation','Retour intégral de la vente ? / إرجاع البيع كاملاً؟'):return
 try:
  refund=store.return_full_sale(int(return_sale.get()),refund_method.get());refresh_products();refresh_history();messagebox.showinfo('Retour',f'Remboursement: {money(refund)} DH')
 except Exception as e:show_error(e)
ttk.Button(r,text='إرجاع كامل / Retour total',command=do_return).pack(side='left',padx=5)
ttk.Label(f,text='Limites: clôture basée sur ventes au comptant, retours et dépenses; règlements fournisseurs exclus. Retour intégral uniquement.',wraplength=850).pack(anchor='w',pady=12)
# V7 inventory and returns
f=pages['inventory'];r=ttk.Frame(f);r.pack(fill='x');adj_barcode=field(r,'Barcode');adj_delta=field(r,'Variation +/-','-1',10);adj_reason=field(r,'Motif / السبب','Inventaire')
def adjust():
 try:
  new=store.adjust_stock(adj_barcode.get().strip(),int(adj_delta.get()),adj_reason.get());refresh_products();refresh_history();messagebox.showinfo('Inventaire',f'Nouveau stock: {new}')
 except Exception as e:show_error(e)
ttk.Button(r,text='تسوية المخزون / Ajuster',command=adjust).pack(side='left',padx=5)

# V62: make the existing read-only inventory reconciliation accessible to managers.
def audit_inventory():
 try:
  from inventory_reconciliation import reconcile_stock
  issues=reconcile_stock(store)
  if not issues:
   messagebox.showinfo('Audit stock / تدقيق المخزون','Aucun écart / لا توجد فروقات في المخزون')
   return
  lines=[f'{x.barcode} | {x.name}: {x.stock} / {x.ledger_stock} (écart {x.difference:+d})' for x in issues[:20]]
  if len(issues)>20:lines.append(f'... {len(issues)-20} autres écarts / فروقات إضافية')
  messagebox.showwarning('Écarts de stock / فروقات المخزون','\n'.join(lines))
 except Exception as exc:show_error(exc)

def export_inventory_audit():
 try:
  from inventory_reconciliation import reconcile_stock,export_stock_differences
  issues=reconcile_stock(store)
  filename=filedialog.asksaveasfilename(title='Écarts de stock / فروقات المخزون',defaultextension='.csv',filetypes=[('CSV','*.csv')])
  if not filename:return
  export_stock_differences(issues,filename)
  messagebox.showinfo('Export','Rapport exporté / تم تصدير تقرير المخزون')
 except Exception as exc:show_error(exc)

# V64: read-only provenance check for sale unit costs.
def audit_sale_costs():
 try:
  from cost_provenance import inspect_sale_costs
  findings=inspect_sale_costs(store)
  if not findings:
   messagebox.showinfo('Coûts / التكاليف','Aucune anomalie détectée. Ceci ne prouve pas le coût FIFO/FEFO. / لا يثبت تكلفة الدفعات الفعلية.')
   return
  lines=[f'Vente {x.sale_id} / {x.barcode}: {x.status} ({x.booked_cost_cents} / {x.latest_purchase_cost_cents})' for x in findings[:20]]
  if len(findings)>20:lines.append(f'... {len(findings)-20} autres')
  messagebox.showwarning('Coûts à vérifier / تكاليف تحتاج مراجعة','\n'.join(lines))
 except Exception as exc:show_error(exc)

def export_sale_costs():
 try:
  from cost_provenance import inspect_sale_costs,export_cost_findings
  findings=inspect_sale_costs(store)
  filename=filedialog.asksaveasfilename(title='Audit coûts / تدقيق التكاليف',defaultextension='.csv',filetypes=[('CSV','*.csv')])
  if not filename:return
  export_cost_findings(findings,filename)
  messagebox.showinfo('Export','Rapport exporté / تم التصدير')
 except Exception as exc:show_error(exc)

# V65: FEFO tracked-lot allocation integrity review (read-only).
def audit_fefo_lots():
 try:
  from lot_allocation_audit import audit_lot_allocations
  issues=audit_lot_allocations(store)
  if not issues:
   messagebox.showinfo('Lots FEFO / الدفعات','Aucune anomalie détectée / لا توجد اختلافات مكتشفة')
  else:
   lines=[f'{x.barcode} / {x.kind} #{x.reference_id}: {x.expected} != {x.actual}' for x in issues[:20]]
   if len(issues)>20:lines.append(f'... {len(issues)-20} autres')
   messagebox.showwarning('Lots FEFO / الدفعات','\n'.join(lines))
 except Exception as exc:show_error(exc)

def export_fefo_lots():
 try:
  from lot_allocation_audit import audit_lot_allocations,export_lot_issues
  issues=audit_lot_allocations(store)
  filename=filedialog.asksaveasfilename(title='Audit lots FEFO',defaultextension='.csv',filetypes=[('CSV','*.csv')])
  if not filename:return
  export_lot_issues(issues,filename)
  messagebox.showinfo('Export','Rapport exporté / تم التصدير')
 except Exception as exc:show_error(exc)

# Only accounts with reporting privileges see these controls.
if store.current_user[2]=='admin':
 ttk.Button(r,text='تدقيق المخزون / Audit stock',command=audit_inventory).pack(side='left',padx=5)
 ttk.Button(r,text='تصدير فروقات المخزون / Export écarts',command=export_inventory_audit).pack(side='left',padx=5)
 ttk.Button(r,text='تدقيق تكاليف البيع / Audit coûts',command=audit_sale_costs).pack(side='left',padx=5)
 ttk.Button(r,text='تصدير تدقيق التكاليف / Export coûts',command=export_sale_costs).pack(side='left',padx=5)
 ttk.Button(r,text='تدقيق دفعات FEFO / Audit lots',command=audit_fefo_lots).pack(side='left',padx=5)
 ttk.Button(r,text='تصدير تدقيق الدفعات / Export lots',command=export_fefo_lots).pack(side='left',padx=5)

r=ttk.Frame(f);r.pack(fill='x');partial_sale=field(r,'N° vente','1',10);partial_line=field(r,'ID ligne','1',10);partial_qty=field(r,'Qté retour','1',10)
partial_refund_method=ttk.StringVar(value='cash')
ttk.Label(r,text='Remboursement / الأداء').pack(side='left')
ttk.Combobox(r,textvariable=partial_refund_method,values=('cash','bank','cheque'),state='readonly',width=9).pack(side='left',padx=4)
def partial_return():
 if not messagebox.askyesno('Retour','Confirmer le retour partiel ?'):return
 try:
  rid,refund=store.return_items(int(partial_sale.get()),{int(partial_line.get()):int(partial_qty.get())},partial_refund_method.get());refresh_products();refresh_history();refresh_return_lines();messagebox.showinfo('Retour',f'Retour #{rid} : {money(refund)} DH')
 except Exception as e:show_error(e)
ttk.Button(r,text='إرجاع جزئي / Retour partiel',command=partial_return).pack(side='left',padx=5)
return_table=grid(f,['Ligne ID','Vente ID','Barcode','Qté vendue','Qté retournée'])
def refresh_return_lines():
 sql="SELECT sl.id,sl.sale_id,p.barcode,sl.quantity,(SELECT COALESCE(SUM(prl.quantity),0) FROM partial_return_lines prl WHERE prl.sale_line_id=sl.id) FROM sale_lines sl JOIN products p ON p.id=sl.product_id ORDER BY sl.id DESC LIMIT 300"
 fill(return_table,store.db.execute(sql).fetchall())
ttk.Button(f,text='تحديث / Actualiser',command=refresh_return_lines).pack(anchor='w')
# V10 lot control: opt-in only with zero stock
f=pages['expiry'];r=ttk.Frame(f);r.pack(fill='x')
lot_barcode=field(r,'Barcode',width=17);lot_qty=field(r,'Qté','1',7)
lot_ref=field(r,'Réf. fournisseur',width=15);lot_code=field(r,'Lot',width=14)
lot_date=field(r,'Expiration YYYY-MM-DD',width=17)
def add_lot():
 try:
  lot_id=store.receive_lot(lot_barcode.get(),int(lot_qty.get()),lot_ref.get(),lot_code.get(),lot_date.get())
  refresh_products();refresh_history();refresh_lots();messagebox.showinfo('OK',f'Lot enregistré #{lot_id}')
 except Exception as e:show_error(e)
def enable_tracking():
 try:
  store.enable_lot_tracking(lot_barcode.get());messagebox.showinfo('OK','Lot tracking enabled / تم تفعيل تتبع الدفعات')
 except Exception as e:show_error(e)
ttk.Button(f,text='تفعيل تتبع الدفعات / Activer FEFO (stock=0)',command=enable_tracking).pack(anchor='w',pady=4)
ttk.Button(f,text='تسجيل دفعة / Enregistrer lot',command=add_lot).pack(anchor='w',pady=5)
ttk.Label(f,text='FEFO للمنتجات المتتبعة فقط. مرتجعاتها تُسجل في شاشة الحجر ولا تعود للمخزون القابل للبيع؛ الجرد للدفعات المتتبعة ما زال معطلاً.',wraplength=900).pack(anchor='w')
lot_table=grid(f,['ID','Barcode','Produit','Lot','Expiration','Qté reçue','Statut'])
def refresh_lots():fill(lot_table,store.expiry_alerts(30))
ttk.Button(f,text='تحديث تنبيهات 30 يوماً / Alertes 30 jours',command=refresh_lots).pack(anchor='w')
lot_stock_table=grid(f,['Barcode','Produit','Lot','Expiration','Reste'])
def refresh_lot_stock():fill(lot_stock_table,store.lot_inventory())
ttk.Button(f,text='رصيد الدفعات / Stock par lot',command=refresh_lot_stock).pack(anchor='w')

# V67 — manager-only explicit acquisition cost entry for FEFO lots.
# Never infer missing costs from the product master or overwrite recorded costs.
if 'inventory' in PERMISSIONS[store.current_user[2]] and 'reports' in PERMISSIONS[store.current_user[2]]:
 cost_row=ttk.Frame(f);cost_row.pack(fill='x',pady=6)
 cost_lot_id=field(cost_row,'ID lot / رقم الدفعة',width=12)
 cost_unit=field(cost_row,'Coût unitaire DH / تكلفة الوحدة',width=17)
 cost_invoice=field(cost_row,'Réf. facture / مرجع الفاتورة',width=20)
 def save_lot_acquisition_cost():
  try:
   from lot_costing import record_lot_cost
   record_lot_cost(store,int(cost_lot_id.get()),cost_unit.get(),cost_invoice.get())
   messagebox.showinfo('OK','Coût de lot enregistré définitivement / تم حفظ تكلفة الدفعة')
  except Exception as e:show_error(e)
 def show_lot_costing_summary():
  try:
   from lot_costing import costing_summary
   data=costing_summary(store)
   messagebox.showinfo('Coûts FEFO / تكاليف الدفعات',
     f"Quantité avec coût / كمية معروفة التكلفة: {data['costed_quantity']}\n"
     f"Quantité sans coût / كمية مجهولة التكلفة: {data['unknown_quantity']}\n"
     f"Coût connu / التكلفة المعروفة: {money(data['known_cost_cents'])} DH\n"
     f"Complet / مكتمل: {'Oui' if data['complete'] else 'Non'}\n"
     'Ce total concerne uniquement les allocations FEFO, pas toutes les ventes. / المجموع يخص تخصيصات FEFO فقط.')
  except Exception as e:show_error(e)
 ttk.Button(cost_row,text='حفظ تكلفة الدفعة / Enregistrer coût',command=save_lot_acquisition_cost).pack(side='left',padx=4)
 ttk.Button(f,text='تقرير تكاليف الدفعات / Coûts FEFO',command=show_lot_costing_summary).pack(anchor='w',pady=4)
 def show_period_cost_coverage():
  try:
   from lot_costing import period_cost_coverage
   data=period_cost_coverage(store,period='month')
   messagebox.showinfo('Couverture des coûts / تغطية التكاليف',
     f"Ventes (unités) / الوحدات المبيعة: {data.sold_quantity}\n"
     f"Unités coûtées / وحدات معروفة التكلفة: {data.known_cost_quantity}\n"
     f"Coût inconnu / تكلفة مجهولة: {data.unknown_cost_quantity}\n"
     f"Sans allocation / بدون دفعة: {data.missing_allocation_quantity}\n"
     f"Allocation excessive / تخصيص زائد: {data.excess_allocation_quantity}\n"
     f"Coût connu / التكلفة المعروفة: {money(data.known_cost_cents)} DH\n"
     f"Couverture complète / تغطية كاملة: {'Oui' if data.complete else 'Non'}\n"
     'Diagnostic des ventes du mois uniquement; retours exclus. / فحص مبيعات الشهر فقط دون المرتجعات.')
  except Exception as e:show_error(e)
 ttk.Button(f,text='تغطية تكلفة مبيعات الشهر / Couverture mensuelle',command=show_period_cost_coverage).pack(anchor='w',pady=4)

 def show_verified_sales_margin():
  try:
   from lot_costing import verified_sales_margin
   data=verified_sales_margin(store,period='month')
   margin=(f'{money(data.gross_margin_cents)} DH' if data.complete else
           'INDISPONIBLE / غير متاح بسبب تكاليف مجهولة')
   messagebox.showinfo('Marge FEFO / هامش الدفعات',
     f"Ventes du mois / مبيعات الشهر: {money(data.sales_cents)} DH\n"
     f"Coût FEFO connu / التكلفة المعروفة: {money(data.known_cogs_cents)} DH\n"
     f"Unités non coûtées / وحدات غير موثقة: {data.uncosted_quantity}\n"
     f"Marge brute / الهامش الخام: {margin}\n"
     'Ventes uniquement, hors retours et dépenses. / المبيعات فقط دون المرتجعات والمصاريف.')
  except Exception as e:show_error(e)
 ttk.Button(f,text='هامش مبيعات الشهر حسب الدفعات / Marge FEFO',command=show_verified_sales_margin).pack(anchor='w',pady=4)
 def show_verified_net_profit():
  from lot_costing import verified_period_profit
  report=verified_period_profit(store,period='month')
  value=money(report.net_profit_cents) + ' DH' if report.complete else 'غير مؤكد / Non vérifié'
  details='\n'.join(report.issues[:8]) if report.issues else 'Toutes les allocations vérifiées'
  messagebox.showinfo('Résultat FEFO / صافي الربح',
    f'Résultat net du mois / صافي ربح الشهر: {value}\n'
    f'Ventes: {money(report.sales_cents)} DH\n'
    f'Remboursements: {money(report.refunds_cents)} DH\n'
    f'Dépenses: {money(report.expenses_cents)} DH\n'
    f'Coût vendu connu: {money(report.known_sold_cost_cents)} DH\n'
    f'Coût retourné connu: {money(report.known_returned_cost_cents)} DH\n'
    f'{details}')
 ttk.Button(f,text='صافي ربح الشهر بتكلفة الدفعات / Résultat FEFO',command=show_verified_net_profit).pack(anchor='w',pady=4)



f=pages['reports'];report_text=tk.Text(f,height=20,font=('Consolas',12));report_text.pack(fill='both',expand=True)
def refresh_reports():
 o=store.overview();report_text.delete('1.0','end')
 report_text.insert('end','ÉPICERIE ENTERPRISE V14 / تقارير تراكمية\n\n'+'\n'.join(str(k)+': '+(money(v)+' DH' if k.endswith('_cents') else str(v)) for k,v in o.items())+'\n\nEstimations non comptables / أرقام تقديرية')
ttk.Button(f,text='تحديث التقرير / Actualiser',command=refresh_reports).pack(anchor='w',pady=8)

# V23 — visible daily, weekly and monthly profit dashboard.
profits_page=pages['profits']
ttk.Label(profits_page,text='الأرباح التشغيلية التقديرية / Bénéfices opérationnels estimés',font=('Segoe UI',16,'bold')).pack(anchor='w',pady=8)
profit_controls=ttk.Frame(profits_page);profit_controls.pack(fill='x',pady=8)
profit_period=tk.StringVar(value='day')
ttk.Label(profit_controls,text='الفترة / Période').pack(side='left',padx=5)
ttk.Combobox(profit_controls,textvariable=profit_period,values=['day','week','month'],state='readonly',width=12).pack(side='left',padx=5)
profit_date=tk.StringVar(value=datetime.datetime.now(__import__("zoneinfo").ZoneInfo("Africa/Casablanca")).date().isoformat())
ttk.Label(profit_controls,text='تاريخ YYYY-MM-DD / Date').pack(side='left',padx=5)
ttk.Entry(profit_controls,textvariable=profit_date,width=15).pack(side='left',padx=5)
profit_result=tk.StringVar(value='اختر الفترة واضغط تحديث / Sélectionnez une période et actualisez')
ttk.Label(profits_page,textvariable=profit_result,font=('Segoe UI',12),justify='left').pack(anchor='w',pady=12)
profit_note='Africa/Casablanca: الفترات حسب توقيت المغرب المحلي مع مراعاة تغيير الساعة.\n' + 'الربح تشغيلي تقديري: لا يشمل كل الضرائب والفقد والاستهلاك. / Estimation non comptable.'
ttk.Label(profits_page,text=profit_note,wraplength=900,justify='left').pack(anchor='w',pady=10)
current_profit_report=[None]
def refresh_profits():
 try:
  report, previous, delta, growth = compare_periods(store,profit_period.get(),profit_date.get().strip(),timezone_name="Africa/Casablanca")
  current_profit_report[0]=report
  lines=[
   f'Période locale / الفترة المحلية: {report.start} → {report.end} (fin exclue)',
   f'عدد الفواتير / Factures: {report.sale_count}',
   f'المبيعات / Ventes: {money(report.sales_cents)} DH',
   f'المرتجعات / Retours: -{money(report.returned_revenue_cents)} DH',
   f'صافي المبيعات / Ventes nettes: {money(report.net_revenue_cents)} DH',
   f'تكلفة المبيعات الصافية / Coût net: {money(report.cogs_cents-report.returned_cost_cents)} DH',
   f'الربح الإجمالي / Marge brute: {money(report.gross_profit_cents)} DH',
   f'المصاريف / Charges: -{money(report.expenses_cents)} DH',
   f'الربح التشغيلي التقديري / Résultat estimé: {money(report.operating_profit_cents)} DH',
   f'الفترة السابقة / Période précédente ({previous.start}): {money(previous.operating_profit_cents)} DH',
   f'الفرق / Variation: {money(delta)} DH',
   f'نسبة التغير / Évolution: {growth:.2f}%' if growth is not None else 'نسبة التغير / Évolution: غير متاحة (ربح الفترة السابقة غير موجب)',
  ]
  profit_result.set('\n'.join(lines))
 except Exception as exc:current_profit_report[0]=None;show_error(exc)
def export_profits():
 if current_profit_report[0] is None:return show_error(ValueError('Actualisez le rapport avant export / حدّث التقرير أولاً'))
 target=filedialog.asksaveasfilename(title='Exporter / تصدير',defaultextension='.csv',filetypes=[('CSV','*.csv')])
 if target:
  try:export_profit_csv(current_profit_report[0],target);messagebox.showinfo('Export CSV',target)
  except Exception as exc:show_error(exc)
ttk.Button(profit_controls,text='تحديث / Actualiser',command=refresh_profits).pack(side='left',padx=8)
ttk.Button(profit_controls,text='تصدير CSV / Exporter',command=export_profits).pack(side='left',padx=8)

# V73: verified lot-cost result follows the same local day/week/month selector.
verified_profit_result=tk.StringVar(value='الربح حسب تكلفة الدفعات: لم يتم التحقق / Résultat FEFO non vérifié')
ttk.Label(profits_page,textvariable=verified_profit_result,justify='left',wraplength=950).pack(anchor='w',pady=8)
def refresh_verified_profits():
 try:
  from lot_costing import verified_period_profit
  r=verified_period_profit(store,period=profit_period.get(),day=profit_date.get().strip(),timezone_name='Africa/Casablanca')
  result=f'{money(r.net_profit_cents)} DH' if r.complete else 'غير مؤكد / NON VÉRIFIÉ'
  issues='\n'.join(r.issues[:8]) if r.issues else 'Toutes les allocations vérifiées / جميع الدفعات موثقة'
  verified_profit_result.set(
   f'نتيجة الفترة حسب تكلفة الدفعات / Résultat FEFO: {result}\n'
   f'المبيعات / Ventes: {money(r.sales_cents)} DH | المرتجعات / Retours: {money(r.refunds_cents)} DH\n'
   f'تكلفة المبيعات / Coût vendu: {money(r.known_sold_cost_cents)} DH | '
   f'تكلفة المرتجعات / Coût retourné: {money(r.known_returned_cost_cents)} DH\n'
   f'المصاريف / Charges: {money(r.expenses_cents)} DH\n{issues}')
 except Exception as exc:
  verified_profit_result.set('تعذر التحقق / Vérification impossible')
  show_error(exc)
ttk.Button(profit_controls,text='تدقيق الربح بتكلفة الدفعات / Vérifier FEFO',command=refresh_verified_profits).pack(side='left',padx=5)
def export_verified_profits():
 try:
  from tkinter import filedialog
  from verified_profit_export import export_verified_profit
  target=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],title='Export résultat FEFO')
  if not target:return
  export_verified_profit(store,target,period=profit_period.get(),day=profit_date.get().strip(),timezone_name='Africa/Casablanca')
  messagebox.showinfo('Export CSV','Rapport FEFO exporté / تم تصدير تقرير الدفعات')
 except Exception as exc:show_error(exc)
ttk.Button(profit_controls,text='تصدير FEFO CSV / Exporter',command=export_verified_profits).pack(side='left',padx=5)

profit_period.trace_add('write',lambda *_: verified_profit_result.set('الفترة تغيرت؛ أعد التحقق / Actualisez le résultat FEFO'))
profit_date.trace_add('write',lambda *_: verified_profit_result.set('التاريخ تغير؛ أعد التحقق / Actualisez le résultat FEFO'))


# V29: twelve-month historical profitability trend, without changing accounting data.
trend_frame=ttk.LabelFrame(profits_page,text='الأرباح خلال 12 شهراً / Évolution mensuelle (12 mois)')
trend_frame.pack(fill='x',pady=6)
trend_year=tk.StringVar(value=str(datetime.datetime.now(__import__('zoneinfo').ZoneInfo('Africa/Casablanca')).year))
ttk.Label(trend_frame,text='السنة / Année').pack(side='left',padx=5)
ttk.Entry(trend_frame,textvariable=trend_year,width=7).pack(side='left',padx=4)
current_trend=[None]
def refresh_trend():
 try:
  year=int(trend_year.get().strip())
  rows=monthly_profit_trend(store,year)
  current_trend[0]=rows
  total=sum(r.operating_profit_cents for r in rows)
  trend_summary.set(' | '.join(f'{r.month}: {money(r.operating_profit_cents)} DH' for r in rows)+f'\nالمجموع السنوي التقديري / Total annuel estimé: {money(total)} DH')
 except Exception as exc:current_trend[0]=None;show_error(exc)
def export_trend():
 if current_trend[0] is None:return show_error(ValueError('حدّث التقرير السنوي أولاً / Actualisez d’abord'))
 target=filedialog.asksaveasfilename(title='Export 12 mois',defaultextension='.csv',filetypes=[('CSV','*.csv')])
 if target:
  try:export_monthly_trend_csv(current_trend[0],target);messagebox.showinfo('Export CSV',target)
  except Exception as exc:show_error(exc)
ttk.Button(trend_frame,text='عرض 12 شهراً / Afficher',command=refresh_trend).pack(side='left',padx=4)
ttk.Button(trend_frame,text='تصدير CSV / Export',command=export_trend).pack(side='left',padx=4)
trend_summary=tk.StringVar(value='اختر السنة لعرض الأرباح الشهرية / Sélectionnez une année')
ttk.Label(profits_page,textvariable=trend_summary,wraplength=980,justify='left').pack(anchor='w',pady=4)
trend_year.trace_add('write',lambda *_:current_trend.__setitem__(0,None))

# V27: product-level gross margin drilldown (read-only).
product_profit_tree=ttk.Treeview(profits_page,columns=('barcode','name','sold','returned','revenue','cost','margin'),show='headings',height=8)
for col,title in [('barcode','Barcode'),('name','Produit / السلعة'),('sold','Vendus'),('returned','Retours'),('revenue','Ventes nettes DH'),('cost','Coût net DH'),('margin','Marge brute DH')]:
 product_profit_tree.heading(col,text=title)
 product_profit_tree.column(col,width=145 if col=='name' else 110,anchor='center')
product_profit_tree.pack(fill='both',expand=True,pady=8)
current_product_profit=[None]
def refresh_product_profits():
 try:
  rows=product_profit_report(store,profit_period.get(),profit_date.get().strip())
  current_product_profit[0]=rows
  product_profit_tree.delete(*product_profit_tree.get_children())
  for r in rows:
   product_profit_tree.insert('','end',values=(r.barcode,r.name,r.quantity_sold,r.quantity_returned,money(r.revenue_cents-r.returned_revenue_cents),money(r.cost_cents-r.returned_cost_cents),money(r.gross_profit_cents)))
 except Exception as exc:current_product_profit[0]=None;show_error(exc)
def export_product_profits():
 if current_product_profit[0] is None:return show_error(ValueError('Actualisez le détail des produits / حدّث تقرير السلع أولاً'))
 target=filedialog.asksaveasfilename(title='Export produits / تصدير السلع',defaultextension='.csv',filetypes=[('CSV','*.csv')])
 if target:
  try:export_product_profit_csv(current_product_profit[0],target);messagebox.showinfo('Export CSV',target)
  except Exception as exc:show_error(exc)
ttk.Button(profit_controls,text='أرباح السلع / Marges produits',command=refresh_product_profits).pack(side='left',padx=4)
ttk.Button(profit_controls,text='تصدير السلع / Export produits',command=export_product_profits).pack(side='left',padx=4)
# V28: explicitly reconcile product-level figures with booked period totals.
reconciliation_result=tk.StringVar(value='مطابقة أرباح السلع / Rapprochement des marges: لم يتم الفحص')
ttk.Label(profits_page,textvariable=reconciliation_result,justify='left',wraplength=900).pack(anchor='w',pady=5)
current_reconciliation=[None]
def refresh_reconciliation():
 try:
  r=reconcile_product_profits(store,profit_period.get(),profit_date.get().strip())
  current_reconciliation[0]=r
  status='متطابق / Conforme' if r.balanced else 'اختلاف يحتاج مراجعة / Écart à examiner'
  reconciliation_result.set(f'{status} | فرق المبيعات: {money(r.revenue_difference_cents)} DH | فرق التكلفة: {money(r.cost_difference_cents)} DH | فرق الربح: {money(r.gross_profit_difference_cents)} DH')
 except Exception as exc:current_reconciliation[0]=None;show_error(exc)
def export_reconciliation():
 if current_reconciliation[0] is None:return show_error(ValueError('شغّل المطابقة أولاً / Lancez le rapprochement'))
 target=filedialog.asksaveasfilename(title='Export rapprochement / تصدير المطابقة',defaultextension='.csv',filetypes=[('CSV','*.csv')])
 if target:
  try:export_reconciliation_csv(current_reconciliation[0],target);messagebox.showinfo('Export CSV',target)
  except Exception as exc:show_error(exc)
ttk.Button(profit_controls,text='مطابقة الأرباح / Rapprocher',command=refresh_reconciliation).pack(side='left',padx=4)
ttk.Button(profit_controls,text='تصدير المطابقة / Export écarts',command=export_reconciliation).pack(side='left',padx=4)
# V34: surface the existing read-only financial-quality audit in the UI.
quality_result=tk.StringVar(value='فحص جودة الأرباح / Contrôle de qualité: لم يتم الفحص')
ttk.Label(profits_page,textvariable=quality_result,justify='left',wraplength=960).pack(anchor='w',pady=5)
current_quality=[None]
def refresh_profit_quality():
 try:
  q=check_profit_quality(store,profit_period.get(),profit_date.get().strip(),timezone_name='Africa/Casablanca')
  current_quality[0]=q
  state='جاهز للمراجعة / Prêt pour révision' if q.ready_for_review else 'يتطلب مراجعة / À examiner'
  quality_result.set(' | '.join([
   state,
   f'تكلفة صفرية / Coût nul: {q.zero_cost_lines}',
   f'بيع بخسارة / Vente à perte: {q.negative_margin_lines}',
   f'فواتير بلا أصناف / Ventes sans lignes: {q.missing_line_sales}',
   f'فرق الأرباح / Écart marges: {money(q.reconciliation_difference_cents)} DH',
   ' ; '.join(q.warnings) if q.warnings else 'لا توجد تحذيرات في هذه الفحوص / Aucun avertissement détecté']))
 except Exception as exc:
  current_quality[0]=None
  show_error(exc)
def export_profit_quality():
 if current_quality[0] is None:
  return show_error(ValueError('شغّل فحص الجودة أولاً / Lancez le contrôle avant export'))
 target=filedialog.asksaveasfilename(title='Export contrôle / تصدير فحص الأرباح',defaultextension='.csv',filetypes=[('CSV','*.csv')])
 if target:
  try:
   export_quality_csv(current_quality[0],target)
   messagebox.showinfo('Export CSV',target)
  except Exception as exc:show_error(exc)
ttk.Button(profit_controls,text='فحص جودة الأرباح / Contrôle',command=refresh_profit_quality).pack(side='left',padx=4)
ttk.Button(profit_controls,text='تصدير الفحص / Export contrôle',command=export_profit_quality).pack(side='left',padx=4)
profit_period.trace_add('write',lambda *_: current_quality.__setitem__(0,None))
profit_date.trace_add('write',lambda *_: current_quality.__setitem__(0,None))
profit_period.trace_add('write',lambda *_: current_product_profit.__setitem__(0,None))
profit_period.trace_add('write',lambda *_: current_reconciliation.__setitem__(0,None))
profit_date.trace_add('write',lambda *_: current_reconciliation.__setitem__(0,None))
profit_date.trace_add('write',lambda *_: current_product_profit.__setitem__(0,None))
profit_period.trace_add('write',lambda *_: current_profit_report.__setitem__(0,None))
profit_date.trace_add('write',lambda *_: current_profit_report.__setitem__(0,None))

# Backups
f=pages['backup'];ttk.Label(f,text='Choisissez un dossier synchronisé par Google Drive for desktop. / اختر مجلداً تتم مزامنته بواسطة Google Drive.',wraplength=800).pack(anchor='w',pady=12)
def backup():
 folder=filedialog.askdirectory(title='Dossier de sauvegarde / مجلد النسخ الاحتياطي')
 if not folder:return
 try:
  timestamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');path=store.backup(Path(folder)/f'epicerie_backup_{timestamp}.db');messagebox.showinfo('Backup OK',f'{path}\nVérifiez la synchronisation Google Drive séparément.')
 except Exception as e:show_error(e)
ttk.Button(f,text='نسخ احتياطي الآن / Sauvegarder maintenant',command=backup).pack(anchor='w',pady=12)
ttk.Label(f,text='Attention: ce bouton crée une sauvegarde locale. Il ne confirme pas que Google Drive l’a téléversée.',wraplength=800).pack(anchor='w')
def close():store.close();root.destroy()
root.protocol('WM_DELETE_WINDOW',close)
# Do not load confidential reports, suppliers or stock movements for cashiers.
if store.current_user[2]=='admin':
 refresh_products();refresh_history();refresh_suppliers();refresh_return_lines();refresh_lots();refresh_reports()
else:
 refresh_products()

# V11 quality-control screen (no financial refund or resale)
qtab=ttk.Frame(notebook,padding=12)
notebook.add(qtab,text='حجر المرتجعات / Quarantaine')
qr=ttk.Frame(qtab);qr.pack(fill='x')
q_sale=field(qr,'N° vente / رقم البيع','',10)
q_line=field(qr,'N° ligne / رقم السطر','',10)
q_qty=field(qr,'Quantité','1',8)
q_reason=field(qr,'Motif / السبب','Retour client',24)
qtable=grid(qtab,['ID','Vente','Date UTC','Motif','Statut','Quantité'])
def refresh_quarantine():fill(qtable,store.quarantine_report())
def submit_quarantine():
 try:
  rid=store.quarantine_return(str(uuid.uuid4()),int(q_sale.get()),{int(q_line.get()):int(q_qty.get())},q_reason.get())
  refresh_quarantine();messagebox.showinfo('Quarantaine',f'Enregistré / تم التسجيل #{rid}\nAucun remboursement automatique / لا استرداد مالي تلقائي')
 except Exception as e:show_error(e)
ttk.Button(qr,text='حجر المرتجع / Quarantiner',command=submit_quarantine).pack(side='left',padx=6,pady=10)
if store.current_user[2]=='admin':refresh_quarantine()

# V14 tiered wholesale checkout, separate from legacy detail POS.
if 'sales' in PERMISSIONS[store.current_user[2]]:
 wholesale=ttk.Frame(notebook,padding=12);notebook.add(wholesale,text='جملة ونصف جملة / Gros')
 wr=ttk.Frame(wholesale);wr.pack(fill='x')
 wc=field(wr,'Barcode / باركود');wq=field(wr,'Packs / العدد','1',8);wu=field(wr,'Unité (piece/carton)','piece',12);wt=field(wr,'Tarif (detail/demi_gros/gros)','gros',18);wp=field(wr,'Reçu DH / المدفوع','0',12)
 ttk.Label(wholesale,text='تطبق الأسعار على القطعة الأساسية؛ الكرتون يخصم عدد القطع داخله. أدخل أسعار الجملة أولاً في إعدادات الأسعار.').pack(anchor='w')
 def submit_tier_sale():
  try:
   result=store.sale_tiered(str(uuid.uuid4()),[(wc.get().strip(),int(wq.get()),wu.get().strip(),wt.get().strip())],wp.get());refresh_products();refresh_history();messagebox.showinfo('Vente',f'N° {result[0]} | Total {money(result[1])} DH | Monnaie {money(result[2])} DH')
  except Exception as exc:show_error(exc)
 ttk.Button(wr,text='تأكيد بيع الجملة / Valider',command=submit_tier_sale).pack(side='left',padx=4)
if 'products' in PERMISSIONS[store.current_user[2]]:
 pricingtab=ttk.Frame(notebook,padding=12);notebook.add(pricingtab,text='تسعير الجملة / Tarifs')
 pr=ttk.Frame(pricingtab);pr.pack(fill='x')
 pc=field(pr,'Barcode');pt=field(pr,'Tarif: detail / demi_gros / gros','gros',18);pv=field(pr,'Prix unitaire DH','0',10);pm=field(pr,'Minimum pièces','1',10)
 def save_tier():
  try:store.set_tier(pc.get().strip(),pt.get().strip(),pv.get(),int(pm.get()));refresh_tiers()
  except Exception as exc:show_error(exc)
 ttk.Button(pr,text='حفظ السعر / Enregistrer',command=save_tier).pack(side='left')
 ur=ttk.Frame(pricingtab);ur.pack(fill='x');uc=field(ur,'Barcode');un=field(ur,'Unité (carton/boite)','carton');uf=field(ur,'Pièces par unité','12',10)
 def save_unit():
  try:store.set_unit(uc.get().strip(),un.get().strip(),int(uf.get()));messagebox.showinfo('OK','Unité enregistrée')
  except Exception as exc:show_error(exc)
 ttk.Button(ur,text='حفظ الوحدة / Enregistrer',command=save_unit).pack(side='left')
 tiers_table=grid(pricingtab,['Barcode','Produit','Tarif','Prix centimes','Min pièces'])
 def refresh_tiers():fill(tiers_table,store.tier_catalog())
 refresh_tiers()

# Role-based tab visibility; API additionally checks mutations.
required_tabs={'catalog':'products','pos':'sales','receipt':'purchases','history':'inventory','suppliers':'purchases','finance':'finance','inventory':'inventory','expiry':'lots','reports':'reports','profits':'reports','backup':'backup'}
for key,permission in required_tabs.items():
 if permission not in PERMISSIONS[store.current_user[2]]:notebook.hide(pages[key])
if 'returns' not in PERMISSIONS[store.current_user[2]]:notebook.hide(qtab)
if 'users' in PERMISSIONS[store.current_user[2]]:
 utab=ttk.Frame(notebook,padding=12);notebook.add(utab,text='المستخدمون / Utilisateurs')
 ur=ttk.Frame(utab);ur.pack(fill='x')
 un=field(ur,'Utilisateur / المستخدم');up=field(ur,'Mot de passe / كلمة المرور');role=field(ur,'Rôle: cashier / البائع','cashier');up_entry=ur.winfo_children()[1].winfo_children()[1];up_entry.configure(show='*')
 users_table=grid(utab,['Utilisateur','Rôle','Actif'])
 def refresh_users():fill(users_table,store.list_users())
 def add_user():
  try:store.create_user(un.get(),up.get(),role.get());refresh_users();up.set('');messagebox.showinfo('OK','Utilisateur créé')
  except Exception as e:show_error(e)
 ttk.Button(ur,text='إنشاء مستخدم / Créer',command=add_user).pack(side='left',padx=5)
 refresh_users()
 def reset_cashier():
  try:
   username=simpledialog.askstring('Caissier / البائع','Cashier username:',parent=root)
   if not username:return
   newpass=simpledialog.askstring('Password / كلمة المرور','New password (12+ characters):',show='*',parent=root)
   if not newpass:return
   store.reset_cashier_password(username,newpass)
   messagebox.showinfo('OK','Cashier password updated / تم تغيير كلمة مرور البائع')
  except Exception as exc:show_error(exc)
 ttk.Button(ur,text='إعادة تعيين كلمة مرور البائع / Réinitialiser',command=reset_cashier).pack(side='left',padx=5)
 def unlock_cashier_ui():
  try:
   username=simpledialog.askstring('Déverrouiller / فك القفل','Cashier username / اسم البائع:',parent=root)
   if not username:return
   store.unlock_cashier(username)
   messagebox.showinfo('OK','Cashier account unlocked / تم فك قفل حساب البائع')
  except Exception as exc:show_error(exc)
 ttk.Button(ur,text='فك قفل البائع / Déverrouiller',command=unlock_cashier_ui).pack(side='left',padx=5)

# V14: receivables and cheque management (manager/admin only)
if 'finance' in PERMISSIONS[store.current_user[2]]:
 debt_tab=ttk.Frame(notebook,padding=12);notebook.add(debt_tab,text='الديون والشيكات / Crédit & Chèques')
 cr=ttk.Frame(debt_tab);cr.pack(fill='x')
 cn=field(cr,'Nom client / اسم الزبون');cp=field(cr,'Téléphone');cl=field(cr,'Plafond crédit DH','0',12)
 def add_client():
  try:store.add_customer(cn.get(),cp.get(),cl.get());refresh_clients()
  except Exception as exc:show_error(exc)
 ttk.Button(cr,text='إضافة زبون / Ajouter',command=add_client).pack(side='left')
 clients_table=grid(debt_tab,['ID','Client','Téléphone','Plafond centimes'])
 def refresh_clients():fill(clients_table,store.customers())
 refresh_clients()
 credit_frame=ttk.LabelFrame(debt_tab,text='بيع بالدين / Vente à crédit');credit_frame.pack(fill='x')
 ar=ttk.Frame(credit_frame);ar.pack(fill='x')
 ccid=field(ar,'ID client','1',7);ccb=field(ar,'Barcode',width=17);ccq=field(ar,'Quantité','1',7);ccu=field(ar,'Unité','piece',10);cct=field(ar,'Tarif','detail',12);ccd=field(ar,'Acompte DH','0',10)
 def credit_checkout():
  try:
   iid,sid,total=store.credit_sale(str(uuid.uuid4()),int(ccid.get()),[(ccb.get().strip(),int(ccq.get()),ccu.get().strip(),cct.get().strip())],ccd.get());refresh_receivables();refresh_products();messagebox.showinfo('OK',f'Facture {iid} / Vente {sid} / Total {money(total)} DH')
  except Exception as exc:show_error(exc)
 ttk.Button(ar,text='تسجيل البيع بالدين / Valider crédit',command=credit_checkout).pack(side='left')
 payment_frame=ttk.LabelFrame(debt_tab,text='تسديد / Encaissement');payment_frame.pack(fill='x')
 rr=ttk.Frame(payment_frame);rr.pack(fill='x')
 ri=field(rr,'N° facture','1',8);ra=field(rr,'Montant DH','0',9);rm=field(rr,'Mode: cash/bank/cheque','cash',13);rn=field(rr,'N° chèque',width=13);rb=field(rr,'Banque',width=12);rd=field(rr,'Échéance YYYY-MM-DD',width=16)
 def record_payment():
  try:
   pid=store.receive_payment(str(uuid.uuid4()),int(ri.get()),ra.get(),rm.get().strip(),cheque_number=rn.get(),bank_name=rb.get(),due_date=rd.get() or None);refresh_receivables();refresh_cheques();messagebox.showinfo('OK',f'Paiement #{pid}')
  except Exception as exc:show_error(exc)
 ttk.Button(rr,text='تسجيل الأداء / Enregistrer',command=record_payment).pack(side='left')
 debts_table=grid(debt_tab,['Facture','Client','Total cts','Payé cts','Reste cts','Échéance'])
 def refresh_receivables():fill(debts_table,store.receivables())
 refresh_receivables()
 cheque_tab=ttk.Frame(notebook,padding=12);notebook.add(cheque_tab,text='سجل الشيكات / Registre chèques')
 ch=ttk.Frame(cheque_tab);ch.pack(fill='x');ch_id=field(ch,'ID paiement / رقم الأداء','',10)
 def settle(value):
  try:store.settle_cheque(int(ch_id.get()),value);refresh_cheques();refresh_receivables()
  except Exception as exc:show_error(exc)
 ttk.Button(ch,text='تحصيل / Encaissé',command=lambda:settle(True)).pack(side='left',padx=5)
 ttk.Button(ch,text='مرفوض / Rejeté',command=lambda:settle(False)).pack(side='left',padx=5)
 cheques_table=grid(cheque_tab,['Paiement','N° chèque','Banque','Échéance','Montant cts','État'])
 def refresh_cheques():fill(cheques_table,store.cheque_register())
 refresh_cheques()
 # V16: read-only financial follow-up and export.
 follow_tab=ttk.Frame(notebook,padding=12);notebook.add(follow_tab,text='متابعة الديون / Suivi crédit')
 fr=ttk.Frame(follow_tab);fr.pack(fill='x')
 follow_id=field(fr,'ID client','1',9)
 follow_table=grid(follow_tab,['Facture','Date','Échéance','Total cts','Encaissé cts','Chèques en attente cts','Reste cts'])
 def view_statement():
  try:
   rows=customer_reports.statement(int(follow_id.get()))
   fill(follow_table,[(r['invoice_id'],r['date'],r['due_date'],r['total_cents'],r['collected_cents'],r['pending_cheques_cents'],r['unpaid_cents']) for r in rows])
  except Exception as exc:show_error(exc)
 def export_statement():
  try:
   target=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')])
   if target:
    n=customer_reports.export_statement(int(follow_id.get()),target)
    messagebox.showinfo('Export / تصدير',f'{n} factures exportées / تم تصدير {n} فواتير')
  except Exception as exc:show_error(exc)
 ttk.Button(fr,text='كشف حساب / Relevé',command=view_statement).pack(side='left',padx=4)
 ttk.Button(fr,text='تصدير CSV / Exporter',command=export_statement).pack(side='left',padx=4)
 def show_due():
  try:
   overdue=customer_reports.aging();checks=customer_reports.cheques_due()
   text='\n'.join(f'Facture {x[0]} / {x[1]} : {money(x[3])} DH ({x[4]} jours)' for x in overdue if x[5]=='overdue')
   messagebox.showinfo('Échéances / الاستحقاقات',f'Dettes en retard:\n{text or "Aucune"}\n\nChèques à présenter: {len(checks)}')
  except Exception as exc:show_error(exc)
 ttk.Button(fr,text='الاستحقاقات / Échéances',command=show_due).pack(side='left',padx=4)

# V18: supplier account UI. Transactions are executed through the permission-checked engine.
if 'finance' in PERMISSIONS[store.current_user[2]]:
 supplier_finance=ttk.Frame(notebook,padding=12)
 notebook.add(supplier_finance,text='حسابات الموردين / Comptes fournisseurs')
 sf=ttk.Frame(supplier_finance);sf.pack(fill='x')
 sf_purchase=field(sf,'N° achat / ID achat','',9)
 sf_amount=field(sf,'Montant DH / المبلغ','0',12)
 sf_method=field(sf,'Mode cash/bank/cheque','cash',14)
 sf_ref=field(sf,'Référence / المرجع','',14)
 sf_cheque=field(sf,'N° chèque / رقم الشيك','',13)
 sf_bank=field(sf,'Banque / البنك','',13)
 sf_due=field(sf,'Échéance YYYY-MM-DD','',17)
 def supplier_payment():
  try:
   ident=store.settle_supplier_invoice(str(uuid.uuid4()),int(sf_purchase.get()),sf_amount.get(),sf_method.get().strip(),sf_ref.get().strip(),sf_cheque.get().strip(),sf_bank.get().strip(),sf_due.get().strip() or None)
   refresh_supplier_accounts();messagebox.showinfo('Règlement / أداء',f'Enregistré / تم التسجيل #{ident}')
  except Exception as exc:show_error(exc)
 ttk.Button(sf,text='تسجيل تسديد المورد / Régler',command=supplier_payment).pack(side='left',padx=4)
 supplier_balances_table=grid(supplier_finance,['ID fournisseur','Fournisseur','Achats cts','Payé cts','Reste cts'])
 def refresh_supplier_accounts():fill(supplier_balances_table,store.supplier_balances())
 ttk.Button(supplier_finance,text='تحديث أرصدة الموردين / Actualiser',command=refresh_supplier_accounts).pack(anchor='w')
 srow=ttk.Frame(supplier_finance);srow.pack(fill='x')
 supplier_id_query=field(srow,'ID fournisseur / المورد','',10)
 def supplier_statement_view():
  try:
   purchases,payments=store.supplier_statement(int(supplier_id_query.get()))
   fill(supplier_purchase_table,purchases)
   fill(supplier_payment_table,payments)
  except Exception as exc:show_error(exc)
 ttk.Button(srow,text='كشف الحساب / Relevé',command=supplier_statement_view).pack(side='left')
 supplier_purchase_table=grid(supplier_finance,['Achat ID','Référence','Date','Total cts','Payé cts'])
 supplier_payment_table=grid(supplier_finance,['ID','Achat ID','Montant cts','Mode','État','Référence','Chèque','Banque','Échéance'])
 cheque_actions=ttk.Frame(supplier_finance);cheque_actions.pack(fill='x')
 supplier_cheque_id=field(cheque_actions,'ID règlement chèque','',10)
 def supplier_cheque_result(cleared):
  if not messagebox.askyesno('Confirmation', 'Confirmer le changement de statut du chèque ?'):return
  try:
   store.resolve_supplier_cheque(int(supplier_cheque_id.get()),cleared)
   refresh_supplier_accounts()
   if supplier_id_query.get().strip():supplier_statement_view()
   messagebox.showinfo('OK','Statut enregistré / تم تحديث الحالة')
  except Exception as exc:show_error(exc)
 ttk.Button(cheque_actions,text='صرف الشيك / Débité',command=lambda:supplier_cheque_result(True)).pack(side='left',padx=5)
 ttk.Button(cheque_actions,text='رفض الشيك / Rejeté',command=lambda:supplier_cheque_result(False)).pack(side='left',padx=5)
 refresh_supplier_accounts()

# V18: multi-item wholesale basket (atomic sale through existing sale_tiered engine).
if 'sales' in PERMISSIONS[store.current_user[2]]:
 multi_tab=ttk.Frame(notebook,padding=12)
 notebook.add(multi_tab,text='فاتورة متعددة / Panier multi-articles')
 mr=ttk.Frame(multi_tab);mr.pack(fill='x')
 mb_code=field(mr,'Barcode','',18);mb_qty=field(mr,'Quantité','1',8)
 mb_unit=field(mr,'Unité piece/carton','piece',12)
 mb_tier=field(mr,'Tarif detail/demi_gros/gros','gros',19)
 multi_lines=[]
 multi_table=grid(multi_tab,['Barcode','Qté','Unité','Tarif'])
 def add_multi_line():
  try:
   code=mb_code.get().strip();qty=int(mb_qty.get());unit=mb_unit.get().strip();tier=mb_tier.get().strip()
   if not code or qty<=0 or unit not in ('piece','carton','boite') or tier not in ('detail','demi_gros','gros'):raise ValueError('Ligne invalide / سطر غير صحيح')
   if not store.db.execute('SELECT 1 FROM products WHERE barcode=?',(code,)).fetchone():raise ValueError('Barcode inconnu')
   multi_lines.append((code,qty,unit,tier));fill(multi_table,multi_lines);mb_code.set('')
  except Exception as exc:show_error(exc)
 ttk.Button(mr,text='إضافة للسلة / Ajouter',command=add_multi_line).pack(side='left',padx=5)
 multi_bottom=ttk.Frame(multi_tab);multi_bottom.pack(fill='x')
 multi_received=field(multi_bottom,'Reçu DH / المقبوض','0',12)
 def remove_multi_line():
  selected=multi_table.selection()
  if selected:
   idx=multi_table.index(selected[0]);multi_lines.pop(idx);fill(multi_table,multi_lines)
 def submit_multi_sale():
  if not multi_lines:return show_error(ValueError('Panier vide / السلة فارغة'))
  if not messagebox.askyesno('Confirmer / تأكيد','Valider la vente ? / تأكيد البيع؟'):return
  try:
   sale_id,total,change=store.sale_tiered(str(uuid.uuid4()),list(multi_lines),multi_received.get())
   multi_lines.clear();fill(multi_table,[]);refresh_products();refresh_history()
   messagebox.showinfo('Vente / بيع',f'Vente #{sale_id}\nTotal: {money(total)} DH\nMonnaie: {money(change)} DH')
  except Exception as exc:show_error(exc)
 ttk.Button(multi_bottom,text='حذف السطر / Supprimer',command=remove_multi_line).pack(side='left',padx=6)
 ttk.Button(multi_bottom,text='تأكيد الفاتورة / Valider',command=submit_multi_sale).pack(side='left',padx=6)
 # V20: the same multi-item basket can be issued on customer credit.
 # CreditStore.credit_sale validates prices, stock, FEFO, credit limit and deposit atomically.
 credit_controls=ttk.LabelFrame(multi_tab,text='Vente à crédit / بيع بالدين (panier multi-articles)',padding=8)
 credit_controls.pack(fill='x',pady=8)
 mc_customer=field(credit_controls,'ID client / رقم الزبون','',10)
 mc_deposit=field(credit_controls,'Acompte espèces DH / تسبيق نقدي','0',13)
 mc_due=field(credit_controls,'Échéance YYYY-MM-DD / الاستحقاق','',16)
 def submit_multi_credit():
  if not multi_lines:return show_error(ValueError('Panier vide / السلة فارغة'))
  if not messagebox.askyesno('Confirmer / تأكيد','Enregistrer la facture à crédit ? / تسجيل فاتورة بالدين؟'):return
  try:
   customer=int(mc_customer.get())
   due=mc_due.get().strip() or None
   iid,sid,total=store.credit_sale(str(uuid.uuid4()),customer,list(multi_lines),mc_deposit.get(),due)
   multi_lines.clear();fill(multi_table,[]);refresh_products();refresh_history()
   messagebox.showinfo('Crédit / دين',f'Facture client #{iid} / Vente #{sid}\nTotal: {money(total)} DH\nAcompte: {mc_deposit.get()} DH')
  except Exception as exc:show_error(exc)
 ttk.Button(credit_controls,text='تأكيد فاتورة بالدين / Valider à crédit',command=submit_multi_credit).pack(side='left',padx=5)
 ttk.Label(multi_tab,text='Les chèques sont enregistrés dans les règlements client, pas comme espèces. / الشيكات تسجل كتسديدات مستقلة ولا تعتبر نقداً.').pack(anchor='w')


def run_integrity_diagnostic():
 try:
  from diagnostics import inspect,save_json
  report=inspect(store.path)
  messagebox.showinfo('Diagnostic / فحص البيانات',f"Findings / ملاحظات: {report['total_findings']}\n"+'\n'.join(f'{k}: {v}' for k,v in report['checks'].items()))
  filename=filedialog.asksaveasfilename(title='Save JSON diagnostic',defaultextension='.json',filetypes=[('JSON','*.json')])
  if filename:save_json(report,filename)
 except Exception as exc:show_error(exc)
ttk.Button(pages['backup'],text='فحص سلامة البيانات / Diagnostic intégrité',command=run_integrity_diagnostic).pack(anchor='w',pady=8)

root.mainloop()
