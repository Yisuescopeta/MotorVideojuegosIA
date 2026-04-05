"""
tests/test_time_manager.py

Unit tests for engine.core.time_manager.TimeManager.

All pyray calls are mocked so no display or raylib window is required.
"""

import math
import unittest
from unittest.mock import patch

from engine.core.time_manager import TimeManager


class SanitizeFrameTimeTests(unittest.TestCase):
    """Direct unit tests for the _sanitize_frame_time() static helper."""

    def test_normal_value_passes_through(self) -> None:
        self.assertAlmostEqual(TimeManager._sanitize_frame_time(0.016), 0.016)

    def test_none_returns_zero(self) -> None:
        self.assertEqual(TimeManager._sanitize_frame_time(None), 0.0)

    def test_negative_returns_zero(self) -> None:
        self.assertEqual(TimeManager._sanitize_frame_time(-0.5), 0.0)

    def test_nan_returns_zero(self) -> None:
        self.assertEqual(TimeManager._sanitize_frame_time(float("nan")), 0.0)

    def test_positive_inf_returns_zero(self) -> None:
        self.assertEqual(TimeManager._sanitize_frame_time(float("inf")), 0.0)

    def test_negative_inf_returns_zero(self) -> None:
        self.assertEqual(TimeManager._sanitize_frame_time(float("-inf")), 0.0)

    def test_value_above_cap_is_clamped(self) -> None:
        self.assertAlmostEqual(TimeManager._sanitize_frame_time(0.5), TimeManager._MAX_FRAME_TIME)

    def test_value_exactly_at_cap_passes_through(self) -> None:
        self.assertAlmostEqual(
            TimeManager._sanitize_frame_time(TimeManager._MAX_FRAME_TIME),
            TimeManager._MAX_FRAME_TIME,
        )

    def test_zero_passes_through(self) -> None:
        self.assertEqual(TimeManager._sanitize_frame_time(0.0), 0.0)

    def test_non_numeric_string_returns_zero(self) -> None:
        self.assertEqual(TimeManager._sanitize_frame_time("bad"), 0.0)

    def test_integer_value_is_accepted(self) -> None:
        # Integers > cap should be clamped; small integers pass through.
        self.assertEqual(TimeManager._sanitize_frame_time(0), 0.0)
        self.assertAlmostEqual(TimeManager._sanitize_frame_time(1), TimeManager._MAX_FRAME_TIME)


