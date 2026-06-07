"""Tests for virtual scroll (E4)."""
import unittest

from engine.editor.ui.virtual_scroll import VirtualScroll


class TestVirtualScroll(unittest.TestCase):
    def test_below_threshold_disabled(self):
        vs = VirtualScroll(row_height=18)
        vs.update(50, 400, 0)
        self.assertFalse(vs.enabled)
        self.assertEqual(vs.first_visible, 0)
        self.assertEqual(vs.last_visible, 50)

    def test_above_threshold_enabled(self):
        vs = VirtualScroll(row_height=18)
        vs.update(200, 400, 0)
        self.assertTrue(vs.enabled)

    def test_visible_range_with_scroll(self):
        vs = VirtualScroll(row_height=18, buffer_rows=0)
        vs.update(500, 360, 180)
        self.assertGreaterEqual(vs.first_visible, 8)
        self.assertLessEqual(vs.last_visible, 32)

    def test_row_y_computation(self):
        vs = VirtualScroll(row_height=20)
        vs.update(500, 400, 100)
        self.assertEqual(vs.row_y(5), 0.0)
        self.assertEqual(vs.row_y(10), 100.0)

    def test_total_height(self):
        vs = VirtualScroll(row_height=18)
        vs.update(100, 400, 0)
        self.assertEqual(vs.total_height, 1800.0)

    def test_no_items(self):
        vs = VirtualScroll()
        vs.update(0, 400, 0)
        self.assertEqual(vs.first_visible, 0)
        self.assertEqual(vs.last_visible, 0)

    def test_buffer_rows(self):
        vs = VirtualScroll(row_height=18, buffer_rows=3)
        vs.update(500, 360, 0)
        first_no_buffer = max(0, 0 - 3)
        self.assertEqual(vs.first_visible, first_no_buffer)


if __name__ == "__main__":
    unittest.main()
