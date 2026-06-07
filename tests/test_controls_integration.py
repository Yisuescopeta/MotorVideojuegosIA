import unittest
from unittest.mock import Mock

from engine.editor.console_panel import ConsolePanel
from engine.editor.editor_control_adapter import ConsolePanelEditorControlAdapter
from engine.editor.editor_control_flags import (
    EditorControlFeatureFlagManager,
    EditorControlFeatureFlags,
    default_editor_control_feature_flags,
    editor_control_feature_flag_names,
    editor_control_feature_flags_from_preferences,
)
from engine.editor.ui_core.controls.console_control import ConsoleControlModel


class TestControlsIntegration(unittest.TestCase):
    def test_console_panel_uses_text_input(self) -> None:
        """C1: ConsolePanel uses TextInput for search and command."""
        panel = ConsolePanel()
        self.assertIsNotNone(panel.search_input)
        self.assertIsNotNone(panel.command_input)
        self.assertEqual(panel.search_input.placeholder, "Search...")
        self.assertEqual(panel.command_input.placeholder, "Command: help")

    def test_search_text_property_delegates_to_model(self) -> None:
        panel = ConsolePanel()
        panel.search_text = "test query"
        self.assertEqual(panel.search_input.text, "test query")
        self.assertEqual(panel.search_text, "test query")

    def test_command_text_property_delegates_to_model(self) -> None:
        panel = ConsolePanel()
        panel.command_text = "help"
        self.assertEqual(panel.command_input.text, "help")

    def test_console_retained_mode_flag_default_off(self) -> None:
        """C5: console_panel flag defaults to False."""
        flags = default_editor_control_feature_flags()
        self.assertFalse(flags.console_panel)

    def test_console_retained_mode_flag_from_env(self) -> None:
        """C5: MOTOR_EDITOR_CONTROL_CONSOLE=1 enables flag."""
        import os
        os.environ["MOTOR_EDITOR_CONTROL_CONSOLE"] = "1"
        try:
            flags = editor_control_feature_flags_from_preferences({})
            self.assertTrue(flags.console_panel)
        finally:
            del os.environ["MOTOR_EDITOR_CONTROL_CONSOLE"]

    def test_console_retained_mode_flag_from_preferences(self) -> None:
        """C5: preferences override default."""
        flags = editor_control_feature_flags_from_preferences(
            {"editor_feature_flags": {"console_panel": True}}
        )
        self.assertTrue(flags.console_panel)

    def test_adapter_sync_when_flag_on(self) -> None:
        """C5: adapter syncs data between model and panel when flag on."""
        panel = Mock()
        panel.show_info = True
        panel.show_warn = True
        panel.show_err = True
        panel.show_debug = True
        panel.search_text = ""
        panel.command_text = ""
        panel.command_output = ""
        panel.scroll_offset = 0.0
        flags = EditorControlFeatureFlags(console_panel=True)
        model = ConsoleControlModel(search_text="warn")
        adapter = ConsolePanelEditorControlAdapter(panel=panel, flags=flags, control_model=model)

        def _render(_x, _y, _w, _h):
            panel.search_text = "after sync"

        panel.render.side_effect = _render

        adapter.render(0, 0, 100, 100)

        self.assertEqual(adapter.control_model.search_text, "after sync")
        panel.render.assert_called_once_with(0, 0, 100, 100)

    def test_adapter_no_sync_when_flag_off(self) -> None:
        """C5: adapter just delegates when flag off."""
        panel = Mock()
        flags = EditorControlFeatureFlags(console_panel=False)
        adapter = ConsolePanelEditorControlAdapter(panel=panel, flags=flags)

        adapter.render(0, 0, 100, 100)

        panel.render.assert_called_once_with(0, 0, 100, 100)

    def test_feature_flags_extended_fields(self) -> None:
        """C2/C4: feature flags include asset_browser and popup_controls."""
        flag_names = editor_control_feature_flag_names()
        self.assertIn("console_panel", flag_names)
        self.assertIn("asset_browser", flag_names)
        self.assertIn("popup_controls", flag_names)

    def test_feature_flag_manager_update(self) -> None:
        """Manager.update() applies new values."""
        manager = EditorControlFeatureFlagManager()
        result = manager.update({"console_panel": True})
        self.assertTrue(result.console_panel)

    def test_context_menu_model_exists(self) -> None:
        """C3: ContextMenuModel is importable."""
        from engine.editor.ui_core.controls.context_menu import ContextMenuItem, ContextMenuModel
        menu = ContextMenuModel(items=[
            ContextMenuItem(id="action1", label="Action 1"),
        ])
        self.assertEqual(len(menu.items), 1)
        self.assertEqual(menu.items[0].id, "action1")

    def test_popup_model_exists(self) -> None:
        """C4: PopupModel has confirm_popup helper."""
        from engine.editor.ui_core.controls.popup import confirm_popup
        popup = confirm_popup("Delete?", "Are you sure?")
        self.assertTrue(popup.visible)
        self.assertEqual(popup.title, "Delete?")

    def test_file_picker_model_exists(self) -> None:
        """C6: FilePickerModel is importable."""
        from engine.editor.ui_core.controls.file_picker import FilePickerModel
        model = FilePickerModel(title="Test")
        self.assertEqual(model.title, "Test")
        self.assertEqual(model.mode, "open")


if __name__ == "__main__":
    unittest.main()
