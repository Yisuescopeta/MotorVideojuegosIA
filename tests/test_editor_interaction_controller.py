import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pyray as rl

from engine.app.editor_interaction_controller import EditorInteractionController
from engine.core.engine_state import EngineState
from engine.editor.cursor_manager import CursorVisualState
from engine.editor.editor_tools import EditorTool, PivotMode, TransformSpace


class EditorInteractionControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = EngineState.EDIT
        self.scene_manager = Mock()
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
        self.history_manager = Mock()
        self.layout = Mock()
        self.layout.project_panel = SimpleNamespace(dragging_file=None)
        self.layout.active_tool = EditorTool.MOVE
        self.layout.transform_space = TransformSpace.WORLD
        self.layout.pivot_mode = PivotMode.PIVOT
        self.layout.snap_settings = None
        self.layout.active_tab = "SCENE"
        self.layout.active_bottom_tab = "PROJECT"
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

    def test_handle_selection_and_gizmos_marks_dirty_and_commits_completed_drag(self) -> None:
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

        self.scene_manager.mark_edit_world_dirty.assert_called_once_with()
        commit.assert_called_once_with(drag)

    def test_resolve_cursor_state_returns_interactive_when_ui_requests_it(self) -> None:
        world = Mock()
        self.ui_system.get_cursor_intent.return_value = CursorVisualState.INTERACTIVE

        with patch("pyray.get_mouse_position", return_value=rl.Vector2(12, 14)), patch(
            "pyray.check_collision_point_rec",
            return_value=True,
        ):
            state = self.controller.resolve_cursor_state(world)

        self.assertEqual(state, CursorVisualState.INTERACTIVE)
        self.ui_system.get_cursor_intent.assert_called_once_with(world, (320.0, 180.0), 5.0, 6.0)

    def test_handle_scene_view_drag_drop_creates_sprite_entity_via_scene_manager(self) -> None:
        world = Mock()
        world.get_entity_by_name.return_value = None
        world.selected_entity_name = None
        self.layout.project_panel.dragging_file = "C:/assets/player.png"
        self.scene_manager.create_entity.return_value = True

        with patch("pyray.is_mouse_button_released", return_value=True):
            self.controller.handle_scene_view_drag_drop(world)

        self.scene_manager.create_entity.assert_called_once()
        name, payload = self.scene_manager.create_entity.call_args.args
        self.assertEqual(name, "player")
        self.assertEqual(payload["Transform"]["x"], 10)
        self.assertEqual(payload["Transform"]["y"], 20)
        self.assertEqual(payload["Sprite"]["texture_path"], "C:/assets/player.png")
        self.assertEqual(world.selected_entity_name, "player")

    def test_handle_scene_view_drag_drop_instantiates_prefab_with_unique_name(self) -> None:
        world = Mock()

        def _get_entity(name: str):
            if name == "enemy":
                return object()
            return None

        world.get_entity_by_name.side_effect = _get_entity
        self.layout.project_panel.dragging_file = "C:/assets/enemy.prefab"
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
            self.scene_manager.instantiate_prefab.call_args.kwargs["overrides"],
            {"": {"components": {"Transform": {"x": 10, "y": 20}}}},
        )
        self.assertEqual(self.scene_manager.instantiate_prefab.call_args.kwargs["root_name"], "EnemyRoot")
        self.scene_manager.set_selected_entity.assert_called_once_with("enemy_1")


if __name__ == "__main__":
    unittest.main()
