import datetime as dt
import unittest
from profit_reports import utc_query_bounds

class LocalPeriodTests(unittest.TestCase):
 def test_morocco_winter_day(self):
  self.assertEqual(utc_query_bounds('day','2026-11-22'),('2026-11-21T23:00:00+00:00','2026-11-22T23:00:00+00:00'))
 def test_utc_day(self):
  self.assertEqual(utc_query_bounds('day','2026-11-22','UTC'),('2026-11-22T00:00:00+00:00','2026-11-23T00:00:00+00:00'))
 def test_week(self):
  a,b=utc_query_bounds('week','2026-11-22')
  self.assertEqual((a,b),('2026-11-15T23:00:00+00:00','2026-11-22T23:00:00+00:00'))
 def test_ramadan_transition_varies(self):
  from zoneinfo import ZoneInfo
  zone=ZoneInfo('Africa/Casablanca')
  # Ensure boundaries use independent timezone conversions, not a fixed UTC offset.
  a,b=utc_query_bounds('month','2026-02-15')
  self.assertLess(dt.datetime.fromisoformat(a),dt.datetime.fromisoformat(b))
