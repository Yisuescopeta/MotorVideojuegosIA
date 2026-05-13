import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from engine.editor import editor_layout as layout_module
from engine.editor.editor_layout import EditorLayout
from engine.editor.ui.widget_state import WidgetResult


class EditorLayoutFase9Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(EditorLayout, "_resize_render_textures", return_value=None))
        self.stack.enter_context(patch.object(EditorLayout, "_draw_version_and_update_info", return_value=None))
        self.stack.enter_context(patch.object(layout_module.rl, "measure_text", side_effect=lambda text, size: len(str(text)) * 6))
        self.stack.enter_context(patch.object(layout_module, "safe_reset_clip_state", Mock()))
        self.stack.enter_context(patch.object(layout_module, "draw_editor_panel_frame", Mock()))
        self.stack.enter_context(patch.object(layout_module, "draw_rounded_rect", Mock()))
        self.stack.enter_context(patch.object(layout_module, "draw_border", Mock()))
        self.stack.enter_context(patch.object(layout_module, "editor_button", Mock(return_value=WidgetResult())))
        self.stack.enter_context(patch.object(layout_module, "editor_icon_button", Mock(return_value=WidgetResult())))
        self.stack.enter_context(patch.object(layout_module, "editor_toggle_button", Mock(return_value=WidgetResult(value=False))))
        self.stack.enter_context(patch.object(layout_module.TOAST_MANAGER, "render", Mock()))
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
        self.stack.enter_context(patch.object(layout_module.rl, "is_mouse_button_released", Mock(return_value=False)))
        self.stack.enter_context(patch.object(layout_module.rl, "is_mouse_button_down", Mock(return_value=False)))
        self.stack.enter_context(patch.object(layout_module.rl, "get_mouse_wheel_move", Mock(return_value=0)))
        self.stack.enter_context(patch.object(layout_module.rl, "get_fps", Mock(return_value=60)))
        self.stack.enter_context(
            patch.object(layout_module.rl, "get_mouse_position", Mock(return_value=layout_module.rl.Vector2(0, 0)))
        )
        self.layout = EditorLayout(1024, 768)
        self.layout.project_panel = None
        self.layout.flow_panel = None
        self.layout.console_panel = None
        self.layout.terminal_panel = None
        self.layout.agent_panel = None

    def test_default_grid_config_matches_current_behavior(self) -> None:
        self.assertTrue(self.layout.grid_enabled)
        self.assertEqual(self.layout.grid_step_size, 50)
        self.assertEqual(self.layout.grid_opacity, 10)
        self.assertTrue(self.layout.grid_show_center_lines)

    def test_set_grid_config_clamps_step_and_opacity(self) -> None:
        self.layout.set_grid_config(enabled=False, step_size=1, opacity=-20, show_center_lines=False)
        self.assertFalse(self.layout.grid_enabled)
        self.assertEqual(self.layout.grid_step_size, 5)
        self.assertEqual(self.layout.grid_opacity, 0)
        self.assertFalse(self.layout.grid_show_center_lines)

        self.layout.set_grid_config(step_size=999, opacity=999)
        self.assertEqual(self.layout.grid_step_size, 500)
        self.assertEqual(self.layout.grid_opacity, 255)

    def test_reset_camera_sets_origin_zoom_and_syncs_offset(self) -> None:
        self.layout.editor_camera.zoom = 2.5
        self.layout.editor_camera.target = layout_module.rl.Vector2(12, -9)
        self.layout.editor_camera.offset = layout_module.rl.Vector2(1, 1)

        self.layout.reset_camera()

        view_rect = self.layout.get_center_view_rect()
        self.assertEqual(self.layout.editor_camera.zoom, 1.0)
        self.assertEqual((self.layout.editor_camera.target.x, self.layout.editor_camera.target.y), (0, 0))
        self.assertEqual((self.layout.editor_camera.offset.x, self.layout.editor_camera.offset.y), (view_rect.width / 2, view_rect.height / 2))

    def test_home_shortcut_resets_scene_camera_but_not_terminal(self) -> None:
        self.layout.active_tab = "SCENE"
        self.layout.active_bottom_tab = "PROJECT"
        self.layout.editor_camera.zoom = 3.0
        self.layout.editor_camera.target = layout_module.rl.Vector2(20, 30)

        with patch.object(layout_module.rl, "is_key_pressed", side_effect=lambda key: key == layout_module.rl.KEY_HOME):
            self.layout.update_input()
        self.assertEqual(self.layout.editor_camera.zoom, 1.0)
        self.assertEqual((self.layout.editor_camera.target.x, self.layout.editor_camera.target.y), (0, 0))

        self.layout.active_bottom_tab = "TERMINAL"
        self.layout.editor_camera.zoom = 2.0
        self.layout.editor_camera.target = layout_module.rl.Vector2(7, 8)
        with patch.object(layout_module.rl, "is_key_pressed", side_effect=lambda key: key == layout_module.rl.KEY_HOME):
            self.layout.update_input()
        self.assertEqual(self.layout.editor_camera.zoom, 2.0)
        self.assertEqual((self.layout.editor_camera.target.x, self.layout.editor_camera.target.y), (7, 8))

    def test_overlay_context_stores_selected_entity(self) -> None:
        self.layout.set_viewport_overlay_context(selected_entity="player")
        self.assertEqual(self.layout.viewport_overlay_context["selected_entity"], "player")

    def test_draw_layout_smoke_draws_viewport_chrome_and_overlay(self) -> None:
        self.layout.active_tab = "SCENE"
        self.layout.set_viewport_overlay_context(selected_entity="player")
        with patch.object(self.layout, "get_scene_mouse_pos", Mock(return_value=layout_module.rl.Vector2(1.0, 2.0))):
            self.layout.draw_layout(False)

        self.assertTrue(layout_module.rl.draw_rectangle_lines_ex.called)
        drawn_text = [call.args[0] for call in layout_module.rl.draw_text.call_args_list]
        self.assertIn("FPS 60", drawn_text)
        self.assertIn("Mouse 1.0, 2.0", drawn_text)
        self.assertIn("Selected player", drawn_text)

    def test_scene_mouse_vector_uses_viewport_local_position(self) -> None:
        view_rect = self.layout.get_center_view_rect()
        mouse = layout_module.rl.Vector2(view_rect.x + 25, view_rect.y + 40)
        captured: list[tuple[float, float]] = []

        def convert(local, _camera):
            captured.append((local.x, local.y))
            return layout_module.rl.Vector2(local.x + 1, local.y + 2)

        with patch.object(layout_module.rl, "get_mouse_position", Mock(return_value=mouse)):
            with patch.object(layout_module.rl, "get_screen_to_world_2d", side_effect=convert):
                result = self.layout.get_scene_mouse_pos()

        self.assertEqual(captured, [(25, 40)])
        self.assertEqual((result.x, result.y), (26, 42))


if __name__ == "__main__":
    unittest.main()
