"""Offline release gate: tests, account isolation, backup and SQLite integrity.
Does not certify Windows hardware or statutory accounting compliance.
"""
from contextlib import closing
import argparse
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from security import SecureStore


def smoke():
    with tempfile.TemporaryDirectory(prefix='epicerie_release_') as tmp:
        root=Path(tmp)
        db=root/'shop.db'
        store=SecureStore(db)
        try:
            store.bootstrap('admin','TestOnlyAdminPass!2026')
            assert store.login('admin','TestOnlyAdminPass!2026')=='admin'
            store.create_user('cashier','TestOnlyCashierPass!2026','cashier')
            store.add_product('1000000000001','Test product',12,8,10)
            store.logout()
            assert store.login('cashier','TestOnlyCashierPass!2026')=='cashier'
            try:
                store.require('reports')
            except PermissionError:
                pass
            else:
                raise AssertionError('Cashier can access profits')
            try:
                store.require('products')
            except PermissionError:
                pass
            else:
                raise AssertionError('Cashier can modify products')
            sid,total,change=store.sale('release-test-sale',[('1000000000001',2)],24)
            assert total==2400 and change==0
            store.logout()
            assert store.login('admin','TestOnlyAdminPass!2026')=='admin'
            assert store.db.execute('SELECT stock FROM products WHERE barcode=?',('1000000000001',)).fetchone()[0]==8
            backup=root/'verified-backup.db'
            store.backup(backup)
            with closing(sqlite3.connect(backup)) as verify:
                assert verify.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                assert verify.execute('SELECT COUNT(*) FROM sales').fetchone()[0]==1
            assert store.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        finally:
            store.close()
    print('PASS: admin/cashier isolation, sale, stock, backup, integrity')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--skip-tests',action='store_true')
    args=parser.parse_args()
    if not args.skip_tests:
        p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-q'],cwd=Path(__file__).parent)
        if p.returncode: return p.returncode
    smoke()
    return 0

if __name__=='__main__':
    raise SystemExit(main())
