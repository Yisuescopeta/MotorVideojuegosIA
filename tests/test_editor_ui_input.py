import unittest

from engine.editor.ui.input import (
    is_clicked_at,
    is_hovered_at,
    is_pressed_at,
    is_right_clicked_at,
)


class EditorUIInputTests(unittest.TestCase):
    def test_is_hovered_at_includes_edges(self) -> None:
        rect = (10, 20, 30, 40)
        self.assertTrue(is_hovered_at(rect, 10, 20))
        self.assertTrue(is_hovered_at(rect, 40, 60))
        self.assertFalse(is_hovered_at(rect, 41, 60))
        self.assertFalse(is_hovered_at(rect, 40, 61))

    def test_is_pressed_at_requires_hover_and_down(self) -> None:
        rect = (0, 0, 10, 10)
        self.assertTrue(is_pressed_at(rect, 5, 5, True))
        self.assertFalse(is_pressed_at(rect, 5, 5, False))
        self.assertFalse(is_pressed_at(rect, 11, 5, True))

    def test_is_clicked_at_requires_hover_and_click_event(self) -> None:
        rect = (0, 0, 10, 10)
        self.assertTrue(is_clicked_at(rect, 5, 5, True))
        self.assertFalse(is_clicked_at(rect, 5, 5, False))
        self.assertFalse(is_clicked_at(rect, -1, 5, True))

    def test_is_right_clicked_at_requires_hover_and_click_event(self) -> None:
        rect = (0, 0, 10, 10)
        self.assertTrue(is_right_clicked_at(rect, 10, 10, True))
        self.assertFalse(is_right_clicked_at(rect, 10, 10, False))
        self.assertFalse(is_right_clicked_at(rect, 10, 11, True))


if __name__ == "__main__":
    unittest.main()
