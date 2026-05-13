import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from engine.editor import editor_layout as layout_module
from engine.editor.editor_layout import EditorLayout
from engine.editor.ui.widget_state import WidgetResult


def _rect_tuple(rect) -> tuple[float, float, float, float]:
    return (float(rect.x), float(rect.y), float(rect.width), float(rect.height))


class EditorLayoutFase4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(EditorLayout, "_resize_render_textures", return_value=None))
        self.stack.enter_context(patch.object(EditorLayout, "_draw_version_and_update_info", return_value=None))
        self.stack.enter_context(patch.object(layout_module.rl, "measure_text", side_effect=lambda text, size: len(str(text)) * 6))
        for name in (
            "clear_background",
            "draw_rectangle",
            "draw_line",
            "draw_rectangle_rec",
            "draw_rectangle_lines_ex",
            "draw_text",
            "draw_texture_pro",
        ):
            self.stack.enter_context(patch.object(layout_module.rl, name, Mock()))
        self.stack.enter_context(patch.object(layout_module.rl, "check_collision_point_rec", Mock(return_value=False)))
        self.stack.enter_context(patch.object(layout_module.rl, "is_mouse_button_pressed", Mock(return_value=False)))
        self.stack.enter_context(
            patch.object(layout_module.rl, "get_mouse_position", Mock(return_value=layout_module.rl.Vector2(0, 0)))
        )
        self.stack.enter_context(patch.object(layout_module, "safe_reset_clip_state", Mock()))
        self.stack.enter_context(patch.object(layout_module, "draw_rounded_rect", Mock()))
        self.stack.enter_context(patch.object(layout_module, "draw_border", Mock()))
        self.stack.enter_context(patch.object(layout_module, "editor_button", Mock(return_value=WidgetResult())))
        self.stack.enter_context(patch.object(layout_module, "editor_icon_button", Mock(return_value=WidgetResult())))
        self.stack.enter_context(patch.object(layout_module, "editor_toggle_button", Mock(return_value=WidgetResult(value=False))))
        self.layout = EditorLayout(1024, 768)
        self.layout.project_panel = None
        self.layout.flow_panel = None
        self.layout.console_panel = None
        self.layout.terminal_panel = None
        self.layout.agent_panel = None

    def test_draw_layout_calls_panel_frames_without_changing_public_rects(self) -> None:
        before = {
            "hierarchy": _rect_tuple(self.layout.hierarchy_rect),
            "inspector": _rect_tuple(self.layout.inspector_rect),
            "center": _rect_tuple(self.layout.center_rect),
            "bottom": _rect_tuple(self.layout.bottom_rect),
        }

        with patch.object(layout_module, "draw_editor_panel_frame", Mock()) as draw_frame:
            self.layout.draw_layout(False)

        titles = [call.args[1] for call in draw_frame.call_args_list]
        self.assertIn("Hierarchy", titles)
        self.assertIn("Inspector", titles)
        self.assertIn("Viewport", titles)
        self.assertIn(self.layout.active_bottom_tab.title(), titles)
        self.assertEqual(before["hierarchy"], _rect_tuple(self.layout.hierarchy_rect))
        self.assertEqual(before["inspector"], _rect_tuple(self.layout.inspector_rect))
        self.assertEqual(before["center"], _rect_tuple(self.layout.center_rect))
        self.assertEqual(before["bottom"], _rect_tuple(self.layout.bottom_rect))

    def test_draw_splitters_uses_rounded_visual_and_state_colors(self) -> None:
        colors: list[tuple[int, int, int, int]] = []

        def capture(_rect, color, _radius=4):
            colors.append(color)

        with patch.object(layout_module, "draw_rounded_rect", side_effect=capture) as rounded:
            self.layout._draw_splitters()
        self.assertEqual(rounded.call_count, 3)
        self.assertEqual(colors[0], (self.layout.SPLITTER_COLOR.r, self.layout.SPLITTER_COLOR.g, self.layout.SPLITTER_COLOR.b, self.layout.SPLITTER_COLOR.a))

        colors.clear()
        self.layout.dragging_splitter = "right"
        with patch.object(layout_module, "draw_rounded_rect", side_effect=capture):
            self.layout._draw_splitters()
        self.assertEqual(colors[1], (self.layout.UNITY_BLUE_HOVER.r, self.layout.UNITY_BLUE_HOVER.g, self.layout.UNITY_BLUE_HOVER.b, self.layout.UNITY_BLUE_HOVER.a))

    def test_draw_splitters_hover_uses_blue_hover_without_hit_rect_change(self) -> None:
        before = _rect_tuple(self.layout.splitter_left_rect)
        hover = Mock(side_effect=[True, False, False])
        colors: list[tuple[int, int, int, int]] = []

        with patch.object(layout_module.rl, "check_collision_point_rec", hover):
            with patch.object(layout_module, "draw_rounded_rect", side_effect=lambda _rect, color, _radius=4: colors.append(color)):
                self.layout._draw_splitters()

        self.assertEqual(before, _rect_tuple(self.layout.splitter_left_rect))
        self.assertEqual(colors[0], (self.layout.SPLITTER_HOVER_COLOR.r, self.layout.SPLITTER_HOVER_COLOR.g, self.layout.SPLITTER_HOVER_COLOR.b, self.layout.SPLITTER_HOVER_COLOR.a))


if __name__ == "__main__":
    unittest.main()
