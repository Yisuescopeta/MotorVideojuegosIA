import unittest
from contextlib import ExitStack
from unittest.mock import patch

from engine.editor import editor_layout as layout_module
from engine.editor.editor_layout import EditorLayout
from engine.editor.editor_tools import EditorTool
from engine.editor.ui.widget_state import WidgetResult


class EditorLayoutFase3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._stack = ExitStack()
        self.addCleanup(self._stack.close)
        self._stack.enter_context(patch.object(EditorLayout, "_resize_render_textures", return_value=None))
        self._stack.enter_context(patch.object(EditorLayout, "_draw_version_and_update_info", return_value=None))
        self._stack.enter_context(patch.object(layout_module.rl, "measure_text", side_effect=lambda text, size: len(str(text)) * 6))
        self._stack.enter_context(patch.object(layout_module.rl, "draw_rectangle", return_value=None))
        self._stack.enter_context(patch.object(layout_module.rl, "draw_line", return_value=None))
        self._stack.enter_context(patch.object(layout_module.rl, "draw_rectangle_rec", return_value=None))
        self._stack.enter_context(patch.object(layout_module.rl, "draw_rectangle_lines_ex", return_value=None))
        self._stack.enter_context(patch.object(layout_module.rl, "draw_text", return_value=None))
        self._stack.enter_context(patch.object(layout_module.rl, "check_collision_point_rec", return_value=False))
        self._stack.enter_context(patch.object(layout_module.rl, "is_mouse_button_pressed", return_value=False))
        self._stack.enter_context(
            patch.object(layout_module.rl, "get_mouse_position", return_value=layout_module.rl.Vector2(0, 0))
        )
        self.layout = EditorLayout(1024, 768)

    def _patch_widgets(self, *, buttons: set[str] | None = None, icons: set[str] | None = None, toggles: set[str] | None = None):
        buttons = buttons or set()
        icons = icons or set()
        toggles = toggles or set()

        def button(_rect, text, **_kwargs):
            return WidgetResult(clicked=str(text) in buttons, value=text)

        def icon_button(_rect, icon_name, **_kwargs):
            return WidgetResult(clicked=str(icon_name) in icons, value=icon_name)

        def toggle_button(_rect, text, value, **_kwargs):
            clicked = str(text) in toggles
            return WidgetResult(clicked=clicked, changed=clicked, value=not value if clicked else value)

        stack = ExitStack()
        stack.enter_context(patch.object(layout_module, "editor_button", side_effect=button))
        stack.enter_context(patch.object(layout_module, "editor_icon_button", side_effect=icon_button))
        stack.enter_context(patch.object(layout_module, "editor_toggle_button", side_effect=toggle_button))
        return stack

    def test_menu_click_opens_and_closes_active_menu(self) -> None:
        with self._patch_widgets(buttons={"File"}):
            self.layout._draw_menu_bar()
        self.assertEqual(self.layout._active_menu, "File")
        self.assertIn("File", self.layout._menu_item_rects)

        with self._patch_widgets(buttons={"File"}):
            self.layout._draw_menu_bar()
        self.assertIsNone(self.layout._active_menu)

    def test_toolbar_tool_click_changes_active_tool(self) -> None:
        with self._patch_widgets(toggles={"E"}):
            self.layout._draw_toolbar(is_playing=False)
        self.assertEqual(self.layout.active_tool, EditorTool.ROTATE)

    def test_play_button_click_sets_request_play(self) -> None:
        with self._patch_widgets(icons={layout_module.ICON_PLAY}):
            self.layout._draw_toolbar(is_playing=False)
        self.assertTrue(self.layout.request_play)

    def test_pause_button_click_sets_request_pause(self) -> None:
        with self._patch_widgets(icons={layout_module.ICON_PAUSE}):
            self.layout._draw_toolbar(is_playing=True)
        self.assertTrue(self.layout.request_pause)

    def test_step_button_click_sets_request_step(self) -> None:
        with self._patch_widgets(buttons={">|"}):
            self.layout._draw_toolbar(is_playing=True)
        self.assertTrue(self.layout.request_step)

    def test_new_and_save_buttons_set_scene_flags(self) -> None:
        with self._patch_widgets(buttons={"New"}):
            self.layout._draw_toolbar(is_playing=False)
        self.assertTrue(self.layout.show_create_scene_modal)
        self.assertEqual(self.layout.scene_create_name, "New Scene")
        self.assertTrue(self.layout.scene_create_name_focused)

        with self._patch_widgets(buttons={"Save"}):
            self.layout._draw_toolbar(is_playing=False)
        self.assertTrue(self.layout.request_save_scene)

    def test_ui_creation_buttons_set_requests(self) -> None:
        cases = [
            ("Canvas", "request_create_canvas"),
            ("Text", "request_create_ui_text"),
            ("Button", "request_create_ui_button"),
        ]
        for label, attr in cases:
            with self.subTest(label=label):
                target = EditorLayout(1024, 768)
                with self._patch_widgets(buttons={label}):
                    target._draw_toolbar(is_playing=False)
                self.assertTrue(getattr(target, attr))

    def test_execute_menu_action_undo_still_sets_request(self) -> None:
        self.layout._execute_menu_action("undo")
        self.assertTrue(self.layout.request_undo)


if __name__ == "__main__":
    unittest.main()
