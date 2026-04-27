import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pyray as rl
from engine.app.project_workspace_controller import ProjectWorkspaceController
from engine.core.engine_state import EngineState
from engine.editor.editor_selection import EditorSelectionState
from engine.project.project_service import ProjectService


class _FakeProjectPanel:
    def __init__(self) -> None:
        self.project_service = None

    def set_project_service(self, service) -> None:
        self.project_service = service


class _FakeEditorLayout:
    def __init__(self) -> None:
        self.project_panel = _FakeProjectPanel()
        self.flow_panel = Mock()
        self.flow_workspace_panel = Mock()
        self.terminal_panel = None
        self.active_tab = "GAME"
        self.show_project_launcher = True
        self.request_browse_project = False
        self.request_exit_launcher = False
        self.request_create_project = False
        self.request_remove_project_path = ""
        self.pending_project_path = ""
        self.show_project_dirty_modal = False
        self.project_switch_decision = ""
        self.dirty_modal_context = ""
        self.launcher_create_name = ""
        self.launcher_create_name_focused = False
        self.show_create_project_modal = False
        self.launcher_feedback: tuple[str, bool] | None = None
        self.recent_projects = None
        self.project_scene_entries = None
        self.scene_tabs = None
        self.applied_preferences = None
        self.editor_camera = SimpleNamespace(target=rl.Vector2(0.0, 0.0), zoom=1.0)

    def set_recent_projects(self, projects) -> None:
        self.recent_projects = list(projects)

    def set_project_scene_entries(self, entries) -> None:
        self.project_scene_entries = list(entries)

    def set_scene_tabs(self, scenes, active_key) -> None:
        self.scene_tabs = (list(scenes), active_key)

    def apply_editor_preferences(self, preferences) -> None:
        self.applied_preferences = dict(preferences)

    def export_editor_preferences(self) -> dict:
        return {"editor_active_tool": "Move", "panel": "PROJECT"}

    def set_launcher_feedback(self, message: str, is_error: bool = False) -> None:
        self.launcher_feedback = (message, is_error)


class _FakeSceneManager:
    def __init__(self) -> None:
        self.active_scene_key = ""
        self.current_scene = None
        self.has_unsaved_scenes = False
        self.selected_entity = None
        self.reset_workspace_called = False
        self.clear_all_dirty_called = False
        self.loaded_calls: list[tuple[str, bool]] = []
        self.activated_keys: list[str] = []
        self.scene_view_states: dict[str, dict] = {}
        self.workspace_state = {
            "open_scenes": [],
            "active_scene": "",
            "scene_view_states": {},
        }
        self.open_scene_entries: list[dict] = []
        self.edit_world = SimpleNamespace(selected_entity_name="Hero")

    def list_open_scenes(self) -> list[dict]:
        return list(self.open_scene_entries)

    def get_workspace_state(self) -> dict:
        return dict(self.workspace_state)

    def load_scene_from_file(self, path: str, activate: bool = False):
        self.loaded_calls.append((path, activate))
        if not any(entry.get("key") == path for entry in self.open_scene_entries):
            self.open_scene_entries.append({"key": path, "path": path, "dirty": False})
        if activate:
            self.active_scene_key = path
            self.current_scene = SimpleNamespace(source_path=path)
        return {"world": path}

    def set_scene_view_state(self, key: str, view_state: dict) -> None:
        self.scene_view_states[key] = dict(view_state)

    def get_scene_view_state(self) -> dict:
        return dict(self.scene_view_states.get(self.active_scene_key, {}))

    def activate_scene(self, key: str):
        self.activated_keys.append(key)
        self.active_scene_key = key
        self.current_scene = SimpleNamespace(source_path=key)
        return {"world": key}

    def set_selected_entity(self, name: str | None) -> None:
        self.selected_entity = name

    def get_edit_world(self):
        return self.edit_world

    def reset_workspace(self) -> None:
        self.reset_workspace_called = True
        self.open_scene_entries = []
        self.active_scene_key = ""
        self.current_scene = None

    def create_new_scene(self, name: str):
        self.current_scene = SimpleNamespace(source_path="")
        return {"created": name}

    def clear_all_dirty(self) -> None:
        self.clear_all_dirty_called = True


class ProjectWorkspaceControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"
        self.project_root = self.workspace / "WorkspaceProject"
        self.project_service = ProjectService(self.project_root, global_state_dir=self.global_state_dir)
        self.layout = _FakeEditorLayout()
        self.scene_manager = _FakeSceneManager()
        self.state = {"value": EngineState.EDIT}
        self.current_scene_path = {"value": ""}
        self.project_loaded = {"value": False}
        self.world_holder = {"world": None}
        self.running = {"value": True}
        self.selection_state = EditorSelectionState()
        self.terminal_panel = Mock()
        self.animator_panel = Mock()
        self.sprite_editor_modal = Mock()
        self.history_manager = Mock()
        self.hot_reload_manager = Mock()
        self.timeline = Mock()
        self.render_system = Mock()
        self.ui_render_system = Mock()
        self.audio_system = Mock()
        self.script_behaviour_system = Mock()
        self.rule_system = Mock()
        self.event_bus = Mock()
        self.sync_scene_workspace_ui = Mock()
        self.load_scene_by_path = Mock(return_value=False)
        self.save_all_dirty_scenes = Mock(return_value=True)
        self.save_scene_entry = Mock(return_value=True)
        self.close_scene_workspace_tab = Mock(return_value=True)
        self.stop_runtime = Mock()
        self.controller = ProjectWorkspaceController(
            get_project_service=lambda: self.project_service,
            get_scene_manager=lambda: self.scene_manager,
            get_editor_layout=lambda: self.layout,
            get_editor_selection=lambda: self.selection_state,
            get_state=lambda: self.state["value"],
            get_current_scene_path=lambda: self.current_scene_path["value"],
            set_current_scene_path=lambda value: self.current_scene_path.__setitem__("value", value),
            is_project_loaded=lambda: self.project_loaded["value"],
            set_project_loaded=lambda value: self.project_loaded.__setitem__("value", value),
            set_world=lambda world: self.world_holder.__setitem__("world", world),
            terminal_panel=self.terminal_panel,
            animator_panel=self.animator_panel,
            sprite_editor_modal=self.sprite_editor_modal,
            history_manager=self.history_manager,
            hot_reload_manager=self.hot_reload_manager,
            timeline=self.timeline,
            get_render_system=lambda: self.render_system,
            get_ui_render_system=lambda: self.ui_render_system,
            get_audio_system=lambda: self.audio_system,
            get_script_behaviour_system=lambda: self.script_behaviour_system,
            get_rule_system=lambda: self.rule_system,
            get_event_bus=lambda: self.event_bus,
            load_scene_by_path=self.load_scene_by_path,
            sync_scene_workspace_ui=self.sync_scene_workspace_ui,
            save_all_dirty_scenes=self.save_all_dirty_scenes,
            save_scene_entry=self.save_scene_entry,
            close_scene_workspace_tab=self.close_scene_workspace_tab,
            stop_runtime=self.stop_runtime,
            set_running=lambda value: self.running.__setitem__("value", value),
        )

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_set_project_service_propagates_to_panels_and_systems(self) -> None:
        self.controller.set_project_service(self.project_service)

        self.terminal_panel.set_project_service.assert_called_once_with(self.project_service)
        self.assertIs(self.layout.terminal_panel, self.terminal_panel)
        self.assertIsNotNone(self.layout.recent_projects)
        self.assertIsNotNone(self.layout.project_scene_entries)
        self.render_system.set_project_service.assert_called_once_with(self.project_service)
        self.ui_render_system.set_project_service.assert_called_once_with(self.project_service)
        self.audio_system.set_project_service.assert_called_once_with(self.project_service)
        self.animator_panel.set_project_service.assert_called_once_with(self.project_service)
        self.sprite_editor_modal.set_project_service.assert_called_once_with(self.project_service)
        self.sprite_editor_modal.set_history_manager.assert_called_once_with(self.history_manager)
        self.assertEqual(self.hot_reload_manager.scripts_dir, self.project_service.get_project_path("scripts").as_posix())
        self.hot_reload_manager.scan_directory.assert_called_once()
        self.script_behaviour_system.set_hot_reload_manager.assert_called_once_with(self.hot_reload_manager)
        self.script_behaviour_system.set_project_service.assert_called_once_with(self.project_service)
        self.assertIs(self.layout.project_panel.project_service, self.project_service)
        self.layout.flow_panel.set_project_service.assert_called_once_with(self.project_service)
        self.layout.flow_panel.set_scene_manager.assert_called_once_with(self.scene_manager)
        self.layout.flow_workspace_panel.set_project_service.assert_called_once_with(self.project_service)
        self.layout.flow_workspace_panel.set_scene_manager.assert_called_once_with(self.scene_manager)
        self.assertTrue(self.project_loaded["value"])

    def test_refresh_project_scene_entries_refreshes_flow_panel_snapshot(self) -> None:
        self.controller.set_project_service(self.project_service)
        self.layout.flow_panel.reset_mock()
        self.layout.flow_workspace_panel.reset_mock()

        self.controller.refresh_project_scene_entries()

        self.assertIsNotNone(self.layout.project_scene_entries)
        self.layout.flow_panel.refresh.assert_called_once_with(force=True)
        self.layout.flow_workspace_panel.refresh.assert_called_once_with(force=True)

    def test_persist_and_restore_workspace_state_round_trip(self) -> None:
        intro_path = self.project_root / "levels" / "intro.json"
        boss_path = self.project_root / "levels" / "boss.json"
        intro_path.write_text(json.dumps({"name": "Intro", "entities": [], "rules": []}), encoding="utf-8")
        boss_path.write_text(json.dumps({"name": "Boss", "entities": [], "rules": []}), encoding="utf-8")
        self.scene_manager.workspace_state = {
            "open_scenes": [intro_path.as_posix(), boss_path.as_posix()],
            "active_scene": boss_path.as_posix(),
            "scene_view_states": {
                intro_path.as_posix(): {
                    "selected_entity": "Hero",
                    "camera_target": {"x": 48.0, "y": 96.0},
                    "camera_zoom": 1.5,
                }
            },
        }
        self.current_scene_path["value"] = boss_path.as_posix()

        self.controller.persist_workspace_state()

        state = self.project_service.load_editor_state()
        self.assertEqual(state["open_scenes"], ["levels/intro.json", "levels/boss.json"])
        self.assertEqual(state["active_scene"], "levels/boss.json")
        self.assertEqual(state["last_scene"], "levels/boss.json")
        self.assertIn("levels/intro.json", state["scene_view_states"])

        self.scene_manager.loaded_calls.clear()
        self.scene_manager.activated_keys.clear()
        self.sync_scene_workspace_ui.reset_mock()

        restored = self.controller.restore_workspace_from_project_state()
        resolved_intro = self.project_service.resolve_path("levels/intro.json").as_posix()
        resolved_boss = self.project_service.resolve_path("levels/boss.json").as_posix()

        self.assertTrue(restored)
        self.assertEqual(
            self.scene_manager.loaded_calls,
            [
                (resolved_intro, False),
                (resolved_boss, False),
                (resolved_boss, False),
            ],
        )
        self.assertEqual(self.scene_manager.activated_keys, [resolved_boss])
        self.assertIn(resolved_intro, self.scene_manager.scene_view_states)
        self.assertEqual(self.scene_manager.active_scene_key, resolved_boss)
        self.assertEqual(
            self.scene_manager.get_scene_view_state(),
            {},
        )
        self.assertEqual(
            self.scene_manager.scene_view_states[resolved_intro]["camera_zoom"],
            1.5,
        )
        self.sync_scene_workspace_ui.assert_called_once_with(True)

    def test_reset_project_bound_state_resets_ui_render_resources(self) -> None:
        self.controller.reset_project_bound_state()

        self.render_system.reset_project_resources.assert_called_once()
        self.ui_render_system.reset_project_resources.assert_called_once()
        self.timeline.clear.assert_called_once()

    def test_open_project_resets_workspace_and_focuses_scene(self) -> None:
        with patch.object(self.controller, "restore_workspace_from_project_state", return_value=False), patch.object(
            self.controller, "pick_initial_scene_path", return_value=""
        ):
            result = self.controller.open_project(self.project_root.as_posix())

        self.assertTrue(result)
        self.history_manager.clear.assert_called_once()
        self.assertTrue(self.scene_manager.reset_workspace_called)
        self.assertEqual(self.world_holder["world"], {"created": "WorkspaceProject"})
        self.assertEqual(self.layout.active_tab, "SCENE")
        self.assertFalse(self.layout.show_project_launcher)
        self.assertIs(self.layout.project_panel.project_service, self.project_service)

    def test_handle_project_switch_requests_respects_dirty_modal_flow(self) -> None:
        target_project = (self.workspace / "OtherProject").as_posix()
        self.project_loaded["value"] = True
        self.scene_manager.has_unsaved_scenes = True
        self.layout.pending_project_path = target_project

        with patch.object(self.controller, "open_project", return_value=True) as open_project:
            self.controller.handle_project_switch_requests()
            self.assertTrue(self.layout.show_project_dirty_modal)
            self.assertEqual(self.layout.dirty_modal_context, "project_switch")
            open_project.assert_not_called()

            self.layout.show_project_dirty_modal = True
            self.layout.project_switch_decision = "discard"
            self.controller.handle_project_switch_requests()

        self.assertTrue(self.scene_manager.clear_all_dirty_called)
        open_project.assert_called_once_with(target_project)

    def test_capture_active_scene_view_state_syncs_shared_selection(self) -> None:
        self.scene_manager.active_scene_key = "scene-a"
        self.scene_manager.edit_world.selected_entity_name = "Hero"
        self.layout.editor_camera.target = rl.Vector2(12.0, 18.0)
        self.layout.editor_camera.zoom = 2.0

        self.controller.capture_active_scene_view_state()

        self.assertEqual(self.selection_state.entity_name, "Hero")
        self.assertEqual(self.scene_manager.scene_view_states["scene-a"]["selected_entity"], "Hero")

    def test_apply_active_scene_view_state_updates_shared_selection(self) -> None:
        self.scene_manager.active_scene_key = "scene-a"
        self.scene_manager.scene_view_states["scene-a"] = {
            "selected_entity": "Boss",
            "camera_target": {"x": 48.0, "y": 96.0},
            "camera_zoom": 1.5,
        }

        self.controller.apply_active_scene_view_state()

        self.assertEqual(self.selection_state.entity_name, "Boss")
        self.assertEqual(self.scene_manager.selected_entity, "Boss")
        self.assertEqual(self.scene_manager.edit_world.selected_entity_name, "Boss")
        self.assertEqual(float(self.layout.editor_camera.target.x), 48.0)
        self.assertEqual(float(self.layout.editor_camera.target.y), 96.0)
        self.assertEqual(float(self.layout.editor_camera.zoom), 1.5)


if __name__ == "__main__":
    unittest.main()
