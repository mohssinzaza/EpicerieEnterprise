import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from supplier_accounts import CommercialStore
from cash_movements import export_movements_csv

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=CommercialStore(Path(self.tmp.name)/'shop.sqlite')
        self.addCleanup(self.store.close)
        self.store.bootstrap('admin','very-secure-password-2026')
        self.store.login('admin','very-secure-password-2026')
        self.store.add_product('A','Sugar','10','4',30)
        self.store.open_cash('100')

    def test_running_balance(self):
        self.store.sale('s1',[('A',2)],'20')
        path=export_movements_csv(self.store,Path(self.tmp.name)/'report.csv')
        with path.open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.reader(f))
        self.assertEqual(rows[0][-1],'Running balance / الرصيد بالسنتيم')
        self.assertEqual([r[-1] for r in rows if r[0] in ('opening','cash_sale')],['10000','12000'])
        self.assertEqual(next(r for r in rows if r[0]=='EXPECTED / المتوقع')[-1],'12000')

    def test_no_partial_file_when_publish_fails(self):
        target=Path(self.tmp.name)/'report.csv'
        with patch('cash_movements.os.link',side_effect=OSError('disk error')):
            with self.assertRaises(OSError):export_movements_csv(self.store,target)
        self.assertFalse(target.exists())
        self.assertEqual(list(Path(self.tmp.name).glob('.cash-export-*')),[])

    def test_no_overwrite(self):
        target=Path(self.tmp.name)/'report.csv'
        target.write_text('existing',encoding='utf-8')
        with self.assertRaises(FileExistsError):export_movements_csv(self.store,target)
        self.assertEqual(target.read_text(encoding='utf-8'),'existing')

    def test_snapshot_mismatch_blocks_export(self):
        target=Path(self.tmp.name)/'report.csv'
        from cash_reconciliation import CashReadiness
        with patch('cash_movements.inspect',return_value=CashReadiness(1,999,(),True)):
            with self.assertRaises(ValueError):export_movements_csv(self.store,target)
        self.assertFalse(target.exists())
