import importlib
import importlib.util
import os
import tempfile
import unittest
from argparse import Namespace
from unittest.mock import patch

from editor_qt.bridge.engine_facade import EditorEngineFacade
from editor_qt.value_codec import parse_value
from editor_qt.viewmodels import (
    normalize_agent_provider,
    normalize_animator_info,
    normalize_asset_summary,
    normalize_flow_connections,
    normalize_project_manifest,
    normalize_scene_summary,
    normalize_viewport_entity,
)


class FakeEngineAPI:
    def __init__(self) -> None:
        self.entities = {
            "Player": {
                "name": "Player",
                "active": True,
                "tag": "",
                "layer": "",
                "parent": None,
                "components": {"Transform": {"x": 1}},
            }
        }
        self.edits: list[tuple[str, str, str, object]] = []
        self.scene_loads: list[str] = []
        self.open_project_calls: list[str] = []
        self.create_project_calls: list[tuple[str, str]] = []
        self.created_scenes: list[str] = []
        self.asset_refresh_calls = 0
        self.created_canvases: list[str] = []
        self.created_texts: list[tuple[str, str, str]] = []
        self.created_buttons: list[tuple[str, str, str]] = []
        self.scene_connection_calls: list[tuple[str, str]] = []
        self.add_component_calls: list[tuple[str, str, dict]] = []
        self.animator_sheet_calls: list[tuple[str, str]] = []
        self.animator_speed_calls: list[tuple[str, float]] = []
        self.animator_flip_calls: list[tuple[str, bool, bool]] = []
        self.animator_upsert_calls: list[tuple[str, str, list, float, bool, object, bool]] = []
        self.animator_remove_calls: list[tuple[str, str]] = []
        self.agent_session_calls = 0
        self.agent_messages: list[tuple[str, str]] = []
        self.agent_approvals: list[tuple[str, str, bool]] = []
        self.save_calls = 0
        self.undo_calls = 0
        self.redo_calls = 0
        self.dirty = False
        self.save_fails = False

    def list_entities(self):
        return list(self.entities.values())

    def get_entity(self, name):
        return self.entities[name]

    def edit_component(self, entity_name, component_name, property_name, value):
        self.edits.append((entity_name, component_name, property_name, value))
        self.entities[entity_name]["components"][component_name][property_name] = value
        self.dirty = True
        return {"success": True, "message": "Edit applied", "data": None}

    def create_entity(self, name):
        self.entities[name] = {
            "name": name,
            "active": True,
            "tag": "",
            "layer": "",
            "parent": None,
            "components": {},
        }
        self.dirty = True
        return {"success": True, "message": "Entity created", "data": {"entity": name}}

    def delete_entity(self, name):
        self.entities.pop(name, None)
        self.dirty = True
        return {"success": True, "message": "Entity removed", "data": {"entity": name}}

    def get_project_manifest(self):
        return {"name": "Test Project", "root": "C:/project", "engine_version": "test"}

    def list_recent_projects(self):
        return [{"name": "Recent Game", "path": "C:/project", "engine_version": "test", "activity": "today"}]

    def open_project(self, path):
        self.open_project_calls.append(path)
        return {"success": True, "message": "Project opened", "data": {"path": path}}

    def create_project(self, path, name=""):
        self.create_project_calls.append((path, name))
        return {"success": True, "message": "Project created", "data": {"path": path, "name": name}}

    def get_active_scene_info(self):
        return {
            "has_scene": True,
            "name": "Main",
            "path": "levels/main.json",
            "entity_count": len(self.entities),
            "dirty": self.dirty,
        }

    def list_project_scenes(self):
        return [{"name": "Main", "path": "levels/main.json"}]

    def list_project_assets(self):
        return [{"name": "Hero", "path": "assets/hero.png", "asset_type": "texture"}]

    def list_project_scripts(self):
        return ["scripts/player.py"]

    def list_project_prefabs(self):
        return ["prefabs/enemy.prefab"]

    def list_open_scenes(self):
        return [
            {
                "has_scene": True,
                "name": "Main",
                "path": "levels/main.json",
                "entity_count": len(self.entities),
                "dirty": self.dirty,
            }
        ]

    def load_scene_for_runtime_inspection(self, scene_ref=""):
        self.scene_loads.append(scene_ref)
        self.dirty = False
        return {
            "success": True,
            "message": "Scene loaded for read-only runtime inspection",
            "data": {"path": scene_ref or "levels/main.json", "entity_count": 1},
        }

    def create_scene(self, name):
        self.created_scenes.append(name)
        self.dirty = True
        return {"success": True, "message": "Scene created", "data": {"path": f"levels/{name}.json"}}

    def create_canvas(self, name="Canvas"):
        self.created_canvases.append(name)
        return self.create_entity(name)

    def create_ui_text(self, name, text, parent):
        self.created_texts.append((name, text, parent))
        return self.create_entity(name)

    def create_ui_button(self, name, label, parent):
        self.created_buttons.append((name, label, parent))
        return self.create_entity(name)

    def refresh_asset_catalog(self):
        self.asset_refresh_calls += 1
        return {"success": True, "message": "Asset catalog refreshed", "data": {"count": 1}}

    def get_scene_connections(self):
        return {"next_scene": "levels/main.json"}

    def set_scene_connection(self, key, path):
        self.scene_connection_calls.append((key, path))
        return {"success": True, "message": "Scene flow updated", "data": {"key": key, "path": path}}

    def add_component(self, entity_name, component_name, payload):
        self.add_component_calls.append((entity_name, component_name, payload))
        self.entities[entity_name]["components"][component_name] = dict(payload)
        return {"success": True, "message": "Component added", "data": {"entity": entity_name}}

    def get_animator_info(self, entity_name):
        animator = self.entities.get(entity_name, {}).get("components", {}).get("Animator")
        if not animator:
            return {"exists": False}
        return {
            "exists": True,
            "sprite_sheet": animator.get("sprite_sheet", ""),
            "speed": animator.get("speed", 1.0),
            "flip_x": animator.get("flip_x", False),
            "flip_y": animator.get("flip_y", False),
            "states": [{"name": "idle", "frame_count": 1, "fps": 8.0, "loop": True, "is_default": True}],
        }

    def list_animator_states(self, entity_name):
        return self.get_animator_info(entity_name).get("states", [])

    def set_animator_sprite_sheet(self, entity_name, asset_path):
        self.animator_sheet_calls.append((entity_name, asset_path))
        self.entities[entity_name]["components"].setdefault("Animator", {})["sprite_sheet"] = asset_path
        return {"success": True, "message": "Animator sheet updated", "data": {"entity": entity_name}}

    def upsert_animator_state(self, entity_name, state_name, slice_names, fps, loop, on_complete, set_default=False):
        self.animator_upsert_calls.append((entity_name, state_name, slice_names, fps, loop, on_complete, set_default))
        return {"success": True, "message": "Animator state updated", "data": {"entity": entity_name, "state": state_name}}

    def remove_animator_state(self, entity_name, state_name):
        self.animator_remove_calls.append((entity_name, state_name))
        return {"success": True, "message": "Animator state removed", "data": {"entity": entity_name, "state": state_name}}

    def set_animator_speed(self, entity_name, speed):
        self.animator_speed_calls.append((entity_name, speed))
        return {"success": True, "message": "Animator speed updated", "data": {"entity": entity_name}}

    def set_animator_flip(self, entity_name, flip_x=None, flip_y=None):
        self.animator_flip_calls.append((entity_name, bool(flip_x), bool(flip_y)))
        return {"success": True, "message": "Animator flip updated", "data": {"entity": entity_name}}

    def list_agent_providers(self):
        return [{"id": "fake", "name": "Fake", "status": "ready"}]

    def list_agent_tools(self):
        return [{"name": "entity.create"}]

    def create_agent_session(self, *args, **kwargs):
        self.agent_session_calls += 1
        return {"success": True, "message": "Agent session created", "data": {"session_id": "session-1", "status": "ready"}}

    def send_agent_message(self, session_id, message):
        self.agent_messages.append((session_id, message))
        return {"success": True, "message": "Agent message processed", "data": {"session_id": session_id, "response": "ok"}}

    def approve_agent_action(self, session_id, action_id, approved):
        self.agent_approvals.append((session_id, action_id, approved))
        return {"success": True, "message": "Agent action resolved", "data": {"session_id": session_id, "status": "ready"}}

    def save_scene(self):
        self.save_calls += 1
        if self.save_fails:
            return {"success": False, "message": "Scene save failed", "data": None}
        self.dirty = False
        return {"success": True, "message": "Scene saved", "data": {"path": "levels/main.json"}}

    def undo(self):
        self.undo_calls += 1
        self.dirty = True
        return {"success": True, "message": "Undo applied", "data": None}

    def redo(self):
        self.redo_calls += 1
        self.dirty = True
        return {"success": True, "message": "Redo applied", "data": None}


