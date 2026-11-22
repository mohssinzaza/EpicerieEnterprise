
import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from profit_reports import utc_query_bounds


class LocalPeriodTests(unittest.TestCase):
    def expected(self, start, end, zone_name='Africa/Casablanca'):
        zone = ZoneInfo(zone_name)

        def to_utc(day):
            local = dt.datetime.combine(
                dt.date.fromisoformat(day),
                dt.time.min,
                tzinfo=zone
            )
            return local.astimezone(dt.timezone.utc).isoformat()

        return to_utc(start), to_utc(end)

    def test_morocco_winter_day(self):
        self.assertEqual(
            utc_query_bounds('day', '2026-11-22'),
            self.expected('2026-11-22', '2026-11-23')
        )

    def test_utc_day(self):
        self.assertEqual(
            utc_query_bounds('day', '2026-11-22', 'UTC'),
            (
                '2026-11-22T00:00:00+00:00',
                '2026-11-23T00:00:00+00:00'
            )
        )

    def test_week(self):
        self.assertEqual(
            utc_query_bounds('week', '2026-11-22'),
            self.expected('2026-11-16', '2026-11-23')
        )

    def test_ramadan_transition_varies(self):
        a, b = utc_query_bounds('month', '2026-02-15')
        self.assertLess(
            dt.datetime.fromisoformat(a),
            dt.datetime.fromisoformat(b)
        )

