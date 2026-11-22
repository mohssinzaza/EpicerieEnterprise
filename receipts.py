"""Safe, offline HTML receipts for 80 mm thermal printers or browser PDF printing."""
from html import escape
from pathlib import Path
import webbrowser


def receipt_html(store, sale_id, shop_name='Épicerie / محل المواد الغذائية'):
    if type(sale_id) is not int or sale_id <= 0:
        raise ValueError('Invalid sale number')
    sale=store.db.execute('SELECT id,created_at,total_cents,received_cents,change_cents FROM sales WHERE id=?',(sale_id,)).fetchone()
    if sale is None: raise ValueError('Sale not found')
    lines=store.db.execute('SELECT p.name,p.barcode,sl.quantity,sl.unit_price_cents FROM sale_lines sl JOIN products p ON p.id=sl.product_id WHERE sl.sale_id=? ORDER BY sl.id',(sale_id,)).fetchall()
    fmt=lambda n:f'{n/100:.2f}'
    rows=''.join('<tr><td>'+escape(name)+'</td><td>'+str(qty)+'</td><td>'+fmt(price)+'</td><td>'+fmt(qty*price)+'</td></tr>' for name,barcode,qty,price in lines)
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Ticket #{id}</title><style>@page{{size:80mm auto;margin:3mm}}body{{font-family:Arial,'Segoe UI',sans-serif;width:72mm;max-width:100%;margin:0 auto;color:#111;font-size:11px}}h2,p{{text-align:center;margin:6px 0}}table{{width:100%;border-collapse:collapse;table-layout:fixed}}td,th{{border-bottom:1px dashed #888;padding:5px 1px;overflow-wrap:anywhere}}td:not(:first-child),th:not(:first-child){{text-align:right}}td:first-child{{width:40%}}.total{{font-size:16px;font-weight:bold}}.actions{{margin:12px 0}}@media print{{.actions{{display:none}}}}</style></head><body><h2>{shop}</h2><p>Ticket / وصل بيع #{id}<br>{date}</p><table><thead><tr><th>Article / سلعة</th><th>Qté</th><th>PU</th><th>Total</th></tr></thead><tbody>{rows}</tbody></table><p class="total">Total: {total} DH</p><p>Reçu: {received} DH | Monnaie: {change} DH</p><p>Merci / شكراً</p><div class="actions"><button onclick="window.print()">Imprimer / طباعة</button></div></body></html>""".format(id=sale[0],shop=escape(shop_name),date=escape(sale[1]),rows=rows,total=fmt(sale[2]),received=fmt(sale[3]),change=fmt(sale[4]))


def save_receipt(store,sale_id,folder,shop_name='Épicerie / محل المواد الغذائية'):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'ticket_{sale_id}.html'
    path.write_text(receipt_html(store,sale_id,shop_name),encoding='utf-8')
    return path
