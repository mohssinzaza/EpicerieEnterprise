import unittest
from verified_profit_export import safe_spreadsheet_cell


class CsvSafetyTests(unittest.TestCase):
    def test_formula_prefixes_are_escaped(self):
        for value in ('=1+1', '+SUM(1,2)', '-2+3', '@SUM(A1:A2)', '  =HYPERLINK("x")', '\t=2'):
            with self.subTest(value=value):
                self.assertEqual(safe_spreadsheet_cell(value), "'" + value)

    def test_normal_text_and_numeric_values_unchanged(self):
        for value in ('normal', 'Africa/Casablanca', 'VERIFIED', '2026-11-22', 42, None):
            with self.subTest(value=value):
                self.assertEqual(safe_spreadsheet_cell(value), value)
