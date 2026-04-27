import unittest
from unittest.mock import patch

import pyray as rl
from engine.editor.console_panel import ConsolePanel
from engine.editor.render_safety import (
    editor_scissor,
    gui_toggle_bool,
    logical_rect_to_scissor_rect,
    safe_reset_clip_state,
)
from engine.editor.scene_flow_panel import SceneFlowPanel


class RenderSafetyTests(unittest.TestCase):
    def test_logical_rect_to_scissor_rect_scales_for_hidpi_framebuffer(self) -> None:
        rect = rl.Rectangle(100.0, 50.0, 300.0, 120.0)

        with patch("pyray.get_screen_width", return_value=1000), patch(
            "pyray.get_screen_height",
            return_value=500,
        ), patch("pyray.get_render_width", return_value=1500), patch(
            "pyray.get_render_height",
            return_value=750,
        ):
            result = logical_rect_to_scissor_rect(rect)

        self.assertEqual(result, (150, 75, 450, 180))

    def test_logical_rect_to_scissor_rect_clamps_to_render_bounds(self) -> None:
        rect = rl.Rectangle(-10.0, 480.0, 200.0, 80.0)

        with patch("pyray.get_screen_width", return_value=1000), patch(
            "pyray.get_screen_height",
            return_value=500,
        ), patch("pyray.get_render_width", return_value=2000), patch(
            "pyray.get_render_height",
            return_value=1000,
        ):
            result = logical_rect_to_scissor_rect(rect)

        self.assertEqual(result, (0, 960, 380, 40))

    def test_editor_scissor_balances_begin_and_end(self) -> None:
        rect = rl.Rectangle(10.0, 20.0, 30.0, 40.0)

        with patch("pyray.get_screen_width", return_value=100), patch(
            "pyray.get_screen_height",
            return_value=100,
        ), patch("pyray.get_render_width", return_value=100), patch(
            "pyray.get_render_height",
            return_value=100,
        ), patch("pyray.begin_scissor_mode") as begin_scissor, patch(
            "pyray.end_scissor_mode"
        ) as end_scissor:
            with editor_scissor(rect) as active:
                self.assertTrue(active)

        begin_scissor.assert_called_once_with(10, 20, 30, 40)
        end_scissor.assert_called_once()

    def test_safe_reset_clip_state_swallow_end_errors(self) -> None:
        with patch("pyray.is_window_ready", return_value=True), patch(
            "pyray.end_scissor_mode",
            side_effect=RuntimeError("clip"),
        ):
            safe_reset_clip_state()

    def test_gui_toggle_bool_uses_mutable_cffi_bool_state(self) -> None:
        captured = {}

        def _toggle(_rect, _label, state):
            captured["state"] = state
            state[0] = not bool(state[0])

        with patch("pyray.gui_toggle", side_effect=_toggle):
            result = gui_toggle_bool(rl.Rectangle(0.0, 0.0, 10.0, 10.0), "Flag", True)

        self.assertFalse(result)
        self.assertEqual(bool(captured["state"][0]), False)

    def test_console_panel_renders_without_scissor_side_effects(self) -> None:
        panel = ConsolePanel()

        with patch("pyray.gui_button", return_value=False), patch(
            "engine.editor.console_panel.gui_toggle_bool",
            side_effect=lambda _rect, _label, value: value,
        ), patch("pyray.draw_rectangle"), patch("pyray.draw_rectangle_rec"), patch(
            "pyray.draw_rectangle_lines_ex"
        ), patch("pyray.draw_line"), patch("pyray.draw_text"), patch(
            "pyray.begin_scissor_mode"
        ) as begin_scissor, patch("pyray.end_scissor_mode") as end_scissor, patch(
            "pyray.get_mouse_position"
        ), patch("pyray.check_collision_point_rec", return_value=False), patch(
            "pyray.get_mouse_wheel_move",
            return_value=0.0,
        ):
            panel.render(100, 200, 300, 140)

        self.assertEqual(begin_scissor.call_count, 0)
        self.assertEqual(end_scissor.call_count, 0)
        self.assertGreater(panel.body_rect.height, 0)

    def test_scene_flow_panel_renders_without_scissor_side_effects(self) -> None:
        panel = SceneFlowPanel()

        with patch("engine.editor.scene_flow_panel.gui_toggle_bool", side_effect=lambda rect, _label, value: value), patch(
            "pyray.gui_button",
            return_value=False,
        ), patch("pyray.draw_rectangle"), patch("pyray.draw_rectangle_rec"), patch(
            "pyray.draw_rectangle_lines_ex"
        ), patch("pyray.draw_line"), patch("pyray.draw_text"), patch(
            "pyray.begin_scissor_mode"
        ) as begin_scissor, patch("pyray.end_scissor_mode") as end_scissor, patch(
            "pyray.check_collision_point_rec",
            return_value=False,
        ), patch("pyray.get_mouse_position"), patch("pyray.get_mouse_wheel_move", return_value=0.0):
            panel.render(100, 200, 600, 180)

        self.assertEqual(begin_scissor.call_count, 0)
        self.assertEqual(end_scissor.call_count, 0)
        self.assertGreater(panel._sidebar_rect.height, 0)
        self.assertGreater(panel._canvas_rect.height, 0)


if __name__ == "__main__":
    unittest.main()
