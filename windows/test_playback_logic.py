import unittest
from datetime import datetime, timedelta
from playback_logic import next_occurrence, should_stop_at_playlist_end, duration_clock

class PlaybackLogicTests(unittest.TestCase):
    def test_playlist_finishes_once_without_loop(self):
        self.assertFalse(should_stop_at_playlist_end("end_of_playlist", 0, 1))
        self.assertTrue(should_stop_at_playlist_end("end_of_playlist", 1, 1))
        self.assertFalse(should_stop_at_playlist_end("end_of_playlist", 1, 3))
        self.assertTrue(should_stop_at_playlist_end("end_of_playlist", 3, 3))
    def test_timed_playback_may_repeat(self):
        for mode in ("duration", "clock"):
            self.assertFalse(should_stop_at_playlist_end(mode, 3, 3))
    def test_next_morning(self):
        before = datetime(2026, 10, 17, 5, 59)
        self.assertEqual(next_occurrence(6, 0, before), datetime(2026, 10, 17, 6, 0))
        after = datetime(2026, 10, 17, 6, 0)
        self.assertEqual(next_occurrence(6, 0, after), datetime(2026, 10, 18, 6, 0))
    def test_cross_midnight_stop_clock(self):
        self.assertEqual(next_occurrence(1, 0, datetime(2026, 10, 17, 23, 0)),
                         datetime(2026, 10, 18, 1, 0))
    def test_duration_format(self):
        self.assertEqual(duration_clock(3_661), "01:01:01")
    def test_invalid_clock_time(self):
        with self.assertRaises(ValueError):
            next_occurrence(24, 0, datetime(2026, 1, 1))

if __name__ == "__main__":
    unittest.main()
