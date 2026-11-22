"""Offline recovery tool. Close the POS before restoring any backup."""
from contextlib import closing
import os
import sqlite3
import tempfile
from pathlib import Path

REQUIRED_TABLES = {'products', 'sales', 'sale_lines', 'stock_ledger', 'audit'}

def inspect_database(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    # mode=ro avoids accidentally creating a missing database.
    uri = path.resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not REQUIRED_TABLES.issubset(tables):
            raise ValueError('Not an Epicerie Enterprise database')
        if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ValueError('Foreign key check failed')
        return {'products': db.execute('SELECT COUNT(*) FROM products').fetchone()[0],
                'sales': db.execute('SELECT COUNT(*) FROM sales').fetchone()[0]}

def restore_backup(source, destination):
    """Copy validated backup into an offline database; preserve original as .before_restore.db.

    Caller must close POS first. Does not replace an existing recovery snapshot.
    """
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('Source and destination must differ')
    summary = inspect_database(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    snapshot = destination.with_name(destination.stem + '.before_restore.db')
    if snapshot.exists():
        raise FileExistsError(f'Previous recovery snapshot exists: {snapshot}')
    if any(Path(str(destination) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise RuntimeError('Database journal present. Close the POS and checkpoint before restore')
    if destination.exists():
        inspect_database(destination)
        # Preserve existing database, never silently discard it.
        import shutil
        shutil.copy2(destination, snapshot)
        inspect_database(snapshot)
    fd, temporary = tempfile.mkstemp(prefix='.restore_', suffix='.db', dir=destination.parent)
    os.close(fd)
    try:
        # SQLite backup API copies a consistent database snapshot.
        with closing(sqlite3.connect(source)) as incoming, closing(sqlite3.connect(temporary)) as outgoing:
            incoming.backup(outgoing)
        inspect_database(temporary)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return summary

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Epicerie Enterprise offline database recovery')
    parser.add_argument('--inspect', metavar='DB')
    parser.add_argument('--restore', metavar='BACKUP')
    parser.add_argument('--destination', metavar='ACTIVE_DB')
    args = parser.parse_args()
    if args.inspect:
        print(inspect_database(args.inspect))
    elif args.restore and args.destination:
        confirm = input('Close POS first. Type RESTORE to proceed: ')
        if confirm != 'RESTORE': raise SystemExit('Cancelled')
        print('Restored:', restore_backup(args.restore, args.destination))
    else: parser.print_help()
