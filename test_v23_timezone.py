import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from profit_reports import utc_query_bounds


class LocalPeriodTests(unittest.TestCase):
    @staticmethod
    def expected_utc(local_date):
        local_midnight = dt.datetime.combine(
            dt.date.fromisoformat(local_date), dt.time.min,
            tzinfo=ZoneInfo('Africa/Casablanca')
        )
        return local_midnight.astimezone(dt.timezone.utc).isoformat()

    def test_morocco_winter_day(self):
        self.assertEqual(
            utc_query_bounds('day', '2026-11-22'),
            (self.expected_utc('2026-11-22'), self.expected_utc('2026-11-23'))
        )

    def test_utc_day(self):
        self.assertEqual(
            utc_query_bounds('day', '2026-11-22', 'UTC'),
            ('2026-11-22T00:00:00+00:00', '2026-11-23T00:00:00+00:00')
        )

    def test_week(self):
        self.assertEqual(
            utc_query_bounds('week', '2026-11-22'),
            (self.expected_utc('2026-11-16'), self.expected_utc('2026-11-23'))
        )

    def test_ramadan_transition_varies(self):
        a, b = utc_query_bounds('month', '2026-02-15')
        self.assertEqual(a, self.expected_utc('2026-02-01'))
        self.assertEqual(b, self.expected_utc('2026-03-01'))
        self.assertLess(dt.datetime.fromisoformat(a), dt.datetime.fromisoformat(b))
