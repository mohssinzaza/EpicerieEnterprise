import ast
import unittest
from pathlib import Path

class InventoryUIWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
        cls.tree=ast.parse(cls.source)
    def test_audit_callback_exists(self):
        self.assertIn('audit_inventory', [x.name for x in ast.walk(self.tree) if isinstance(x,ast.FunctionDef)])
    def test_export_callback_exists(self):
        self.assertIn('export_inventory_audit', [x.name for x in ast.walk(self.tree) if isinstance(x,ast.FunctionDef)])
    def test_report_permissions_checked_by_backend(self):
        backend=(Path(__file__).resolve().parents[1]/'inventory_reconciliation.py').read_text(encoding='utf-8')
        self.assertIn("store.require('reports')",backend)
    def test_admin_only_controls(self):
        self.assertIn("if store.current_user[2]=='admin':",self.source)
        self.assertIn('command=audit_inventory',self.source)
        self.assertIn('command=export_inventory_audit',self.source)
