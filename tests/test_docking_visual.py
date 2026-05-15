"""Tests for docking visual helpers: rect computation, hit-testing, state transitions."""
import unittest

from engine.editor.ui.dock_render import hit_test_floating_window
from engine.editor.ui_core.dock_rects import (
    compute_auto_hide_collapsed_rect,
    compute_floating_window_rects,
)
from engine.editor.ui_core.docking import DockLayout, FloatingDockWindow


class TestComputeFloatingRects(unittest.TestCase):
    """Tests for compute_floating_window_rects."""

    def test_open_windows_returned(self):
        """Only open floating windows get rects."""
        layout = DockLayout.default()
        layout.floating_windows = [
            FloatingDockWindow(tab_id="tab_a", x=100, y=200, width=300, height=400, is_open=True),
            FloatingDockWindow(tab_id="tab_b", x=50, y=60, width=200, height=100, is_open=False),
        ]
        rects = compute_floating_window_rects(layout)
        self.assertEqual(len(rects), 1)
        self.assertIn("tab_a", rects)
        self.assertNotIn("tab_b", rects)

    def test_rect_matches_coordinates(self):
        """Floating window rect matches model coordinates."""
        layout = DockLayout.default()
        layout.floating_windows = [
            FloatingDockWindow(tab_id="tab_c", x=10.5, y=20.5, width=320.0, height=240.0, is_open=True),
        ]
        rects = compute_floating_window_rects(layout)
        self.assertEqual(rects["tab_c"], (10.5, 20.5, 320.0, 240.0))

    def test_empty_when_no_windows(self):
        """Returns empty dict when no floating windows."""
        layout = DockLayout.default()
        layout.floating_windows = []
        rects = compute_floating_window_rects(layout)
        self.assertEqual(rects, {})


class TestAutoHideCollapsedRect(unittest.TestCase):
    """Tests for compute_auto_hide_collapsed_rect."""

    def test_left_edge(self):
        """Strip at left edge of area."""
        result = compute_auto_hide_collapsed_rect((0, 50, 200, 400), "left")
        self.assertEqual(result, (0, 50, 24.0, 400))

    def test_right_edge(self):
        """Strip at right edge of area."""
        result = compute_auto_hide_collapsed_rect((0, 50, 200, 400), "right")
        self.assertEqual(result, (176, 50, 24.0, 400))

    def test_bottom_edge(self):
        """Strip at bottom edge of area."""
        result = compute_auto_hide_collapsed_rect((0, 50, 200, 400), "bottom")
        self.assertEqual(result, (0, 426.0, 200, 24.0))

    def test_custom_thickness(self):
        """Custom strip thickness respected."""
        result = compute_auto_hide_collapsed_rect((0, 0, 500, 300), "left", strip_thickness=32.0)
        self.assertEqual(result, (0, 0, 32.0, 300))

    def test_unknown_edge_raises(self):
        """Unknown edge raises ValueError."""
        with self.assertRaises(ValueError):
            compute_auto_hide_collapsed_rect((0, 0, 100, 100), "top")


class TestHitTestFloatingWindow(unittest.TestCase):
    """Tests for hit_test_floating_window pure geometry."""

    def setUp(self):
        self.rect = (100.0, 200.0, 320.0, 240.0)
        self.title = "Test Window"

    def test_outside_rect(self):
        """Mouse outside rect returns all False."""
        result = hit_test_floating_window(self.rect, self.title, (50, 50))
        self.assertFalse(any(result.values()))

    def test_title_hit(self):
        """Mouse in title bar area returns title_hit=True."""
        result = hit_test_floating_window(self.rect, self.title, (200, 205))
        self.assertTrue(result["title_hit"])
        self.assertFalse(result["close_hit"])
        self.assertFalse(result["dock_hit"])

    def test_close_button_hit(self):
        """Mouse in close button zone."""
        # Close button is at right side: x=rect.x+rect.w-20-4 to x=rect.x+rect.w-4
        result = hit_test_floating_window(self.rect, self.title, (412, 208))
        self.assertTrue(result["close_hit"])

    def test_dock_button_hit(self):
        """Mouse in dock button zone."""
        # Dock button is left of close: x=close_x-18 to x=close_x-2
        result = hit_test_floating_window(self.rect, self.title, (394, 208))
        self.assertTrue(result["dock_hit"])

    def test_resize_hit_bottom_right(self):
        """Mouse in resize margin zone."""
        result = hit_test_floating_window(self.rect, self.title, (418, 438))
        self.assertTrue(result["resize_hit"])

    def test_resize_hit_right_edge(self):
        """Mouse at right edge triggers resize."""
        result = hit_test_floating_window(self.rect, self.title, (418, 300))
        self.assertTrue(result["resize_hit"])

    def test_body_hit(self):
        """Mouse in body area (not title, not resize)."""
        result = hit_test_floating_window(self.rect, self.title, (200, 300))
        self.assertTrue(result["body_hit"])


class TestDragPreviewZoneDetection(unittest.TestCase):
    """Tests for drag preview zone highlight detection logic."""

    def test_highlight_matching_zone(self):
        """Point inside a zone should highlight that zone."""
        zones = [
            ("hierarchy", (0, 50, 200, 400)),
            ("center", (200, 50, 600, 400)),
            ("inspector", (800, 50, 280, 400)),
        ]
        px, py = 100.0, 100.0  # inside hierarchy

        highlight = None
        for zone_id, (zx, zy, zw, zh) in zones:
            if zx <= px <= zx + zw and zy <= py <= zy + zh:
                highlight = zone_id
                break

        self.assertEqual(highlight, "hierarchy")

    def test_no_highlight_outside_all(self):
        """Point outside all zones should not highlight any."""
        zones = [
            ("hierarchy", (0, 50, 200, 400)),
            ("center", (200, 50, 600, 400)),
        ]
        px, py = 9999.0, 9999.0

        highlight = None
        for zone_id, (zx, zy, zw, zh) in zones:
            if zx <= px <= zx + zw and zy <= py <= zy + zh:
                highlight = zone_id
                break

        self.assertIsNone(highlight)


if __name__ == "__main__":
    unittest.main()
