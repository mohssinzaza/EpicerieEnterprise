"""Static checks: FEFO verified profit is selectable for day/week/month."""
import ast
import unittest
from pathlib import Path

class VerifiedProfitGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(Path(__file__).resolve().parents[1]/'app.py').read_text(encoding='utf-8')
        cls.tree=ast.parse(cls.source)
    def test_verified_profit_callback_exists(self):
        self.assertTrue(any(isinstance(n,ast.FunctionDef) and n.name=='refresh_verified_profits' for n in ast.walk(self.tree)))
    def test_callback_uses_period_and_date(self):
        callback=next(n for n in ast.walk(self.tree) if isinstance(n,ast.FunctionDef) and n.name=='refresh_verified_profits')
        source=ast.get_source_segment(self.source,callback)
        self.assertIn('period=profit_period.get()',source)
        self.assertIn('day=profit_date.get().strip()',source)
        self.assertIn('Africa/Casablanca',source)
    def test_unknown_cost_does_not_display_profit(self):
        callback=next(n for n in ast.walk(self.tree) if isinstance(n,ast.FunctionDef) and n.name=='refresh_verified_profits')
        source=ast.get_source_segment(self.source,callback)
        self.assertIn('if r.complete else',source)
        self.assertIn('NON VÉRIFIÉ',source)
    def test_stale_result_invalidated_on_selection_change(self):
        self.assertIn("profit_period.trace_add('write',lambda *_: verified_profit_result.set",self.source)
        self.assertIn("profit_date.trace_add('write',lambda *_: verified_profit_result.set",self.source)
