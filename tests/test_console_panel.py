import unittest
from unittest.mock import patch

from engine.editor.console_panel import ConsolePanel, GLOBAL_LOGS, log_err, log_info


class ConsolePanelRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        GLOBAL_LOGS.clear()

    def tearDown(self) -> None:
        GLOBAL_LOGS.clear()

    def test_console_panel_renders_placeholder_when_empty(self) -> None:
        panel = ConsolePanel()
        drawn_texts: list[str] = []

        with patch("pyray.gui_button", return_value=False), patch(
            "engine.editor.console_panel.gui_toggle_bool",
            side_effect=lambda _rect, _label, value: value,
        ), patch("pyray.draw_rectangle"), patch("pyray.draw_rectangle_rec"), patch(
            "pyray.draw_rectangle_lines_ex"
        ), patch("pyray.draw_line"), patch(
            "pyray.draw_text",
            side_effect=lambda text, *_args, **_kwargs: drawn_texts.append(str(text)),
        ), patch("pyray.begin_scissor_mode"), patch("pyray.end_scissor_mode"), patch(
            "pyray.get_mouse_position"
        ), patch("pyray.check_collision_point_rec", return_value=False), patch(
            "pyray.get_mouse_wheel_move",
            return_value=0.0,
        ):
            panel.clear()
            panel.render(10, 20, 600, 140)

        self.assertIn("No console messages yet", drawn_texts)
        self.assertGreater(panel.body_rect.height, 0)
        self.assertGreater(panel.toolbar_rect.height, 0)

    def test_console_panel_keeps_layout_rects_inside_panel_bounds(self) -> None:
        panel = ConsolePanel()
        log_info("hello")
        log_err("boom")

        with patch("pyray.gui_button", return_value=False), patch(
            "engine.editor.console_panel.gui_toggle_bool",
            side_effect=lambda _rect, _label, value: value,
        ), patch("pyray.draw_rectangle"), patch("pyray.draw_rectangle_rec"), patch(
            "pyray.draw_rectangle_lines_ex"
        ), patch("pyray.draw_line"), patch("pyray.draw_text"), patch(
            "pyray.begin_scissor_mode"
        ), patch("pyray.end_scissor_mode"), patch("pyray.get_mouse_position"), patch(
            "pyray.check_collision_point_rec",
            return_value=False,
        ), patch("pyray.get_mouse_wheel_move", return_value=0.0):
            panel.render(12, 34, 720, 180)

        px = panel.panel_rect.x
        py = panel.panel_rect.y
        pw = panel.panel_rect.width
        ph = panel.panel_rect.height

        def _inside(rect) -> bool:
            return (
                rect.x >= px
                and rect.y >= py
                and rect.x + rect.width <= px + pw
                and rect.y + rect.height <= py + ph
            )

        self.assertTrue(_inside(panel.toolbar_rect))
        self.assertTrue(_inside(panel.body_rect))

    def test_console_panel_propagates_body_render_errors_without_scissor_dependency(self) -> None:
        panel = ConsolePanel()
        log_info("hello")

        with patch("pyray.gui_button", return_value=False), patch(
            "engine.editor.console_panel.gui_toggle_bool",
            side_effect=lambda _rect, _label, value: value,
        ), patch("pyray.draw_rectangle"), patch("pyray.draw_rectangle_rec"), patch(
            "pyray.draw_rectangle_lines_ex"
        ), patch("pyray.draw_line"), patch(
            "pyray.draw_text",
            side_effect=[None, RuntimeError("draw failure")],
        ), patch("pyray.begin_scissor_mode") as begin_scissor, patch(
            "pyray.end_scissor_mode"
        ) as end_scissor, patch("pyray.get_mouse_position"), patch(
            "pyray.check_collision_point_rec",
            return_value=False,
        ), patch("pyray.get_mouse_wheel_move", return_value=0.0):
            with self.assertRaises(RuntimeError):
                panel.render(12, 34, 720, 180)

        begin_scissor.assert_not_called()
        end_scissor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
