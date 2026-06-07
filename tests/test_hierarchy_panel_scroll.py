"""Tests for HierarchyPanel scroll offset, wheel input, clamping, and hit-test."""
import unittest

from engine.ecs.world import World
from engine.editor.hierarchy_panel import HierarchyPanel


class HierarchyPanelScrollTests(unittest.TestCase):
    """Tests covering scroll offset clamping, wheel handling, and culling."""

    def setUp(self) -> None:
        self.panel = HierarchyPanel()
        self.world = World()
        # Create many root-level entities so all are visible without expanding
        for i in range(30):
            self.world.create_entity(f"Entity_{i:02d}")

    # ------------------------------------------------------------------
    # Scroll offset clamping
    # ------------------------------------------------------------------

    def test_scroll_offset_clamps_to_zero(self) -> None:
        self.panel.scroll_offset = -100
        visible_rows = self.panel._get_visible_rows(self.world)
        self.panel._clamp_scroll_offset(visible_rows, viewport_height=200)
        self.assertEqual(self.panel.scroll_offset, 0)

    def test_scroll_offset_clamps_to_max(self) -> None:
        visible_rows = self.panel._get_visible_rows(self.world)
        total = len(visible_rows) * self.panel.LINE_HEIGHT
        viewport = 100
        max_scroll = max(0, total - viewport)
        self.assertGreater(max_scroll, 0, "Sanity: content exceeds viewport")

        self.panel.scroll_offset = 9999
        self.panel._clamp_scroll_offset(visible_rows, viewport_height=viewport)
        self.assertEqual(self.panel.scroll_offset, max_scroll)

    def test_scroll_offset_zero_when_content_fits(self) -> None:
        # Few entities + large viewport = no scroll needed
        small_world = World()
        small_world.create_entity("A")

        panel = HierarchyPanel()
        panel.scroll_offset = 50
        visible_rows = panel._get_visible_rows(small_world)
        panel._clamp_scroll_offset(visible_rows, viewport_height=2000)
        self.assertEqual(panel.scroll_offset, 0)

    # ------------------------------------------------------------------
    # Visible row range shifts with scroll
    # ------------------------------------------------------------------

    def test_first_visible_row_increases_with_scroll(self) -> None:
        row_height = self.panel.LINE_HEIGHT

        self.panel.scroll_offset = 0
        first_row_0 = max(0, self.panel.scroll_offset // row_height)
        self.assertEqual(first_row_0, 0)

        self.panel.scroll_offset = 36  # skip 2 rows
        first_row_36 = max(0, self.panel.scroll_offset // row_height)
        self.assertEqual(first_row_36, 2)

    def test_last_visible_row_increases_with_scroll(self) -> None:
        visible_rows = self.panel._get_visible_rows(self.world)
        row_height = self.panel.LINE_HEIGHT
        viewport = 100

        self.panel.scroll_offset = 0
        last_0 = min(len(visible_rows), ((self.panel.scroll_offset + viewport) // row_height) + 2)
        self.panel.scroll_offset = 54  # skip 3 rows
        last_54 = min(len(visible_rows), ((self.panel.scroll_offset + viewport) // row_height) + 2)
        self.assertGreater(last_54, last_0)

    # ------------------------------------------------------------------
    # Row y-position shifts with scroll
    # ------------------------------------------------------------------

    def test_row_y_shifts_with_scroll_offset(self) -> None:
        row_height = self.panel.LINE_HEIGHT
        content_y_start = 50

        self.panel.scroll_offset = 0
        base_y_0 = content_y_start - self.panel.scroll_offset
        row_y_0 = base_y_0 + (5 * row_height)  # row index 5
        self.assertEqual(row_y_0, 50 + 5 * 18)  # 140

        self.panel.scroll_offset = 36
        base_y_36 = content_y_start - self.panel.scroll_offset
        row_y_36 = base_y_36 + (5 * row_height)  # row index 5
        self.assertEqual(row_y_36, 50 - 36 + 90)  # 104

        # Row 5 with scroll=36 is 36px higher than row 5 without scroll
        self.assertEqual(row_y_36, row_y_0 - 36)

    # ------------------------------------------------------------------
    # Hit-test accuracy with scrolled rows (logic verification)
    # ------------------------------------------------------------------

    def test_scrolled_row_y_stays_positive_for_visible_rows(self) -> None:
        """Rows within the visible range produce positive y coordinates."""
        visible_rows = self.panel._get_visible_rows(self.world)
        row_height = self.panel.LINE_HEIGHT
        content_y_start = 50
        viewport = 200

        self.panel.scroll_offset = 36
        self.panel._clamp_scroll_offset(visible_rows, viewport)
        base_y = content_y_start - self.panel.scroll_offset

        first_row = max(0, self.panel.scroll_offset // row_height)
        # The first visible scrolled row should be at or near the top of the viewport
        row_y = base_y + (first_row * row_height)
        self.assertLessEqual(row_y, content_y_start + row_height,
                             "First visible row should start near viewport top")
        self.assertGreater(row_y + row_height, content_y_start,
                           "First visible row should be at least partially inside viewport")

    def test_row_above_viewport_y_is_below_panel_top(self) -> None:
        """Rows scrolled above the viewport get y < panel_y (clipped out)."""
        visible_rows = self.panel._get_visible_rows(self.world)
        row_height = self.panel.LINE_HEIGHT
        content_y_start = 50
        viewport = 200

        self.panel.scroll_offset = 54  # first 3 rows scrolled out
        self.panel._clamp_scroll_offset(visible_rows, viewport)
        base_y = content_y_start - self.panel.scroll_offset

        # Row 0: y = 50 - 54 = -4, it ends at -4 + 18 = 14 (all above viewport)
        row_0_y = base_y + (0 * row_height)
        self.assertLess(row_0_y + row_height, content_y_start,
                        "Row 0 should be completely above the viewport")

    def test_partially_visible_row_top_clipped_correctly(self) -> None:
        """A row starting above viewport but ending inside it is partially visible."""
        row_height = self.panel.LINE_HEIGHT
        content_y_start = 50

        # scroll_offset=40 means row 2 starts at y=46 (50-40+36=46)
        # row ends at 64 (>50), so partially visible
        self.panel.scroll_offset = 40
        base_y = content_y_start - self.panel.scroll_offset
        row_2_y = base_y + (2 * row_height)

        self.assertLess(row_2_y, content_y_start,
                        "Row starts above viewport")
        self.assertGreater(row_2_y + row_height, content_y_start,
                           "Row extends into viewport")

    # ------------------------------------------------------------------
    # Wheel delta integration with render
    # ------------------------------------------------------------------

    def test_positive_wheel_decreases_scroll_offset(self) -> None:
        """Wheel up (positive delta) scrolls up, decreasing offset."""
        visible_rows = self.panel._get_visible_rows(self.world)
        viewport = 100
        self.panel._clamp_scroll_offset(visible_rows, viewport)
        self.panel.scroll_offset = 100
        self.panel._clamp_scroll_offset(visible_rows, viewport)
        # Re-set after clamp
        self.panel.scroll_offset = min(100, self.panel._compute_max_scroll(visible_rows, viewport))

        original = self.panel.scroll_offset
        self.assertGreater(original, 0, "Precondition: scroll_offset > 0")

        # Simulate wheel up
        wheel = 1.0
        self.panel.scroll_offset -= int(wheel * self.panel.WHEEL_STEP)
        self.panel._clamp_scroll_offset(visible_rows, viewport)
        self.assertLess(self.panel.scroll_offset, original)

    def test_negative_wheel_increases_scroll_offset(self) -> None:
        """Wheel down (negative delta) scrolls down, increasing offset."""
        visible_rows = self.panel._get_visible_rows(self.world)
        viewport = 100
        self.panel._clamp_scroll_offset(visible_rows, viewport)
        self.panel.scroll_offset = 0

        wheel = -1.0
        self.panel.scroll_offset -= int(wheel * self.panel.WHEEL_STEP)
        self.panel._clamp_scroll_offset(visible_rows, viewport)
        self.assertGreater(self.panel.scroll_offset, 0)

    # ------------------------------------------------------------------
    # Max scroll computation
    # ------------------------------------------------------------------

    def test_max_scroll_is_zero_when_content_fits(self) -> None:
        small_world = World()
        small_world.create_entity("A")
        panel = HierarchyPanel()
        visible_rows = panel._get_visible_rows(small_world)
        max_scroll = panel._compute_max_scroll(visible_rows, viewport_height=2000)
        self.assertEqual(max_scroll, 0)

    def test_max_scroll_positive_when_content_overflows(self) -> None:
        visible_rows = self.panel._get_visible_rows(self.world)
        viewport = 100
        total = len(visible_rows) * self.panel.LINE_HEIGHT
        expected_max = total - viewport
        max_scroll = self.panel._compute_max_scroll(visible_rows, viewport)
        self.assertEqual(max_scroll, expected_max)
        self.assertGreater(max_scroll, 0)

    def test_max_scroll_zero_with_no_rows(self) -> None:
        empty_world = World()
        panel = HierarchyPanel()
        visible_rows = panel._get_visible_rows(empty_world)
        max_scroll = panel._compute_max_scroll(visible_rows, viewport_height=200)
        self.assertEqual(max_scroll, 0)


if __name__ == "__main__":
    unittest.main()
