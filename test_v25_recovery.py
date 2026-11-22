from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from engine import Store
from recovery import inspect_database, restore_backup

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.active=self.dir/'active.db';self.backup=self.dir/'backup.db'
        s=Store(self.active);s.add_product('111','Sugar',10,7,20);s.backup(self.backup);s.close()
    def test_inspect(self):
        self.assertEqual(inspect_database(self.backup)['products'],1)
    def test_restore_preserves_old_database(self):
        s=Store(self.active);s.add_product('222','Milk',12,9,4);s.close()
        restore_backup(self.backup,self.active)
        self.assertEqual(inspect_database(self.active)['products'],1)
        self.assertEqual(inspect_database(self.dir/'active.before_restore.db')['products'],2)
    def test_reject_non_database(self):
        bad=self.dir/'bad.db';bad.write_bytes(b'not a database')
        with self.assertRaises(sqlite3.DatabaseError):restore_backup(bad,self.active)
        self.assertEqual(inspect_database(self.active)['products'],1)
    def test_reject_unrelated_sqlite(self):
        unrelated=self.dir/'other.db'
        with closing(sqlite3.connect(unrelated)) as db:db.execute('CREATE TABLE test(id)')
        with self.assertRaises(ValueError):restore_backup(unrelated,self.active)
    def test_never_overwrite_previous_snapshot(self):
        restore_backup(self.backup,self.active)
        with self.assertRaises(FileExistsError):restore_backup(self.backup,self.active)
    def test_refuse_journal(self):
        (self.dir/'active.db-wal').write_bytes(b'')
        with self.assertRaises(RuntimeError):restore_backup(self.backup,self.active)
