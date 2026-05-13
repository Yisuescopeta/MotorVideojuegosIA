import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from engine.editor.ui import panels, scroll
from engine.editor.ui.widget_state import WidgetResult


class _FakeRL:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def Rectangle(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        return (x, y, w, h)

    def Color(self, r: int, g: int, b: int, a: int) -> tuple[int, int, int, int]:
        return (r, g, b, a)

    def draw_rectangle_rec(self, *args) -> None:
        self.calls.append(("draw_rectangle_rec", args))

    def draw_rectangle(self, *args) -> None:
        self.calls.append(("draw_rectangle", args))

    def begin_scissor_mode(self, *args) -> None:
        self.calls.append(("begin_scissor_mode", args))

    def end_scissor_mode(self) -> None:
        self.calls.append(("end_scissor_mode", ()))


class EditorPanelsScrollTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.fake_rl = _FakeRL()
        self.stack.enter_context(patch.object(panels, "_rl", return_value=self.fake_rl))
        self.mock_panel_bg = Mock()
        self.stack.enter_context(patch.object(panels, "draw_panel_background", self.mock_panel_bg))
        self.mock_border = Mock()
        self.stack.enter_context(patch.object(panels, "draw_border", self.mock_border))
        self.stack.enter_context(patch.object(panels, "draw_rounded_rect", Mock()))
        self.draw_text = self.stack.enter_context(patch.object(panels, "draw_text_clipped", Mock()))
        self.stack.enter_context(patch.object(panels.ui_input, "is_hovered", Mock(return_value=False)))
        self.stack.enter_context(patch.object(panels.ui_input, "is_pressed", Mock(return_value=False)))
        self.is_clicked = self.stack.enter_context(patch.object(panels.ui_input, "is_clicked", Mock(return_value=False)))
        self.stack.enter_context(patch.object(panels.ui_input, "is_right_clicked", Mock(return_value=False)))

    def test_draw_panel_header_uppercase_menu_and_actions(self) -> None:
        self.is_clicked.side_effect = [False, True, False, False, False]

        result = panels.draw_panel_header((0, 0, 200, 24), "Hierarchy", actions=["+"], subtitle="Scene")

        self.assertIsInstance(result, WidgetResult)
        self.assertTrue(result.clicked)
        self.assertTrue(result.changed)
        drawn_text = [call.args[0] for call in self.draw_text.call_args_list]
        self.assertIn("HIERARCHY", drawn_text)
        self.assertIn("Scene", drawn_text)
        self.assertIn("...", drawn_text)
        self.assertIn("+", drawn_text)

    def test_draw_editor_panel_draws_frame_and_header(self) -> None:
        result = panels.draw_editor_panel((0, 0, 180, 120), "Inspector", active=True)

        self.assertIsInstance(result, WidgetResult)
        self.mock_panel_bg.assert_called_once()
        self.mock_border.assert_called()

    def test_begin_end_panel_content_scissors_safely(self) -> None:
        panels.begin_panel_content((1.2, 2.8, -5.0, 10.0))
        panels.end_panel_content()

        self.assertIn(("begin_scissor_mode", (1, 2, 0, 10)), self.fake_rl.calls)
        self.assertIn(("end_scissor_mode", ()), self.fake_rl.calls)

    def test_nested_panel_content_restores_outer_scissor(self) -> None:
        panels.begin_panel_content((1.0, 2.0, 30.0, 40.0))
        panels.begin_panel_content((5.0, 6.0, 7.0, 8.0))
        panels.end_panel_content()
        panels.end_panel_content()

        self.assertEqual(
            self.fake_rl.calls,
            [
                ("begin_scissor_mode", (1, 2, 30, 40)),
                ("begin_scissor_mode", (5, 6, 7, 8)),
                ("end_scissor_mode", ()),
                ("begin_scissor_mode", (1, 2, 30, 40)),
                ("end_scissor_mode", ()),
            ],
        )

    def test_end_panel_content_without_begin_is_noop(self) -> None:
        panels.end_panel_content()

        self.assertNotIn(("end_scissor_mode", ()), self.fake_rl.calls)

    def test_scroll_clamps_wheel_and_draws_thumb(self) -> None:
        with ExitStack() as stack:
            stack.enter_context(patch.object(scroll, "draw_rounded_rect", Mock()))
            stack.enter_context(patch.object(scroll.ui_input, "is_hovered", Mock(side_effect=[True, False])))
            stack.enter_context(patch.object(scroll.ui_input, "is_pressed", Mock(return_value=False)))
            stack.enter_context(patch.object(scroll.ui_input, "wheel_delta", Mock(return_value=-1.0)))

            result = scroll.editor_scroll_area((0, 0, 100, 100), 250, 200)

        self.assertEqual(result.scroll_offset_y, 150.0)
        self.assertEqual(result.max_scroll_y, 150.0)
        self.assertTrue(result.changed)
        self.assertIsNotNone(result.track_rect)
        self.assertIsNotNone(result.thumb_rect)

    def test_scroll_track_press_updates_offset(self) -> None:
        with ExitStack() as stack:
            stack.enter_context(patch.object(scroll, "draw_rounded_rect", Mock()))
            stack.enter_context(patch.object(scroll.ui_input, "is_hovered", Mock(return_value=True)))
            stack.enter_context(patch.object(scroll.ui_input, "is_pressed", Mock(return_value=True)))
            stack.enter_context(patch.object(scroll.ui_input, "wheel_delta", Mock(return_value=0.0)))
            stack.enter_context(patch.object(scroll.ui_input, "mouse_position", Mock(return_value=(98.0, 90.0))))

            result = scroll.editor_scroll_area((0, 0, 100, 100), 300, 0)

        self.assertGreater(result.scroll_offset_y, 0.0)
        self.assertTrue(result.changed)


if __name__ == "__main__":
    unittest.main()
