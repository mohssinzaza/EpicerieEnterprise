import unittest, tempfile
from pathlib import Path
from security import SecureStore
from lot_costing import verified_period_profit

class VerifiedProfitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=SecureStore(str(Path(self.tmp.name)/'test.db'))
        self.store.bootstrap('admin','SafePassword!123')
        self.store.login('admin','SafePassword!123')
    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()
    def test_empty_period(self):
        report=verified_period_profit(self.store,period='month')
        self.assertTrue(report.complete)
        self.assertEqual(report.net_profit_cents,0)
    def test_rejects_unknown_period(self):
        with self.assertRaises(ValueError):
            verified_period_profit(self.store,period='decade')
