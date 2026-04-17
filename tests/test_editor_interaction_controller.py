import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pyray as rl
from engine.app.editor_interaction_controller import EditorInteractionController
from engine.core.engine_state import EngineState
from engine.editor.cursor_manager import CursorVisualState
from engine.editor.editor_selection import EditorSelectionState
from engine.editor.editor_tools import EditorTool, PivotMode, TransformSpace
from engine.levels.component_registry import create_default_registry
from engine.project.project_service import ProjectService
from engine.scenes.scene_manager import SceneManager


class EditorInteractionControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "project"
        self.project_service = ProjectService(self.project_root)
        self.state = EngineState.EDIT
        self.scene_manager = Mock()
        self.scene_manager.get_active_scene_summary.return_value = {}
        self.selection_system = Mock()
        self.gizmo_system = Mock()
        self.gizmo_system.is_dragging = False
        self.gizmo_system.is_hot.return_value = False
        self.gizmo_system.consume_completed_drag.return_value = None
        self.ui_system = Mock()
        self.hierarchy_panel = Mock()
        self.hierarchy_panel.get_cursor_intent.return_value = CursorVisualState.DEFAULT
        self.inspector_system = Mock()
        self.inspector_system.get_cursor_intent.return_value = CursorVisualState.DEFAULT
        self.inspector_system.is_tilemap_tool_active.return_value = False
        self.inspector_system.handle_tilemap_scene_input.return_value = False
        self.inspector_system.get_tilemap_preview_snapshot.return_value = None
        self.history_manager = Mock()
        self.editor_selection = EditorSelectionState()
        self.layout = Mock()
        self.layout.project_panel = SimpleNamespace(
            dragging_file=None,
            project_service=self.project_service,
            asset_service=None,
        )
        self.layout.active_tool = EditorTool.MOVE
        self.layout.transform_space = TransformSpace.WORLD
        self.layout.pivot_mode = PivotMode.PIVOT
        self.layout.snap_settings = None
        self.layout.active_tab = "SCENE"
        self.layout.active_bottom_tab = "PROJECT"
        self.layout.flow_panel = Mock()
        self.layout.flow_panel.get_cursor_intent.return_value = CursorVisualState.DEFAULT
        self.layout.flow_workspace_panel = Mock()
        self.layout.flow_workspace_panel.get_cursor_intent.return_value = CursorVisualState.DEFAULT
        self.layout.get_scene_mouse_pos.return_value = rl.Vector2(10, 20)
        self.layout.get_scene_overlay_mouse_pos.return_value = rl.Vector2(5, 6)
        self.layout.is_mouse_in_scene_view.return_value = True
        self.layout.is_mouse_in_inspector.return_value = False
        self.layout.get_cursor_intent.return_value = CursorVisualState.DEFAULT
        self.layout.get_center_view_rect.return_value = rl.Rectangle(0, 0, 320, 180)
        self.layout.project_panel.get_cursor_intent = Mock(return_value=CursorVisualState.DEFAULT)

        self.controller = EditorInteractionController(
            get_state=lambda: self.state,
            get_editor_layout=lambda: self.layout,
            get_editor_selection=lambda: self.editor_selection,
            get_scene_manager=lambda: self.scene_manager,
            get_selection_system=lambda: self.selection_system,
            get_gizmo_system=lambda: self.gizmo_system,
            get_ui_system=lambda: self.ui_system,
            get_hierarchy_panel=lambda: self.hierarchy_panel,
            get_inspector_system=lambda: self.inspector_system,
            get_history_manager=lambda: self.history_manager,
            get_current_scene_viewport_size=lambda: (320.0, 180.0),
            get_current_viewport_size=lambda: (640.0, 360.0),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_handle_selection_and_gizmos_blocks_interaction_over_inspector(self) -> None:
        world = Mock()
        self.layout.is_mouse_in_inspector.return_value = True

        with patch("pyray.is_mouse_button_pressed", return_value=True):
            self.controller.handle_selection_and_gizmos(world)

        self.gizmo_system.update.assert_not_called()
        self.selection_system.update.assert_not_called()

    def test_handle_selection_and_gizmos_prioritizes_ui_hits(self) -> None:
        world = Mock()
        self.ui_system.find_topmost_entity_at_point.return_value = SimpleNamespace(name="PlayButton")

        with patch("pyray.is_mouse_button_pressed", return_value=True):
            self.controller.handle_selection_and_gizmos(world)

        self.ui_system.ensure_layout_cache.assert_called_once_with(world, (320.0, 180.0))
        self.selection_system.update.assert_not_called()
        self.scene_manager.set_selected_entity.assert_called_with("PlayButton")
        self.assertEqual(self.editor_selection.entity_name, "PlayButton")

    def test_handle_selection_and_gizmos_updates_shared_selection_state_from_selection_system(self) -> None:
        world = Mock()
        self.ui_system.should_render_scene_view_ui.return_value = False
        self.selection_system.update.return_value = "Hero"

        with patch("pyray.is_mouse_button_pressed", return_value=True):
            self.controller.handle_selection_and_gizmos(world)

        self.scene_manager.set_selected_entity.assert_called_with("Hero")
        self.assertEqual(self.editor_selection.entity_name, "Hero")

    def test_handle_selection_and_gizmos_ignores_hidden_scene_ui(self) -> None:
        world = Mock()
        self.ui_system.should_render_scene_view_ui.return_value = False

        with patch("pyray.is_mouse_button_pressed", return_value=True):
            self.controller.handle_selection_and_gizmos(world)

        self.ui_system.ensure_layout_cache.assert_not_called()
        self.ui_system.find_topmost_entity_at_point.assert_not_called()
        self.selection_system.update.assert_called_once()
        selected_world, mouse_world = self.selection_system.update.call_args.args
        self.assertIs(selected_world, world)
        self.assertEqual(float(mouse_world.x), 10.0)
        self.assertEqual(float(mouse_world.y), 20.0)
        self.assertIsNone(self.gizmo_system.update.call_args.kwargs.get("ui_system"))

    def test_handle_selection_and_gizmos_marks_transient_preview_and_commits_completed_drag(self) -> None:
        world = Mock()
        drag = SimpleNamespace(
            label="Move Entity",
            entity_name="Player",
            before_state={"x": 0},
            after_state={"x": 10},
            component_name="Transform",
        )
        self.gizmo_system.is_dragging = True
        self.gizmo_system.consume_completed_drag.return_value = drag

        with patch("pyray.is_mouse_button_pressed", return_value=False), patch.object(
            self.controller,
            "commit_gizmo_drag",
        ) as commit:
            self.controller.handle_selection_and_gizmos(world)

        self.scene_manager.mark_edit_world_dirty.assert_called_once_with(reason="transient_preview")
        commit.assert_called_once_with(drag)

    def test_commit_gizmo_drag_uses_scene_manager_canonical_transform_route(self) -> None:
        drag = SimpleNamespace(
            label="Move Entity",
            entity_name="Player",
            before_state={"x": 0.0, "y": 0.0},
            after_state={"x": 10.0, "y": 12.0},
            component_name="Transform",
        )
        self.scene_manager.active_scene_key = "scene-a"

        self.controller.commit_gizmo_drag(drag)

        self.scene_manager.sync_from_edit_world.assert_not_called()
        self.scene_manager.apply_transform_state.assert_called_once_with(
            "Player",
            {"x": 10.0, "y": 12.0},
            key_or_path="scene-a",
            record_history=True,
            label="Move Entity",
        )

    def test_handle_selection_and_gizmos_delegates_to_tilemap_tool_and_skips_selection(self) -> None:
        world = Mock()
        self.inspector_system.is_tilemap_tool_active.return_value = True
        self.inspector_system.get_tilemap_preview_snapshot.return_value = {"status": "ok"}

        with patch("pyray.is_mouse_button_pressed", return_value=True), patch("pyray.is_mouse_button_down", return_value=True), patch(
            "pyray.is_mouse_button_released",
            return_value=False,
        ):
            self.controller.handle_selection_and_gizmos(world)

        self.inspector_system.handle_tilemap_scene_input.assert_called_once()
        self.gizmo_system.set_tilemap_preview.assert_called_once_with({"status": "ok"})
        self.gizmo_system.update.assert_not_called()
        self.selection_system.update.assert_not_called()

    def test_handle_selection_and_gizmos_clears_tilemap_preview_when_tool_inactive(self) -> None:
        world = Mock()
        self.inspector_system.is_tilemap_tool_active.return_value = False

        with patch("pyray.is_mouse_button_pressed", return_value=False):
            self.controller.handle_selection_and_gizmos(world)

        self.gizmo_system.set_tilemap_preview.assert_called_once_with(None)

    def test_resolve_cursor_state_marks_scene_interactive_when_tilemap_tool_is_active(self) -> None:
        world = Mock()
        self.inspector_system.is_tilemap_tool_active.return_value = True
        self.ui_system.should_render_scene_view_ui.return_value = False
        self.ui_system.get_cursor_intent.return_value = CursorVisualState.DEFAULT

        with patch("pyray.get_mouse_position", return_value=rl.Vector2(12, 14)), patch(
            "pyray.check_collision_point_rec",
            return_value=True,
        ):
            state = self.controller.resolve_cursor_state(world)

        self.assertEqual(state, CursorVisualState.INTERACTIVE)

    def test_resolve_cursor_state_returns_interactive_when_ui_requests_it(self) -> None:
        world = Mock()
        self.state = EngineState.PLAY
        self.layout.active_tab = "GAME"
        self.ui_system.get_cursor_intent.return_value = CursorVisualState.INTERACTIVE

        with patch("pyray.get_mouse_position", return_value=rl.Vector2(12, 14)), patch(
            "pyray.check_collision_point_rec",
            return_value=True,
        ):
            state = self.controller.resolve_cursor_state(world)

        self.assertEqual(state, CursorVisualState.INTERACTIVE)
        self.ui_system.get_cursor_intent.assert_called_once_with(
            world,
            (640.0, 360.0),
            5.0,
            6.0,
            allow_interaction=True,
        )

    def test_resolve_cursor_state_ignores_ui_runtime_intent_while_editing_scene(self) -> None:
        world = Mock()
        self.state = EngineState.EDIT
        self.layout.active_tab = "SCENE"
        self.ui_system.get_cursor_intent.side_effect = (
            lambda *_args, **kwargs: CursorVisualState.INTERACTIVE
            if kwargs.get("allow_interaction")
            else CursorVisualState.DEFAULT
        )

        with patch("pyray.get_mouse_position", return_value=rl.Vector2(12, 14)), patch(
            "pyray.check_collision_point_rec",
            return_value=True,
        ):
            state = self.controller.resolve_cursor_state(world)

        self.assertEqual(state, CursorVisualState.DEFAULT)
        self.ui_system.get_cursor_intent.assert_called_once_with(
            world,
            (320.0, 180.0),
            5.0,
            6.0,
            allow_interaction=False,
        )

    def test_resolve_cursor_state_reads_flow_panel_when_flow_tab_is_active(self) -> None:
        self.layout.active_bottom_tab = "FLOW"
        self.layout.flow_panel.get_cursor_intent.return_value = CursorVisualState.INTERACTIVE

        with patch("pyray.get_mouse_position", return_value=rl.Vector2(12, 14)), patch(
            "pyray.check_collision_point_rec",
            return_value=False,
        ):
            state = self.controller.resolve_cursor_state(None)

        self.assertEqual(state, CursorVisualState.INTERACTIVE)
        self.layout.flow_panel.get_cursor_intent.assert_called_once()

    def test_resolve_cursor_state_reads_flow_workspace_panel_when_center_flow_is_active(self) -> None:
        self.layout.active_tab = "FLOW"
        self.layout.flow_workspace_panel.get_cursor_intent.return_value = CursorVisualState.INTERACTIVE

        with patch("pyray.get_mouse_position", return_value=rl.Vector2(12, 14)), patch(
            "pyray.check_collision_point_rec",
            return_value=False,
        ):
            state = self.controller.resolve_cursor_state(None)

        self.assertEqual(state, CursorVisualState.INTERACTIVE)
        self.layout.flow_workspace_panel.get_cursor_intent.assert_called_once()

    def test_handle_scene_view_drag_drop_creates_sprite_entity_via_scene_manager(self) -> None:
        world = Mock()
        world.get_entity_by_name.return_value = None
        world.selected_entity_name = None
        texture_path = self.project_root / "assets" / "player.png"
        texture_path.parent.mkdir(parents=True, exist_ok=True)
        texture_path.write_bytes(b"")
        self.layout.project_panel.dragging_file = texture_path.as_posix()
        self.scene_manager.create_entity.return_value = True

        with patch("pyray.is_mouse_button_released", return_value=True):
            self.controller.handle_scene_view_drag_drop(world)

        self.scene_manager.create_entity.assert_called_once()
        name, payload = self.scene_manager.create_entity.call_args.args
        self.assertEqual(name, "player")
        self.assertEqual(payload["Transform"]["x"], 10)
        self.assertEqual(payload["Transform"]["y"], 20)
        self.assertEqual(payload["Sprite"]["texture_path"], "assets/player.png")
        self.scene_manager.set_selected_entity.assert_called_with("player")

    def test_handle_scene_view_drag_drop_instantiates_prefab_with_project_relative_locator_when_scene_has_no_path(self) -> None:
        world = Mock()

        def _get_entity(name: str):
            if name == "enemy":
                return object()
            return None

        world.get_entity_by_name.side_effect = _get_entity
        prefab_path = self.project_root / "prefabs" / "enemy.prefab"
        prefab_path.parent.mkdir(parents=True, exist_ok=True)
        prefab_path.write_text("{}", encoding="utf-8")
        self.layout.project_panel.dragging_file = prefab_path.as_posix()
        self.scene_manager.instantiate_prefab.return_value = True

        with patch("pyray.is_mouse_button_released", return_value=True), patch(
            "engine.assets.prefab.PrefabManager.load_prefab_data",
            return_value={"root_name": "EnemyRoot"},
        ):
            self.controller.handle_scene_view_drag_drop(world)

        self.scene_manager.instantiate_prefab.assert_called_once()
        unique_name = self.scene_manager.instantiate_prefab.call_args.args[0]
        self.assertEqual(unique_name, "enemy_1")
        self.assertEqual(
            self.scene_manager.instantiate_prefab.call_args.kwargs["prefab_path"],
            "prefabs/enemy.prefab",
        )
        self.assertEqual(
            self.scene_manager.instantiate_prefab.call_args.kwargs["overrides"],
            {"": {"components": {"Transform": {"x": 10, "y": 20}}}},
        )
        self.assertEqual(self.scene_manager.instantiate_prefab.call_args.kwargs["root_name"], "EnemyRoot")
        self.scene_manager.set_selected_entity.assert_called_once_with("enemy_1")

    def test_handle_scene_view_drag_drop_instantiates_prefab_with_scene_relative_locator_when_scene_is_saved(self) -> None:
        world = Mock()
        world.get_entity_by_name.return_value = None
        prefab_path = self.project_root / "prefabs" / "enemy.prefab"
        scene_path = self.project_root / "levels" / "main_scene.json"
        prefab_path.parent.mkdir(parents=True, exist_ok=True)
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        prefab_path.write_text("{}", encoding="utf-8")
        self.layout.project_panel.dragging_file = prefab_path.as_posix()
        self.scene_manager.get_active_scene_summary.return_value = {"path": scene_path.as_posix()}
        self.scene_manager.instantiate_prefab.return_value = True

        with patch("pyray.is_mouse_button_released", return_value=True), patch(
            "engine.assets.prefab.PrefabManager.load_prefab_data",
            return_value={"root_name": "EnemyRoot"},
        ) as load_prefab:
            self.controller.handle_scene_view_drag_drop(world)

        load_prefab.assert_called_once_with(prefab_path.as_posix())
        self.assertEqual(
            self.scene_manager.instantiate_prefab.call_args.kwargs["prefab_path"],
            "../prefabs/enemy.prefab",
        )

    def test_drag_drop_save_load_persists_portable_sprite_and_prefab_locators(self) -> None:
        scene_manager = SceneManager(create_default_registry())
        scene_path = self.project_root / "levels" / "drag_drop_scene.json"
        texture_path = self.project_root / "assets" / "player.png"
        prefab_path = self.project_root / "prefabs" / "enemy.prefab"
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        texture_path.parent.mkdir(parents=True, exist_ok=True)
        prefab_path.parent.mkdir(parents=True, exist_ok=True)
        texture_path.write_bytes(b"")
        prefab_path.write_text(
            json.dumps(
                {
                    "root_name": "EnemyRoot",
                    "entities": [
                        {
                            "name": "EnemyRoot",
                            "active": True,
                            "tag": "Untagged",
                            "layer": "Default",
                            "components": {
                                "Transform": {
                                    "enabled": True,
                                    "x": 0.0,
                                    "y": 0.0,
                                    "rotation": 0.0,
                                    "scale_x": 1.0,
                                    "scale_y": 1.0,
                                }
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        scene_manager.load_scene(
            {
                "name": "DragDropScene",
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
            source_path=scene_path.as_posix(),
        )

        layout = Mock()
        layout.project_panel = SimpleNamespace(
            dragging_file=texture_path.as_posix(),
            project_service=self.project_service,
            asset_service=None,
        )
        layout.get_scene_mouse_pos.return_value = rl.Vector2(10, 20)
        layout.is_mouse_in_scene_view.return_value = True

        controller = EditorInteractionController(
            get_state=lambda: EngineState.EDIT,
            get_editor_layout=lambda: layout,
            get_editor_selection=lambda: EditorSelectionState(),
            get_scene_manager=lambda: scene_manager,
            get_selection_system=lambda: Mock(),
            get_gizmo_system=lambda: Mock(),
            get_ui_system=lambda: Mock(),
            get_hierarchy_panel=lambda: Mock(),
            get_inspector_system=lambda: Mock(),
            get_history_manager=lambda: Mock(),
            get_current_scene_viewport_size=lambda: (320.0, 180.0),
            get_current_viewport_size=lambda: (640.0, 360.0),
        )

        with patch("pyray.is_mouse_button_released", return_value=True):
            controller.handle_scene_view_drag_drop(scene_manager.get_edit_world())

        layout.project_panel.dragging_file = prefab_path.as_posix()
        with patch("pyray.is_mouse_button_released", return_value=True):
            controller.handle_scene_view_drag_drop(scene_manager.get_edit_world())

        self.assertTrue(scene_manager.save_scene_to_file(scene_path.as_posix()))
        persisted = json.loads(scene_path.read_text(encoding="utf-8"))
        raw_json = scene_path.read_text(encoding="utf-8")
        sprite_entity = next(entity for entity in persisted["entities"] if entity["name"] == "player")
        prefab_entity = next(entity for entity in persisted["entities"] if entity["name"] == "enemy")

        self.assertEqual(sprite_entity["components"]["Sprite"]["texture_path"], "assets/player.png")
        self.assertFalse(os.path.isabs(sprite_entity["components"]["Sprite"]["texture_path"]))
        self.assertEqual(prefab_entity["prefab_instance"]["prefab_path"], "../prefabs/enemy.prefab")
        self.assertFalse(os.path.isabs(prefab_entity["prefab_instance"]["prefab_path"]))
        self.assertNotIn(self.project_root.as_posix(), raw_json)

        reloaded = SceneManager(create_default_registry())
        self.assertIsNotNone(reloaded.load_scene_from_file(scene_path.as_posix()))
        reloaded_sprite = reloaded.current_scene.find_entity("player")
        reloaded_prefab = reloaded.current_scene.find_entity("enemy")

        self.assertEqual(reloaded_sprite["components"]["Sprite"]["texture_path"], "assets/player.png")
        self.assertEqual(reloaded_prefab["prefab_instance"]["prefab_path"], "../prefabs/enemy.prefab")


if __name__ == "__main__":
    unittest.main()
