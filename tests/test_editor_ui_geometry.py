import unittest

from engine.editor.ui.geometry import (
    clamp_rect,
    inset_rect,
    rect_contains,
    split_bottom,
    split_left,
    split_right,
    split_top,
)


class EditorUIGeometryTests(unittest.TestCase):
    def test_inset_rect_clamps_size(self) -> None:
        self.assertEqual(inset_rect((0, 0, 10, 8), 2), (2, 2, 6, 4))
        self.assertEqual(inset_rect((0, 0, 4, 4), 9), (9, 9, 0.0, 0.0))

    def test_split_helpers_return_primary_and_remainder(self) -> None:
        rect = (0, 0, 100, 50)
        self.assertEqual(split_top(rect, 10), ((0, 0, 100, 10.0), (0, 10.0, 100, 40.0)))
        self.assertEqual(split_bottom(rect, 10), ((0, 0, 100, 40.0), (0, 40.0, 100, 10.0)))
        self.assertEqual(split_left(rect, 25), ((0, 0, 25.0, 50), (25.0, 0, 75.0, 50)))
        self.assertEqual(split_right(rect, 25), ((0, 0, 75.0, 50), (75.0, 0, 25.0, 50)))

    def test_rect_contains_edges(self) -> None:
        self.assertTrue(rect_contains((10, 10, 20, 20), 10, 30))
        self.assertFalse(rect_contains((10, 10, 20, 20), 31, 30))

    def test_clamp_rect_keeps_rect_inside_bounds(self) -> None:
        self.assertEqual(clamp_rect((90, 90, 20, 20), (0, 0, 100, 100)), (80, 80, 20, 20))
        self.assertEqual(clamp_rect((-10, -10, 150, 150), (0, 0, 100, 100)), (0, 0, 100, 100))

    def test_split_helpers_clamp_negative_and_oversized_values(self) -> None:
        rect = (0, 0, 10, 8)
        self.assertEqual(split_top(rect, -5), ((0, 0, 10, 0.0), (0, 0.0, 10, 8.0)))
        self.assertEqual(split_left(rect, 99), ((0, 0, 10, 8), (10, 0, 0, 8)))

    def test_rect_contains_zero_size_and_negative_size(self) -> None:
        self.assertTrue(rect_contains((5, 5, 0, 0), 5, 5))
        self.assertFalse(rect_contains((5, 5, -1, 10), 5, 5))

    def test_clamp_rect_handles_negative_rect_size(self) -> None:
        self.assertEqual(clamp_rect((4, 4, -1, -2), (0, 0, 10, 10)), (4, 4, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