class EditorQtFoundationTests(unittest.TestCase):
    def test_facade_delegates_entity_operations_to_engine_api(self) -> None:
        api = FakeEngineAPI()
        facade = EditorEngineFacade(engine_api=api)

        self.assertEqual([entity["name"] for entity in facade.list_entities()], ["Player"])
        self.assertEqual(facade.select_entity("Player")["name"], "Player")
        self.assertEqual(facade.selected_entity_name, "Player")

        edit = facade.update_component_property("Player", "Transform", "x", 42)
        self.assertTrue(edit["success"])
        self.assertEqual(api.entities["Player"]["components"]["Transform"]["x"], 42)

        create = facade.create_entity("Enemy")
        self.assertTrue(create["success"])
        self.assertIn("Enemy", api.entities)

        delete = facade.delete_entity("Enemy")
        self.assertTrue(delete["success"])
        self.assertNotIn("Enemy", api.entities)

    def test_facade_delegates_save_scene_to_engine_api(self) -> None:
        api = FakeEngineAPI()
        facade = EditorEngineFacade(engine_api=api)

        result = facade.save_scene()

        self.assertTrue(result["success"])
        self.assertEqual(api.save_calls, 1)

    def test_facade_delegates_undo_redo_to_engine_api(self) -> None:
        api = FakeEngineAPI()
        facade = EditorEngineFacade(engine_api=api)

        self.assertTrue(facade.undo()["success"])
        self.assertTrue(facade.redo()["success"])

        self.assertEqual(api.undo_calls, 1)
        self.assertEqual(api.redo_calls, 1)

    def test_facade_reads_unsaved_changes_from_active_scene_info(self) -> None:
        api = FakeEngineAPI()
        facade = EditorEngineFacade(engine_api=api)

        self.assertFalse(facade.has_unsaved_changes())
        api.dirty = True
        self.assertTrue(facade.has_unsaved_changes())

    def test_facade_delegates_project_scene_asset_and_ui_routes(self) -> None:
        api = FakeEngineAPI()
        facade = EditorEngineFacade(engine_api=api)

        self.assertEqual(facade.list_recent_projects()[0]["root"], "C:/project")
        self.assertTrue(facade.open_project("C:/project")["success"])
        self.assertTrue(facade.create_scene("NewScene")["success"])
        self.assertTrue(facade.refresh_assets()["success"])
        self.assertTrue(facade.create_canvas("Canvas")["success"])
        self.assertTrue(facade.create_ui_text(parent="Canvas")["success"])
        self.assertTrue(facade.create_ui_button(parent="Canvas")["success"])

        self.assertEqual(api.open_project_calls, ["C:/project"])
        self.assertEqual(api.created_scenes, ["NewScene"])
        self.assertEqual(api.asset_refresh_calls, 1)
        self.assertEqual(api.created_canvases, ["Canvas"])
        self.assertEqual(api.created_texts, [("Text", "Text", "Canvas")])
        self.assertEqual(api.created_buttons, [("Button", "Button", "Canvas")])
        self.assertEqual(facade.list_project_scripts(), ["scripts/player.py"])
        self.assertEqual(facade.list_project_prefabs(), ["prefabs/enemy.prefab"])

    def test_facade_delegates_create_project_flow_animator_and_agent_routes(self) -> None:
        api = FakeEngineAPI()
        facade = EditorEngineFacade(engine_api=api)

        self.assertTrue(facade.create_project("C:/new", "New Game")["success"])
        self.assertEqual(facade.get_scene_connections(), [{"key": "next_scene", "target": "levels/main.json"}])
        self.assertTrue(facade.set_scene_connection("menu_scene", "levels/menu.json")["success"])
        self.assertTrue(facade.ensure_animator("Player")["success"])
        self.assertTrue(facade.set_animator_sprite_sheet("Player", "assets/player.png")["success"])
        self.assertTrue(facade.upsert_animator_state("Player", "idle", ["idle_0"], 8.0, True, None, True)["success"])
        self.assertTrue(facade.remove_animator_state("Player", "idle")["success"])
        self.assertTrue(facade.set_animator_speed("Player", 1.25)["success"])
        self.assertTrue(facade.set_animator_flip("Player", True, False)["success"])
        self.assertEqual(facade.list_agent_providers()[0]["id"], "fake")
        self.assertEqual(facade.list_agent_tools()[0]["name"], "entity.create")
        session = facade.create_agent_session()
        self.assertTrue(session["success"])
        self.assertEqual(session["data"]["session_id"], "session-1")
        self.assertTrue(facade.send_agent_message("session-1", "hola")["success"])
        self.assertTrue(facade.approve_agent_action("session-1", "action-1", True)["success"])

        self.assertEqual(api.create_project_calls, [("C:/new", "New Game")])
        self.assertEqual(api.scene_connection_calls, [("menu_scene", "levels/menu.json")])
        self.assertEqual(api.add_component_calls[0][1], "Animator")
        self.assertEqual(api.animator_sheet_calls, [("Player", "assets/player.png")])
        self.assertEqual(api.animator_speed_calls, [("Player", 1.25)])
        self.assertEqual(api.animator_flip_calls, [("Player", True, False)])
        self.assertEqual(api.agent_messages, [("session-1", "hola")])
        self.assertEqual(api.agent_approvals, [("session-1", "action-1", True)])

    def test_engine_api_create_project_creates_and_rejects_non_empty_directory(self) -> None:
        from pathlib import Path

        from engine.api import EngineAPI

        with tempfile.TemporaryDirectory() as temp_dir:
            api = EngineAPI(project_root=temp_dir)
            try:
                target = Path(temp_dir) / "CreatedProject"
                result = api.create_project(target.as_posix(), "Created Project")
                self.assertTrue(result["success"], result.get("message"))
                self.assertTrue((target / "project.json").exists())

                non_empty = Path(temp_dir) / "NonEmpty"
                non_empty.mkdir()
                (non_empty / "file.txt").write_text("x", encoding="utf-8")
                failed = api.create_project(non_empty.as_posix(), "Bad")
                self.assertFalse(failed["success"])
            finally:
                api.shutdown()

    def test_facade_undo_redo_with_real_engine_api_project(self) -> None:
        from engine.api import EngineAPI

        with tempfile.TemporaryDirectory() as temp_dir:
            api = EngineAPI(project_root=temp_dir)
            try:
                facade = EditorEngineFacade(engine_api=api)
                self.assertTrue(api.create_scene("Qt Undo Scene")["success"])

                self.assertTrue(facade.create_entity("Probe")["success"])
                self.assertTrue(facade.update_component_property("Probe", "Transform", "x", 10.0)["success"])
                self.assertEqual(facade.get_entity("Probe")["components"]["Transform"]["x"], 10.0)
                self.assertTrue(facade.has_unsaved_changes())

                self.assertTrue(facade.undo()["success"])
                self.assertEqual(facade.get_entity("Probe")["components"]["Transform"]["x"], 0.0)

                self.assertTrue(facade.redo()["success"])
                self.assertEqual(facade.get_entity("Probe")["components"]["Transform"]["x"], 10.0)
            finally:
                api.shutdown()

    def test_facade_loads_default_scene_for_runtime_inspection(self) -> None:
        api = FakeEngineAPI()
        facade = EditorEngineFacade(engine_api=api)

        result = facade.load_default_scene()

        self.assertTrue(result["success"])
        self.assertEqual(api.scene_loads, [""])

    def test_facade_loads_explicit_scene_for_runtime_inspection(self) -> None:
        api = FakeEngineAPI()
        facade = EditorEngineFacade(engine_api=api)

        result = facade.load_scene("levels/other.json")

        self.assertTrue(result["success"])
        self.assertEqual(api.scene_loads, ["levels/other.json"])

    def test_viewmodels_normalize_project_scene_and_asset_payloads(self) -> None:
        project = normalize_project_manifest({"name": "Game", "root": "C:/game"})
        scene = normalize_scene_summary({"path": "levels/level_one.json"})
        asset = normalize_asset_summary({"path": "assets/player.png"})
        viewport_entity = normalize_viewport_entity(
            {"name": "Box", "components": {"Transform": {"x": "2", "y": 3}, "Sprite": {"asset_path": "assets/box.png"}}}
        )
        flow = normalize_flow_connections({"next_scene": "levels/next.json"})
        animator = normalize_animator_info({"exists": True, "sprite_sheet_path": "assets/sheet.png", "speed": "2"})
        provider = normalize_agent_provider({"id": "fake", "models": ["m"]})

        self.assertEqual(project["name"], "Game")
        self.assertTrue(project["has_project"])
        self.assertEqual(scene["name"], "level one")
        self.assertEqual(scene["path"], "levels/level_one.json")
        self.assertEqual(asset["name"], "player.png")
        self.assertEqual(asset["type"], "png")
        self.assertEqual(viewport_entity["x"], 2.0)
        self.assertEqual(viewport_entity["sprite"], "assets/box.png")
        self.assertEqual(flow, [{"key": "next_scene", "target": "levels/next.json"}])
        self.assertEqual(animator["sprite_sheet"], "assets/sheet.png")
        self.assertEqual(provider["id"], "fake")

    def test_value_codec_preserves_supported_types(self) -> None:
        self.assertIs(parse_value("true", False), True)
        self.assertIs(parse_value("false", True), False)
        self.assertEqual(parse_value("42", 1), 42)
        self.assertEqual(parse_value("3.5", 1.0), 3.5)
        self.assertEqual(parse_value("hello", "old"), "hello")
        self.assertEqual(parse_value("[1, 2]", []), [1, 2])
        self.assertEqual(parse_value('{"x": 1}', {}), {"x": 1})
        self.assertIsNone(parse_value("null", None))

    def test_value_codec_rejects_invalid_json_for_containers(self) -> None:
        with self.assertRaises(ValueError):
            parse_value("{broken", {})
        with self.assertRaises(ValueError):
            parse_value('{"not": "list"}', [])

    def test_facade_module_import_does_not_require_pyside6(self) -> None:
        module = importlib.import_module("editor_qt.bridge.engine_facade")
        self.assertIs(module.EditorEngineFacade, EditorEngineFacade)

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_qt_modules_import_when_pyside6_is_available(self) -> None:
        modules = (
            "editor_qt.app",
            "editor_qt.launcher_window",
            "editor_qt.main_window",
            "editor_qt.panels.agent_panel",
            "editor_qt.panels.animator_panel",
            "editor_qt.panels.flow_panel",
            "editor_qt.panels.hierarchy_panel",
            "editor_qt.panels.inspector_panel",
            "editor_qt.panels.project_panel",
            "editor_qt.panels.terminal_panel",
            "editor_qt.panels.viewport_panel",
            "editor_qt.panels.console_panel",
        )
        for module_name in modules:
            with self.subTest(module=module_name):
                self.assertIsNotNone(importlib.import_module(module_name))

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_app_builds_launcher_without_project(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        import editor_qt.app as app_module
        from editor_qt.launcher_window import LauncherWindow

        app = QApplication.instance() or QApplication([])

        def fake_facade_factory(**_kwargs):
            return EditorEngineFacade(engine_api=FakeEngineAPI())

        with patch.object(app_module, "EditorEngineFacade", side_effect=fake_facade_factory):
            window = app_module._create_startup_window(app, Namespace(project="", scene=""))
        try:
            self.assertIsInstance(window, LauncherWindow)
            self.assertEqual(window.projects_table.rowCount(), 1)
            self.assertTrue(window.new_project_button.isEnabled())
        finally:
            window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_launcher_new_project_calls_facade_and_emits_project_path(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        import editor_qt.launcher_window as launcher_module
        from editor_qt.launcher_window import LauncherWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        launcher = LauncherWindow(facade=EditorEngineFacade(engine_api=api))
        received: list[str] = []
        launcher.project_open_requested.connect(received.append)
        with (
            patch.object(launcher_module.QFileDialog, "getExistingDirectory", return_value="C:/new"),
            patch.object(launcher_module.QInputDialog, "getText", return_value=("New Game", True)),
        ):
            launcher.new_project_button.click()
        app.processEvents()
        try:
            self.assertEqual(api.create_project_calls, [("C:/new", "New Game")])
            self.assertEqual(received, ["C:/new"])
        finally:
            launcher.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_app_builds_editor_shell_with_project(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        import editor_qt.app as app_module
        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])

        def fake_facade_factory(**_kwargs):
            return EditorEngineFacade(engine_api=FakeEngineAPI())

        with patch.object(app_module, "EditorEngineFacade", side_effect=fake_facade_factory):
            window = app_module._create_startup_window(app, Namespace(project=".", scene=""))
        try:
            self.assertIsInstance(window, MainWindow)
            self.assertEqual([window.center_tabs.tabText(index) for index in range(4)], ["Scene", "Game", "Flow", "Animator"])
            self.assertEqual(
                [window.bottom_tabs.tabText(index) for index in range(window.bottom_tabs.count())],
                ["Project", "Flow", "Console", "Terminal", "Agent"],
            )
        finally:
            window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_main_window_has_legacy_composition_menus_toolbar_and_tabs(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from editor_qt.main_window import MainWindow
        from editor_qt.panels.agent_panel import AgentPanel
        from editor_qt.panels.animator_panel import AnimatorPanel
        from editor_qt.panels.flow_panel import FlowPanel
        from editor_qt.panels.terminal_panel import TerminalPanel
        from editor_qt.panels.viewport_panel import QtSceneViewportPanel

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        window = MainWindow(facade=EditorEngineFacade(engine_api=api))
        app.processEvents()
        try:
            menu_names = [action.text() for action in window.menuBar().actions()]
            self.assertEqual(menu_names, ["File", "Edit", "Assets", "GameObject", "Component", "Window", "Help"])
            self.assertEqual([window.center_tabs.tabText(index) for index in range(4)], ["Scene", "Game", "Flow", "Animator"])
            self.assertEqual(
                [window.bottom_tabs.tabText(index) for index in range(window.bottom_tabs.count())],
                ["Project", "Flow", "Console", "Terminal", "Agent"],
            )
            self.assertFalse(window.play_action.isEnabled())
            self.assertFalse(window.pause_action.isEnabled())
            self.assertFalse(window.step_action.isEnabled())
            self.assertFalse(window.add_component_action.isEnabled())
            self.assertIsInstance(window.scene_viewport, QtSceneViewportPanel)
            self.assertIsInstance(window.game_viewport, QtSceneViewportPanel)
            self.assertIsInstance(window.flow_panel, FlowPanel)
            self.assertIsInstance(window.animator_panel, AnimatorPanel)
            self.assertIsInstance(window.terminal_panel, TerminalPanel)
            self.assertIsInstance(window.agent_panel, AgentPanel)
        finally:
            window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_main_window_menu_and_toolbar_actions_delegate_to_facade(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        import editor_qt.main_window as main_window_module
        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        window = MainWindow(facade=EditorEngineFacade(engine_api=api))
        app.processEvents()
        try:
            with patch.object(main_window_module.QInputDialog, "getText", return_value=("Empty", True)):
                window.create_empty_action.trigger()
            window.save_scene_action.trigger()
            window.undo_action.trigger()
            window.redo_action.trigger()
            window.create_canvas_action.trigger()
            window.create_text_action.trigger()
            window.create_button_action.trigger()
            window.refresh_assets_action.trigger()
            app.processEvents()

            self.assertIn("Empty", api.entities)
            self.assertEqual(api.save_calls, 1)
            self.assertEqual(api.undo_calls, 1)
            self.assertEqual(api.redo_calls, 1)
            self.assertEqual(api.created_canvases, ["Canvas"])
            self.assertEqual(api.created_texts, [("Text", "Text", "Canvas")])
            self.assertEqual(api.created_buttons, [("Button", "Button", "Canvas")])
            self.assertEqual(api.asset_refresh_calls, 1)
        finally:
            api.dirty = False
            window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_flow_animator_terminal_agent_and_viewport_are_wired(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        window = MainWindow(facade=EditorEngineFacade(engine_api=api))
        window.resize(900, 600)
        app.processEvents()
        try:
            window.flow_panel.table.item(0, 0).setText("menu_scene")
            window.flow_panel.table.item(0, 1).setText("levels/menu.json")
            window.flow_panel.table.setCurrentCell(0, 0)
            window.flow_panel.apply_button.click()

            window._on_entity_selected("Player")
            window.animator_panel.ensure_button.click()
            window.animator_panel.sprite_sheet_edit.setText("assets/player.png")
            window.animator_panel.apply_sheet_button.click()
            window.animator_panel.speed_spin.setValue(1.5)
            window.animator_panel.flip_x_check.setChecked(True)
            window.animator_panel.apply_speed_button.click()
            window.animator_panel.state_name_edit.setText("idle")
            window.animator_panel.slice_names_edit.setText("idle_0,idle_1")
            window.animator_panel.upsert_state_button.click()

            self.assertIsNone(window.terminal_panel.process)
            window.agent_panel.start_button.click()
            window.agent_panel.message_input.setText("status")
            window.agent_panel.send_button.click()
            app.processEvents()

            pixmap = window.scene_viewport.grab()
            self.assertFalse(pixmap.isNull())
            self.assertGreater(window.scene_viewport.width(), 0)

            self.assertEqual(api.scene_connection_calls[-1], ("menu_scene", "levels/menu.json"))
            self.assertEqual(api.add_component_calls[-1][1], "Animator")
            self.assertEqual(api.animator_sheet_calls[-1], ("Player", "assets/player.png"))
            self.assertEqual(api.animator_speed_calls[-1], ("Player", 1.5))
            self.assertEqual(api.animator_flip_calls[-1], ("Player", True, False))
            self.assertEqual(api.animator_upsert_calls[-1][1], "idle")
            self.assertEqual(api.agent_session_calls, 1)
            self.assertEqual(api.agent_messages, [("session-1", "status")])
        finally:
            window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_center_and_bottom_tab_changes_update_status_without_mutation(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        window = MainWindow(facade=EditorEngineFacade(engine_api=api))
        app.processEvents()
        try:
            window.center_tabs.setCurrentIndex(1)
            window.bottom_tabs.setCurrentIndex(2)
            app.processEvents()

            self.assertIn("View: Game", window.statusBar().currentMessage())
            self.assertEqual(api.edits, [])
            self.assertEqual(api.save_calls, 0)
        finally:
            window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_main_window_smoke_loads_default_scene_with_fake_facade(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        facade = EditorEngineFacade(engine_api=api)

        window = MainWindow(facade=facade)
        app.processEvents()
        try:
            self.assertEqual(window.windowTitle(), "MotorVideojuegosIA Editor")
            self.assertEqual(api.scene_loads, [""])
            self.assertEqual(window.hierarchy_panel.tree.topLevelItem(0).text(0), "Player")
        finally:
            window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_inspector_panel_emits_property_edit_without_engine_access(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from editor_qt.panels.inspector_panel import InspectorPanel

        app = QApplication.instance() or QApplication([])
        panel = InspectorPanel()
        received: list[tuple[str, str, str, str, object]] = []
        panel.property_edit_requested.connect(lambda *args: received.append(args))
        panel.set_entity(
            {
                "name": "Player",
                "components": {"Transform": {"x": 1, "enabled": True}},
            }
        )

        panel.table.item(0, 2).setText("5")
        app.processEvents()

        self.assertEqual(received[0], ("Player", "Transform", "enabled", "5", True))

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_hierarchy_panel_emits_delete_request_without_engine_mutation(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from editor_qt.panels.hierarchy_panel import HierarchyPanel

        app = QApplication.instance() or QApplication([])
        facade = EditorEngineFacade(engine_api=FakeEngineAPI())
        panel = HierarchyPanel(facade)
        received: list[str] = []
        panel.entity_delete_requested.connect(received.append)
        panel.refresh()
        panel.tree.setCurrentItem(panel.tree.topLevelItem(0))

        panel._request_delete_entity()
        app.processEvents()

        self.assertEqual(received, ["Player"])

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_main_window_applies_inspector_edit_through_facade(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        facade = EditorEngineFacade(engine_api=api)
        window = MainWindow(facade=facade)
        app.processEvents()
        try:
            window._on_entity_selected("Player")
            value_item = window.inspector_panel.table.item(0, 2)
            value_item.setText("7")
            app.processEvents()

            self.assertIn(("Player", "Transform", "x", 7), api.edits)
            self.assertEqual(api.entities["Player"]["components"]["Transform"]["x"], 7)
            self.assertIn("Unsaved", window.statusBar().currentMessage())
        finally:
            api.dirty = False
            window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_main_window_undo_redo_actions_call_facade_and_refresh(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        window = MainWindow(facade=EditorEngineFacade(engine_api=api))
        app.processEvents()
        try:
            window.undo_action.trigger()
            window.redo_action.trigger()
            app.processEvents()

            self.assertEqual(api.undo_calls, 1)
            self.assertEqual(api.redo_calls, 1)
            self.assertIn("Unsaved", window.statusBar().currentMessage())
        finally:
            api.dirty = False
            window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_main_window_save_updates_dirty_status(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        window = MainWindow(facade=EditorEngineFacade(engine_api=api))
        app.processEvents()
        try:
            api.dirty = True
            window._refresh_project_panel()
            self.assertIn("Unsaved", window.statusBar().currentMessage())

            window.save_scene_action.trigger()
            app.processEvents()

            self.assertEqual(api.save_calls, 1)
            self.assertIn("Saved", window.statusBar().currentMessage())
        finally:
            window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_main_window_close_clean_scene_does_not_block(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        window = MainWindow(facade=EditorEngineFacade(engine_api=api))
        app.processEvents()

        api.dirty = False
        window.close()
        app.processEvents()

        self.assertFalse(window.isVisible())

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_main_window_close_dirty_cancel_blocks_close(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QCloseEvent
        from PySide6.QtWidgets import QApplication, QMessageBox

        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        window = MainWindow(facade=EditorEngineFacade(engine_api=api))
        api.dirty = True
        window._confirm_close_with_unsaved_changes = lambda: QMessageBox.StandardButton.Cancel
        event = QCloseEvent()

        window.closeEvent(event)
        app.processEvents()

        self.assertFalse(event.isAccepted())
        api.dirty = False
        window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_main_window_close_dirty_discard_accepts_without_save(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QCloseEvent
        from PySide6.QtWidgets import QApplication, QMessageBox

        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        window = MainWindow(facade=EditorEngineFacade(engine_api=api))
        api.dirty = True
        window._confirm_close_with_unsaved_changes = lambda: QMessageBox.StandardButton.Discard
        event = QCloseEvent()

        window.closeEvent(event)
        app.processEvents()

        self.assertTrue(event.isAccepted())
        self.assertEqual(api.save_calls, 0)
        api.dirty = False
        window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_main_window_close_dirty_save_accepts_after_successful_save(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QCloseEvent
        from PySide6.QtWidgets import QApplication, QMessageBox

        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        window = MainWindow(facade=EditorEngineFacade(engine_api=api))
        api.dirty = True
        window._confirm_close_with_unsaved_changes = lambda: QMessageBox.StandardButton.Save
        event = QCloseEvent()

        window.closeEvent(event)
        app.processEvents()

        self.assertTrue(event.isAccepted())
        self.assertEqual(api.save_calls, 1)
        self.assertFalse(api.dirty)
        window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_main_window_close_dirty_save_failure_blocks_close(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QCloseEvent
        from PySide6.QtWidgets import QApplication, QMessageBox

        from editor_qt.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        api = FakeEngineAPI()
        api.save_fails = True
        window = MainWindow(facade=EditorEngineFacade(engine_api=api))
        api.dirty = True
        window._confirm_close_with_unsaved_changes = lambda: QMessageBox.StandardButton.Save
        event = QCloseEvent()

        window.closeEvent(event)
        app.processEvents()

        self.assertFalse(event.isAccepted())
        self.assertEqual(api.save_calls, 1)
        self.assertIn("Scene save failed", window.console_panel.output.toPlainText())
        api.dirty = False
        window.close()

    @unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 optional dependency not installed")
    def test_project_panel_emits_scene_request_without_engine_access(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from editor_qt.panels.project_panel import ProjectPanel

        app = QApplication.instance() or QApplication([])
        panel = ProjectPanel()
        received: list[str] = []
        panel.scene_requested.connect(received.append)
        panel.set_project_data(
            project={"name": "Game", "root": "C:/game"},
            active_scene={},
            scenes=[{"name": "Main", "path": "levels/main.json"}],
            assets=[],
        )

        panel._on_scene_activated(panel.scenes_tree.topLevelItem(0))
        app.processEvents()

        self.assertEqual(received, ["levels/main.json"])


if __name__ == "__main__":
    unittest.main()
