import tempfile
import unittest
from pathlib import Path
from inventory_reconciliation import StockDifference, export_stock_differences

class AtomicStockExportTests(unittest.TestCase):
    def test_export_success(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'report.csv'
            export_stock_differences([StockDifference(1,'123','Tea',5,3,2)],target)
            self.assertIn('Tea',target.read_text(encoding='utf-8-sig'))
            self.assertFalse(list(Path(d).glob('*.tmp')))
    def test_failed_serialization_leaves_no_partial_report(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'report.csv'
            def broken():
                yield StockDifference(1,'123','Tea',5,3,2)
                raise RuntimeError('broken stream')
            with self.assertRaises(RuntimeError): export_stock_differences(broken(),target)
            self.assertFalse(target.exists())
            self.assertFalse(list(Path(d).glob('*.tmp')))
    def test_does_not_overwrite_existing_report(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'report.csv'
            target.write_text('original')
            with self.assertRaises(FileExistsError):export_stock_differences([],target)
            self.assertEqual(target.read_text(),'original')
