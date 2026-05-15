import unittest
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from engine.app.project_workspace_controller import ProjectWorkspaceController
from engine.core.engine_state import EngineState
from engine.editor.editor_control_adapter import ConsolePanelEditorControlAdapter
from engine.editor.editor_layout import EditorLayout
from engine.editor.editor_control_flags import EditorControlFeatureFlags
from engine.editor.ui_core.controls.console_control import ConsoleControlModel
from engine.project.project_service import ProjectService


class EditorControlMigrationTests(unittest.TestCase):
    def test_feature_flags_default_false(self) -> None:
        flags = EditorControlFeatureFlags()

        self.assertFalse(flags.console_panel)

    def test_console_model_filters_counts_and_commands(self) -> None:
        model = ConsoleControlModel(show_debug=False, search_text="alpha")
        logs = [("INFO", "Alpha ready"), ("DEBUG", "Alpha trace"), ("ERR", "Boom")]

        self.assertEqual(model.count_by_level(logs), {"INFO": 1, "WARN": 0, "ERR": 1, "DEBUG": 1})
        self.assertEqual(model.filtered_logs(logs), [("INFO", "Alpha ready")])
        self.assertEqual(model.execute_command("echo hi").output, "hi")
        self.assertTrue(model.execute_command("toggle_debug").show_debug)
        self.assertTrue(model.execute_command("clear").clear_logs)
        self.assertEqual(
            model.execute_command("time", now=lambda: datetime(2026, 5, 14, 1, 2, 3)).output,
            "2026-05-14T01:02:03",
        )

    def test_console_adapter_flag_false_delegates_legacy_panel(self) -> None:
        panel = Mock()
        adapter = ConsolePanelEditorControlAdapter(panel=panel, flags=EditorControlFeatureFlags(console_panel=False))

        adapter.render(1, 2, 3, 4)

        panel.render.assert_called_once_with(1, 2, 3, 4)

    def test_console_adapter_flag_true_syncs_model_and_panel(self) -> None:
        panel = Mock()
        panel.show_info = True
        panel.show_warn = True
        panel.show_err = True
        panel.show_debug = True
        panel.search_text = ""
        panel.command_text = ""
        panel.command_output = ""
        panel.scroll_offset = 0.0
        adapter = ConsolePanelEditorControlAdapter(panel=panel, flags=EditorControlFeatureFlags(console_panel=True))
        adapter.control_model.search_text = "warn"

        def _render(_x, _y, _w, _h):
            panel.search_text = "after"

        panel.render.side_effect = _render

        adapter.render(1, 2, 3, 4)

        self.assertEqual(adapter.control_model.search_text, "after")
        panel.render.assert_called_once_with(1, 2, 3, 4)

    def test_layout_applies_persisted_feature_flags_to_console_adapter(self) -> None:
        layout = EditorLayout.__new__(EditorLayout)
        layout.screen_height = 600
        layout._panel_slots = SimpleNamespace(console_panel=None)
        layout.console_panel = ConsolePanelEditorControlAdapter()

        layout.apply_editor_preferences({"editor_feature_flags": {"console_panel": True}})

        self.assertTrue(layout.console_panel.flags.console_panel)

    def test_persist_editor_preferences_preserves_feature_flags_and_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "EditorProject"
            project_root.mkdir()
            (project_root / "project.json").write_text('{"name":"EditorProject"}', encoding="utf-8")
            (project_root / ".motor").mkdir()
            service = ProjectService(project_root, global_state_dir=Path(tmp) / "global")
            service.save_editor_state(
                {
                    "preferences": {
                        "editor_feature_flags": {"console_panel": True},
                        "editor_theme": "unity_light",
                    }
                }
            )
            layout = Mock()
            layout.export_editor_preferences.return_value = {"editor_active_tool": "Scale"}
            layout.export_dock_layout.return_value = {"root": "dock"}
            controller = ProjectWorkspaceController(
                get_project_service=lambda: service,
                get_scene_manager=lambda: None,
                get_editor_layout=lambda: layout,
                get_editor_selection=lambda: None,
                get_state=lambda: EngineState.EDIT,
                get_current_scene_path=lambda: "",
                set_current_scene_path=lambda _value: None,
                is_project_loaded=lambda: True,
                set_project_loaded=lambda _value: None,
                set_world=lambda _world: None,
                terminal_panel=None,
                animator_panel=None,
                sprite_editor_modal=None,
                history_manager=Mock(),
                hot_reload_manager=Mock(),
                timeline=Mock(),
                get_render_system=lambda: None,
                get_ui_render_system=lambda: None,
                get_audio_system=lambda: None,
                get_script_behaviour_system=lambda: None,
                get_rule_system=lambda: None,
                get_event_bus=lambda: None,
                load_scene_by_path=lambda _path: False,
                sync_scene_workspace_ui=lambda _value: None,
                save_all_dirty_scenes=lambda: True,
                save_scene_entry=lambda _path, _save_as: True,
                close_scene_workspace_tab=lambda _key, _prompt: True,
                stop_runtime=lambda: None,
                set_running=lambda _value: None,
            )

            controller.persist_editor_preferences()

            preferences = service.load_editor_state()["preferences"]
            self.assertEqual(preferences["editor_feature_flags"], {"console_panel": True})
            self.assertEqual(preferences["editor_theme"], "unity_light")
            self.assertEqual(preferences["editor_active_tool"], "Scale")


if __name__ == "__main__":
    unittest.main()