class TimeManagerUpdateTests(unittest.TestCase):
    """Tests for TimeManager.update() with mocked pyray calls."""

    def _make_tm(self) -> TimeManager:
        return TimeManager()

    def test_normal_frame_time_updates_delta_and_total(self) -> None:
        tm = self._make_tm()
        with patch("pyray.get_frame_time", return_value=0.016), \
             patch("pyray.get_fps", return_value=60):
            tm.update()
        self.assertAlmostEqual(tm.delta_time, 0.016)
        self.assertAlmostEqual(tm.total_time, 0.016)
        self.assertEqual(tm.fps, 60)
        self.assertEqual(tm.frame_count, 1)

    def test_none_frame_time_does_not_crash_and_gives_zero_delta(self) -> None:
        tm = self._make_tm()
        with patch("pyray.get_frame_time", return_value=None), \
             patch("pyray.get_fps", return_value=60):
            tm.update()  # must NOT raise TypeError
        self.assertEqual(tm.delta_time, 0.0)
        self.assertEqual(tm.total_time, 0.0)

    def test_negative_frame_time_gives_zero_delta(self) -> None:
        tm = self._make_tm()
        with patch("pyray.get_frame_time", return_value=-0.5), \
             patch("pyray.get_fps", return_value=60):
            tm.update()
        self.assertEqual(tm.delta_time, 0.0)

    def test_nan_frame_time_gives_zero_delta(self) -> None:
        tm = self._make_tm()
        with patch("pyray.get_frame_time", return_value=float("nan")), \
             patch("pyray.get_fps", return_value=60):
            tm.update()
        self.assertEqual(tm.delta_time, 0.0)
        self.assertFalse(math.isnan(tm.total_time))

    def test_large_frame_time_is_capped(self) -> None:
        tm = self._make_tm()
        with patch("pyray.get_frame_time", return_value=5.0), \
             patch("pyray.get_fps", return_value=1):
            tm.update()
        self.assertAlmostEqual(tm.delta_time, TimeManager._MAX_FRAME_TIME)

    def test_none_fps_gives_zero_fps(self) -> None:
        tm = self._make_tm()
        with patch("pyray.get_frame_time", return_value=0.016), \
             patch("pyray.get_fps", return_value=None):
            tm.update()
        self.assertEqual(tm.fps, 0)

    def test_valid_fps_is_stored(self) -> None:
        tm = self._make_tm()
        with patch("pyray.get_frame_time", return_value=0.016), \
             patch("pyray.get_fps", return_value=120):
            tm.update()
        self.assertEqual(tm.fps, 120)

    def test_frame_count_increments_each_call(self) -> None:
        tm = self._make_tm()
        with patch("pyray.get_frame_time", return_value=0.016), \
             patch("pyray.get_fps", return_value=60):
            tm.update()
            tm.update()
            tm.update()
        self.assertEqual(tm.frame_count, 3)

    def test_total_time_accumulates_across_frames(self) -> None:
        tm = self._make_tm()
        with patch("pyray.get_frame_time", return_value=0.016), \
             patch("pyray.get_fps", return_value=60):
            tm.update()
            tm.update()
        self.assertAlmostEqual(tm.total_time, 0.032, places=6)

    def test_total_time_not_corrupted_by_none_frame(self) -> None:
        """A None frame-time must not corrupt the running total."""
        tm = self._make_tm()
        with patch("pyray.get_frame_time", return_value=0.016), \
             patch("pyray.get_fps", return_value=60):
            tm.update()
        with patch("pyray.get_frame_time", return_value=None), \
             patch("pyray.get_fps", return_value=0):
            tm.update()
        # total should still be only 0.016 (the None frame added 0)
        self.assertAlmostEqual(tm.total_time, 0.016, places=6)


class TimeManagerUpdateManualTests(unittest.TestCase):
    """Tests for TimeManager.update_manual() — headless / test path."""

    def test_normal_dt_works_as_before(self) -> None:
        tm = TimeManager()
        tm.update_manual(0.016)
        self.assertAlmostEqual(tm.delta_time, 0.016)
        self.assertAlmostEqual(tm.total_time, 0.016)
        self.assertEqual(tm.fps, 62)  # int(1/0.016) == 62

    def test_zero_dt_gives_zero_fps_without_crash(self) -> None:
        tm = TimeManager()
        tm.update_manual(0.0)  # must NOT raise ZeroDivisionError
        self.assertEqual(tm.delta_time, 0.0)
        self.assertEqual(tm.fps, 0)

    def test_none_dt_does_not_crash(self) -> None:
        tm = TimeManager()
        tm.update_manual(None)  # type: ignore[arg-type]
        self.assertEqual(tm.delta_time, 0.0)
        self.assertEqual(tm.total_time, 0.0)

    def test_large_dt_is_capped(self) -> None:
        tm = TimeManager()
        tm.update_manual(10.0)
        self.assertAlmostEqual(tm.delta_time, TimeManager._MAX_FRAME_TIME)

    def test_frame_count_increments(self) -> None:
        tm = TimeManager()
        tm.update_manual(0.016)
        tm.update_manual(0.016)
        self.assertEqual(tm.frame_count, 2)

    def test_time_alias_equals_total_time(self) -> None:
        tm = TimeManager()
        tm.update_manual(0.05)
        self.assertAlmostEqual(tm.time, tm.total_time)


if __name__ == "__main__":
    unittest.main()
