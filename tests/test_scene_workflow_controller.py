import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from engine.app.scene_workflow_controller import SceneWorkflowController
from engine.core.engine_state import EngineState
from engine.project.project_service import ProjectService


class _FakeSceneManager:
    def __init__(self) -> None:
        self.active_scene_key = "scene-key"
        self.current_scene = SimpleNamespace(source_path="")
        self._entries: dict[str, SimpleNamespace] = {}
        self.saved_calls: list[tuple[str, str | None]] = []
        self.loaded_calls: list[tuple[str, bool]] = []
        self.created_calls: list[tuple[str, bool]] = []

    def add_entry(self, *, key: str, name: str, path: str = "", dirty: bool = False) -> None:
        self._entries[key] = SimpleNamespace(
            key=key,
            source_path=path,
            dirty=dirty,
            scene=SimpleNamespace(name=name),
        )

    def _resolve_entry(self, key: str | None):
        resolved_key = key or self.active_scene_key
        return self._entries.get(resolved_key)

    def resolve_entry(self, key: str | None):
        return self._resolve_entry(key)

    def save_scene_to_file(self, path: str, *, key: str | None = None) -> bool:
        resolved_key = key or self.active_scene_key
        self.saved_calls.append((path, resolved_key))
        entry = self._entries.get(resolved_key)
        if entry is not None:
            entry.source_path = path
            entry.dirty = False
        return True

    def list_open_scenes(self) -> list[dict]:
        return [
            {"key": entry.key, "path": entry.source_path, "dirty": entry.dirty}
            for entry in self._entries.values()
        ]

    def create_new_scene(self, name: str, activate: bool = True):
        self.created_calls.append((name, activate))
        return {"scene": name}

    def load_scene_from_file(self, path: str, activate: bool = True):
        self.loaded_calls.append((path, activate))
        self.current_scene = SimpleNamespace(source_path=path)
        if activate:
            self.active_scene_key = path
        return {"loaded": path}

    def activate_scene(self, key_or_path: str):
        self.active_scene_key = key_or_path
        return {"active": key_or_path}

    def close_scene(self, key: str, discard_changes: bool = False) -> bool:
        self._entries.pop(key, None)
        return True

    def reload_scene(self):
        return {"reloaded": True}


class SceneWorkflowControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "SceneWorkflowProject"
        self.project_service = ProjectService(self.project_root, global_state_dir=self.workspace / "global_state")
        self.scene_manager = _FakeSceneManager()
        self.layout = SimpleNamespace(
            active_tab="GAME",
            request_activate_scene_key="",
            request_close_scene_key="",
            pending_scene_close_key="",
            dirty_modal_context="",
            show_project_dirty_modal=False,
            request_new_scene=False,
            show_create_scene_modal=False,
            scene_create_name="",
            scene_create_name_focused=False,
            request_create_scene=False,
            request_save_scene=False,
            request_load_scene=False,
            pending_scene_open_path="",
            show_scene_browser_modal=False,
            request_browse_scene_file=False,
            project_switch_decision="",
        )
        self.state = {"value": EngineState.PLAY}
        self.world_holder = {"world": None}
        self.project_loaded = {"value": False}
        self.capture_active_scene_view_state = Mock()
        self.sync_scene_workspace_ui = Mock()
        self.refresh_project_scene_entries = Mock()
        self.clear_rules_and_events = Mock()
        self.stop_runtime = Mock()
        self.play_runtime = Mock()
        self.controller = SceneWorkflowController(
            get_scene_manager=lambda: self.scene_manager,
            get_project_service=lambda: self.project_service,
            get_editor_layout=lambda: self.layout,
            get_state=lambda: self.state["value"],
            stop_runtime=self.stop_runtime,
            capture_active_scene_view_state=self.capture_active_scene_view_state,
            sync_scene_workspace_ui=self.sync_scene_workspace_ui,
            refresh_project_scene_entries=self.refresh_project_scene_entries,
            clear_rules_and_events=self.clear_rules_and_events,
            set_world=lambda world: self.world_holder.__setitem__("world", world),
            set_project_loaded=lambda value: self.project_loaded.__setitem__("value", value),
            get_scene_flow=lambda: {"next": "levels/next.json"},
            play_runtime=self.play_runtime,
            get_level_loader=lambda: None,
        )

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_create_scene_saves_scene_and_focuses_scene_tab(self) -> None:
        result = self.controller.create_scene("Boss Intro")

        self.assertTrue(result)
        self.stop_runtime.assert_called_once()
        self.capture_active_scene_view_state.assert_called_once()
        self.assertEqual(self.scene_manager.created_calls, [("Boss Intro", True)])
        self.assertEqual(
            self.scene_manager.saved_calls,
            [(self.project_service.build_scene_file_path("Boss Intro").as_posix(), self.scene_manager.active_scene_key)],
        )
        self.assertEqual(self.world_holder["world"], {"scene": "Boss Intro"})
        self.assertTrue(self.project_loaded["value"])
        self.sync_scene_workspace_ui.assert_called_once_with(True)
        self.refresh_project_scene_entries.assert_called_once()
        self.assertEqual(self.layout.active_tab, "SCENE")

    def test_save_scene_entry_prompts_for_missing_path(self) -> None:
        self.scene_manager.add_entry(key="scene-key", name="Untitled", dirty=True)
        target_path = self.project_service.build_scene_file_path("Untitled").as_posix()
        self.controller.prompt_scene_save_path = Mock(return_value=target_path)

        result = self.controller.save_scene_entry(prompt_if_needed=True)

        self.assertTrue(result)
        self.controller.prompt_scene_save_path.assert_called_once_with("Untitled")
        self.capture_active_scene_view_state.assert_called_once()
        self.assertEqual(self.scene_manager.saved_calls, [(target_path, "scene-key")])
        self.sync_scene_workspace_ui.assert_called_once_with(False)

    def test_autosave_dirty_scenes_only_persists_entries_with_path(self) -> None:
        valid_path = self.project_service.build_scene_file_path("SavedScene").as_posix()
        self.scene_manager.add_entry(key="scene-key", name="SavedScene", path=valid_path, dirty=True)
        self.scene_manager.add_entry(key="untitled", name="Untitled", path="", dirty=True)
        self.scene_manager._entries["missing-key"] = SimpleNamespace(
            key="",
            source_path=self.project_service.build_scene_file_path("Ghost").as_posix(),
            dirty=True,
            scene=SimpleNamespace(name="Ghost"),
        )

        self.controller.autosave_dirty_scenes()

        self.capture_active_scene_view_state.assert_called_once()
        self.assertEqual(self.scene_manager.saved_calls, [(valid_path, "scene-key")])
        self.sync_scene_workspace_ui.assert_called_once_with(False)

    def test_load_scene_by_path_stops_runtime_and_syncs_workspace(self) -> None:
        scene_path = self.project_service.build_scene_file_path("Playable").as_posix()
        Path(scene_path).parent.mkdir(parents=True, exist_ok=True)
        Path(scene_path).write_text('{"name":"Playable","entities":[],"rules":[]}', encoding="utf-8")

        result = self.controller.load_scene_by_path("levels/Playable.json")

        self.assertTrue(result)
        self.stop_runtime.assert_called_once()
        self.capture_active_scene_view_state.assert_called_once()
        self.assertEqual(self.scene_manager.loaded_calls, [(scene_path, True)])
        self.clear_rules_and_events.assert_called_once()
        self.assertEqual(self.world_holder["world"], {"loaded": scene_path})
        self.assertTrue(self.project_loaded["value"])
        self.sync_scene_workspace_ui.assert_called_once_with(True)
        self.assertEqual(self.layout.active_tab, "SCENE")

    def test_handle_scene_ui_requests_opens_new_scene_modal(self) -> None:
        self.layout.active_tab = "ANIMATOR"
        self.layout.request_new_scene = True

        self.controller.handle_scene_ui_requests()

        self.assertEqual(self.layout.active_tab, "SCENE")
        self.assertFalse(self.layout.request_new_scene)
        self.assertTrue(self.layout.show_create_scene_modal)
        self.assertEqual(self.layout.scene_create_name, "New Scene")
        self.assertTrue(self.layout.scene_create_name_focused)


if __name__ == "__main__":
    unittest.main()
