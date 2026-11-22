"""Offline recovery GUI for Windows; run with the main POS closed."""
# Headless startup check for the packaged recovery executable.
# This runs before Tk is initialized and does not touch the shop database.
import sys as _recovery_sys
if len(_recovery_sys.argv) == 3 and _recovery_sys.argv[1] == '--self-test':
    from pathlib import Path as _RecoveryPath
    from recovery import inspect_database as _inspect_database, restore_backup as _restore_backup
    from sqlite3 import connect as _sqlite_connect
    from tempfile import TemporaryDirectory as _TemporaryDirectory
    try:
        with _TemporaryDirectory(prefix='epicerie_recovery_smoke_') as _tmp:
            _db = _RecoveryPath(_tmp) / 'probe.db'
            with _sqlite_connect(_db) as _conn:
                _conn.execute('CREATE TABLE recovery_probe (id INTEGER PRIMARY KEY)')
                _conn.execute('INSERT INTO recovery_probe VALUES (1)')
            with _sqlite_connect(_db) as _conn:
                assert _conn.execute('SELECT COUNT(*) FROM recovery_probe').fetchone()[0] == 1
        _RecoveryPath(_recovery_sys.argv[2]).write_text('PASS: recovery startup and SQLite', encoding='utf-8')
    except Exception as _exc:
        _RecoveryPath(_recovery_sys.argv[2]).write_text('FAIL: ' + str(_exc), encoding='utf-8')
        raise SystemExit(1)
    raise SystemExit(0)
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from recovery import inspect_database, restore_backup

root=tk.Tk();root.title('Épicerie Enterprise | استرجاع البيانات / Restauration');root.geometry('710x320')
base=Path(os.getenv('LOCALAPPDATA') or Path.home())/'EpicerieEnterpriseV11'/'enterprise_v14.db'
source=tk.StringVar();destination=tk.StringVar(value=str(base))
for row,(label,var,save) in enumerate([('Backup / النسخة الاحتياطية',source,False),('Database / قاعدة البيانات',destination,True)]):
    ttk.Label(root,text=label).grid(row=row*2,column=0,sticky='w',padx=12,pady=(14,2))
    ttk.Entry(root,textvariable=var,width=74).grid(row=row*2+1,column=0,padx=12,sticky='ew')
    ttk.Button(root,text='Browse / اختيار',command=lambda v=var,s=save:v.set(filedialog.asksaveasfilename(defaultextension='.db') if s else filedialog.askopenfilename(filetypes=[('SQLite databases','*.db'),('All files','*.*')]))).grid(row=row*2+1,column=1,padx=8)

def run_restore():
    try:
        stats=inspect_database(source.get())
        if not messagebox.askyesno('Confirm / تأكيد',f'Close the POS before proceeding!\nأغلق برنامج المحل أولاً.\n\nBackup: {stats["products"]} products, {stats["sales"]} sales.\n\nThe existing database will be saved as .before_restore.db.\nContinue?'):
            return
        restore_backup(source.get(),destination.get())
        messagebox.showinfo('Success / نجاح','Restore completed. / اكتمل الاسترجاع. تحقق من البيانات قبل الاستخدام.')
    except Exception as exc:messagebox.showerror('Restore failed / فشل الاسترجاع',str(exc))

ttk.Label(root,text='IMPORTANT: Close Épicerie Enterprise before restoring. / مهم: أغلق البرنامج قبل الاسترجاع.',foreground='#9a3412').grid(row=4,column=0,columnspan=2,padx=12,pady=16)
ttk.Button(root,text='Restore verified backup / استرجاع النسخة بعد التحقق',command=run_restore).grid(row=5,column=0,columnspan=2,pady=5)
root.columnconfigure(0,weight=1);root.mainloop()
