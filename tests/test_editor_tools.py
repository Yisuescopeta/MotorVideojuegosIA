import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pyray as rl

from engine.components.recttransform import RectTransform
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.core.game import Game
from engine.ecs.entity import Entity
from engine.editor.cursor_manager import CursorVisualState
from engine.editor.editor_layout import EditorLayout
from engine.editor.editor_tools import EditorTool, PivotMode, TransformSpace
from engine.editor.gizmo_system import GizmoSystem
from engine.levels.component_registry import create_default_registry
from engine.project.project_service import ProjectService
from engine.scenes.scene_manager import SceneManager


class EditorLayoutToolStateTests(unittest.TestCase):
    def test_editor_layout_round_trips_tool_preferences(self) -> None:
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            layout = EditorLayout(1280, 720)

        layout.apply_editor_preferences(
            {
                "editor_active_tool": "Transform",
                "editor_transform_space": "local",
                "editor_pivot_mode": "center",
                "editor_snap_move_step": 12.5,
                "editor_snap_rotate_step": 30.0,
                "editor_snap_scale_step": 0.25,
            }
        )

        self.assertEqual(layout.active_tool, EditorTool.TRANSFORM)
        self.assertEqual(layout.transform_space, TransformSpace.LOCAL)
        self.assertEqual(layout.pivot_mode, PivotMode.CENTER)
        self.assertEqual(layout.snap_settings.move_step, 12.5)
        self.assertTrue(layout.export_editor_preferences()["editor_pivot_mode"] == "center")
        self.assertFalse(layout.consume_editor_preferences_dirty())

        layout.set_active_tool(EditorTool.ROTATE)
        self.assertTrue(layout.consume_editor_preferences_dirty())
        self.assertEqual(layout.current_tool, "Rotate")

    def test_view_tabs_live_in_center_header_and_leave_room_for_scene_tabs(self) -> None:
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            layout = EditorLayout(1280, 720)

        self.assertGreaterEqual(layout.tab_scene_rect.x, layout.center_rect.x)
        self.assertGreater(layout.tab_game_rect.x, layout.tab_scene_rect.x)
        self.assertGreater(layout.tab_animator_rect.x, layout.tab_game_rect.x)
        self.assertLessEqual(
            layout.tab_animator_rect.x + layout.tab_animator_rect.width,
            layout.center_rect.x + layout.center_rect.width,
        )

    def test_scene_render_textures_match_visible_viewport_height(self) -> None:
        resize_calls: list[tuple[int, int]] = []

        def _capture_resize(self, width: int, height: int) -> None:
            resize_calls.append((width, height))

        with patch.object(EditorLayout, "_resize_render_textures", _capture_resize):
            layout = EditorLayout(1280, 720)

        self.assertTrue(resize_calls)
        self.assertEqual(
            resize_calls[-1],
            (int(layout.get_center_view_rect().width), int(layout.get_center_view_rect().height)),
        )

    def test_editor_camera_offset_tracks_visible_scene_view_center(self) -> None:
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            layout = EditorLayout(1280, 720)

        view_rect = layout.get_center_view_rect()
        self.assertEqual(layout.editor_camera.offset.x, view_rect.width / 2)
        self.assertEqual(layout.editor_camera.offset.y, view_rect.height / 2)

        layout.update_layout(1440, 900, update_texture=False)
        resized_view_rect = layout.get_center_view_rect()
        self.assertEqual(layout.editor_camera.offset.x, resized_view_rect.width / 2)
        self.assertEqual(layout.editor_camera.offset.y, resized_view_rect.height / 2)

    def test_scene_mouse_world_pos_uses_visible_viewport_origin(self) -> None:
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            layout = EditorLayout(1280, 720)

        layout.editor_camera.target = rl.Vector2(25.0, -10.0)
        layout.editor_camera.zoom = 1.0
        view_rect = layout.get_center_view_rect()
        screen_pos = rl.Vector2(view_rect.x + view_rect.width / 2, view_rect.y + view_rect.height / 2)

        with patch("pyray.get_mouse_position", return_value=screen_pos):
            world_pos = layout.get_scene_mouse_pos()

        self.assertAlmostEqual(world_pos.x, 25.0)
        self.assertAlmostEqual(world_pos.y, -10.0)

    def test_cursor_intent_returns_text_for_manual_inputs(self) -> None:
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            layout = EditorLayout(1280, 720)

        shared_rect = rl.Rectangle(120, 80, 180, 32)
        layout.launcher_search_rect = shared_rect
        layout.tab_scene_rect = shared_rect

        with patch("pyray.get_mouse_position", return_value=rl.Vector2(140, 96)):
            self.assertEqual(layout.get_cursor_intent(), CursorVisualState.TEXT)

    def test_cursor_intent_returns_interactive_for_tabs_and_splitters(self) -> None:
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            layout = EditorLayout(1280, 720)

        tab_mouse = rl.Vector2(layout.tab_scene_rect.x + 4, layout.tab_scene_rect.y + 4)
        splitter_mouse = rl.Vector2(layout.splitter_left_rect.x + 1, layout.splitter_left_rect.y + 8)

        with patch("pyray.get_mouse_position", return_value=tab_mouse):
            self.assertEqual(layout.get_cursor_intent(), CursorVisualState.INTERACTIVE)
        with patch("pyray.get_mouse_position", return_value=splitter_mouse):
            self.assertEqual(layout.get_cursor_intent(), CursorVisualState.INTERACTIVE)


class SceneViewFocusRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.global_state_dir = self.workspace / "global_state"
        self.project_root = self.workspace / "FocusProject"
        self.project_service = ProjectService(self.project_root, global_state_dir=self.global_state_dir)
        self.scene_path = self.project_root / "levels" / "intro.json"
        self.scene_path.write_text(
            '{"name":"Intro","entities":[],"rules":[],"feature_metadata":{}}',
            encoding="utf-8",
        )

        self.game = Game()
        self.game.set_scene_manager(SceneManager(create_default_registry()))
        self.game.set_project_service(self.project_service)
        with patch.object(EditorLayout, "_resize_render_textures", lambda *args, **kwargs: None):
            self.game.editor_layout = EditorLayout(1280, 720)
        self.game.set_project_service(self.project_service)
        self.game.set_scene_manager(self.game._scene_manager)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_open_project_forces_scene_view_active(self) -> None:
        self.game.editor_layout.active_tab = "GAME"

        result = self.game.open_project(self.project_root.as_posix())

        self.assertTrue(result)
        self.assertEqual(self.game.editor_layout.active_tab, "SCENE")

    def test_new_scene_request_forces_scene_view_active(self) -> None:
        self.game.editor_layout.active_tab = "ANIMATOR"
        self.game.editor_layout.request_new_scene = True

        self.game._process_ui_requests()

        self.assertEqual(self.game.editor_layout.active_tab, "SCENE")

    def test_autosave_preserves_live_scene_selection_and_camera(self) -> None:
        self.game._scene_manager.load_scene(
            {
                "name": "AutosaveProbe",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 32.0,
                                "y": 48.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            }
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            },
            source_path=self.scene_path.as_posix(),
        )
        self.game.editor_layout.editor_camera.target = rl.Vector2(125.0, -75.0)
        self.game.editor_layout.editor_camera.zoom = 1.75
        self.game._scene_manager.set_selected_entity("Player")
        self.game._scene_manager.set_scene_view_state(
            self.game._scene_manager.active_scene_key,
            {
                "selected_entity": None,
                "camera_target": {"x": 0.0, "y": 0.0},
                "camera_zoom": 1.0,
            },
        )

        entry = self.game._scene_manager._resolve_entry(self.game._scene_manager.active_scene_key)  # type: ignore[attr-defined]
        entry.dirty = True

        self.game._autosave_dirty_scenes()

        self.assertEqual(self.game._scene_manager.get_edit_world().selected_entity_name, "Player")
        self.assertEqual(self.game.editor_layout.editor_camera.target.x, 125.0)
        self.assertEqual(self.game.editor_layout.editor_camera.target.y, -75.0)
        self.assertEqual(self.game.editor_layout.editor_camera.zoom, 1.75)


class GameUiAuthoringRequestTests(unittest.TestCase):
    def _make_layout(self) -> Mock:
        layout = Mock()
        layout.project_panel = Mock()
        layout.project_panel.request_open_sprite_editor_for = None
        layout.project_panel.request_open_scene_for = None
        layout.request_create_canvas = False
        layout.request_create_ui_text = False
        layout.request_create_ui_button = False
        return layout

    def _stub_ui_request_controllers(self, game: Game) -> None:
        game._scene_workflow_controller.handle_scene_tab_requests = Mock()
        game._scene_workflow_controller.handle_scene_ui_requests = Mock()
        game._project_workspace_controller.handle_project_launcher_requests = Mock(return_value=False)
        game._project_workspace_controller.handle_project_switch_requests = Mock()

    def test_process_ui_requests_creates_canvas_entity(self) -> None:
        game = Game()
        game.editor_layout = self._make_layout()
        game.editor_layout.request_create_canvas = True
        game._scene_manager = Mock()
        game._scene_manager.active_world = None
        self._stub_ui_request_controllers(game)

        game._process_ui_requests()

        game._scene_manager.create_entity.assert_called_once()
        entity_name = game._scene_manager.create_entity.call_args.args[0]
        components = game._scene_manager.create_entity.call_args.kwargs["components"]
        self.assertEqual(entity_name, "Canvas")
        self.assertIn("Canvas", components)
        self.assertIn("RectTransform", components)

    def test_process_ui_requests_uses_selected_entity_as_default_ui_parent(self) -> None:
        game = Game()
        game.editor_layout = self._make_layout()
        game.editor_layout.request_create_ui_text = True
        active_world = Mock()
        active_world.selected_entity_name = "HudRoot"
        game._scene_manager = Mock()
        game._scene_manager.active_world = active_world
        self._stub_ui_request_controllers(game)

        game._process_ui_requests()

        game._scene_manager.create_child_entity.assert_called_once()
        parent_name, entity_name = game._scene_manager.create_child_entity.call_args.args[:2]
        components = game._scene_manager.create_child_entity.call_args.kwargs["components"]
        self.assertEqual(parent_name, "HudRoot")
        self.assertEqual(entity_name, "Text")
        self.assertIn("UIText", components)

    def test_process_ui_requests_falls_back_to_first_canvas_for_button_parent(self) -> None:
        game = Game()
        game.editor_layout = self._make_layout()
        game.editor_layout.request_create_ui_button = True

        non_canvas_entity = Mock()
        non_canvas_entity.has_component.return_value = False
        canvas_entity = Mock()
        canvas_entity.name = "MainCanvas"
        canvas_entity.has_component.return_value = True

        active_world = Mock()
        active_world.selected_entity_name = None
        active_world.get_all_entities.return_value = [non_canvas_entity, canvas_entity]

        game._scene_manager = Mock()
        game._scene_manager.active_world = active_world
        self._stub_ui_request_controllers(game)

        game._process_ui_requests()

        game._scene_manager.create_child_entity.assert_called_once()
        parent_name, entity_name = game._scene_manager.create_child_entity.call_args.args[:2]
        components = game._scene_manager.create_child_entity.call_args.kwargs["components"]
        self.assertEqual(parent_name, "MainCanvas")
        self.assertEqual(entity_name, "Button")
        self.assertIn("UIButton", components)


class GameCursorRenderTests(unittest.TestCase):
    def test_render_frame_draws_custom_cursor_after_layout(self) -> None:
        game = Game()
        layout = Mock()
        layout.active_tab = "TEST"
        layout.draw_layout = Mock()
        layout.get_cursor_intent = Mock(return_value=CursorVisualState.INTERACTIVE)
        game.editor_layout = layout
        game.hierarchy_panel = None
        game.animator_panel = None
        game._inspector_system = None
        game._draw_debug_info = Mock()
        game._draw_performance_overlay = Mock()
        game._cursor_renderer.render = Mock()

        with patch("pyray.begin_drawing"), patch("pyray.end_drawing"), patch("pyray.clear_background"), patch(
            "pyray.get_mouse_position", return_value=rl.Vector2(64, 48)
        ):
            game._render_frame(Mock())

        game._cursor_renderer.render.assert_called_once()
        _, state = game._cursor_renderer.render.call_args.args
        self.assertEqual(state, CursorVisualState.INTERACTIVE)

    def test_cleanup_restores_system_cursor(self) -> None:
        game = Game()
        game.terminal_panel = Mock()
        game.animator_panel = Mock()
        game.sprite_editor_modal = Mock()
        game._cursor_renderer = Mock()

        with patch("pyray.close_window"):
            game._cleanup()

        game._cursor_renderer.show_system_cursor.assert_called_once()


class GizmoSystemMathTests(unittest.TestCase):
    def test_local_axes_follow_transform_rotation(self) -> None:
        gizmo = GizmoSystem()
        gizmo.transform_space = TransformSpace.LOCAL
        transform = Transform(rotation=90.0)

        x_axis, y_axis = gizmo._get_axes(transform)

        self.assertAlmostEqual(x_axis.x, 0.0, places=4)
        self.assertAlmostEqual(x_axis.y, -1.0, places=4)
        self.assertAlmostEqual(y_axis.x, 1.0, places=4)
        self.assertAlmostEqual(y_axis.y, 0.0, places=4)

    def test_center_pivot_uses_sprite_bounds(self) -> None:
        gizmo = GizmoSystem()
        entity = Entity("Player")
        transform = Transform(100.0, 50.0)
        sprite = Sprite(width=40, height=20, origin_x=0.0, origin_y=1.0)
        entity.add_component(transform)
        entity.add_component(sprite)

        center_x, center_y = gizmo._get_gizmo_origin(entity, transform, PivotMode.CENTER)

        self.assertEqual((center_x, center_y), (120.0, 60.0))

    def test_free_move_constrain_locks_to_dominant_axis(self) -> None:
        gizmo = GizmoSystem()
        move = rl.Vector2(20.0, 6.0)
        x_axis = rl.Vector2(1.0, 0.0)
        y_axis = rl.Vector2(0.0, -1.0)

        constrained = gizmo._constrain_move(move, x_axis, y_axis)

        self.assertEqual((constrained.x, constrained.y), (20.0, 0.0))
        self.assertEqual(gizmo._snap(43.0, 10.0), 40.0)
        self.assertAlmostEqual(gizmo._snap(28.0, 15.0), 30.0)

    def test_rect_transform_selection_resolves_transform_tool_to_rect_tool(self) -> None:
        gizmo = GizmoSystem()
        entity = Entity("Button")
        entity.add_component(RectTransform())
        gizmo.current_tool = EditorTool.TRANSFORM

        self.assertEqual(gizmo._resolve_effective_tool(entity), EditorTool.RECT)

    def test_visual_rect_drag_updates_rect_transform_fields(self) -> None:
        gizmo = GizmoSystem()
        rect_transform = RectTransform(
            anchor_min_x=0.5,
            anchor_min_y=0.5,
            anchor_max_x=0.5,
            anchor_max_y=0.5,
            pivot_x=0.5,
            pivot_y=0.5,
            anchored_x=0.0,
            anchored_y=0.0,
            width=280.0,
            height=84.0,
        )
        parent_rect = {"x": 0.0, "y": 0.0, "width": 800.0, "height": 600.0, "scale_x": 1.0, "scale_y": 1.0}

        gizmo._apply_visual_rect_to_rect_transform(rect_transform, parent_rect, 300.0, 250.0, 620.0, 370.0, False)

        self.assertEqual(rect_transform.anchored_x, 60.0)
        self.assertEqual(rect_transform.anchored_y, 10.0)
        self.assertEqual(rect_transform.width, 320.0)
        self.assertEqual(rect_transform.height, 120.0)

    def test_transform_tool_renders_translate_rotate_and_scale_handles(self) -> None:
        gizmo = GizmoSystem()
        world = SceneManager(create_default_registry()).load_scene(
            {
                "name": "GizmoProbe",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 32.0,
                                "y": 64.0,
                                "rotation": 15.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            }
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )
        world.selected_entity_name = "Player"
        gizmo._draw_translate_gizmo = Mock()
        gizmo._draw_rotate_gizmo = Mock()
        gizmo._draw_scale_gizmo = Mock()

        gizmo.render(world, EditorTool.TRANSFORM, TransformSpace.WORLD, PivotMode.PIVOT)

        gizmo._draw_translate_gizmo.assert_called_once()
        gizmo._draw_rotate_gizmo.assert_called_once()
        gizmo._draw_scale_gizmo.assert_called_once()


class SceneManagerTransformStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene_manager = SceneManager(create_default_registry())
        self.scene_manager.load_scene(
            {
                "name": "Tool Probe",
                "entities": [
                    {
                        "name": "Player",
                        "active": True,
                        "tag": "Untagged",
                        "layer": "Default",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 10.0,
                                "y": 20.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            }
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

    def test_apply_transform_state_updates_edit_world_and_scene(self) -> None:
        applied = self.scene_manager.apply_transform_state(
            "Player",
            {"x": 45.0, "y": 64.0, "rotation": 90.0, "scale_x": 2.0, "scale_y": 0.5},
        )

        self.assertTrue(applied)
        edit_world = self.scene_manager.get_edit_world()
        player = edit_world.get_entity_by_name("Player")
        transform = player.get_component(Transform)
        self.assertEqual(transform.local_x, 45.0)
        self.assertEqual(transform.local_y, 64.0)
        self.assertEqual(transform.local_rotation, 90.0)
        entity_data = self.scene_manager.find_entity_data("Player")
        self.assertEqual(entity_data["components"]["Transform"]["x"], 45.0)
        self.assertEqual(entity_data["components"]["Transform"]["scale_y"], 0.5)

    def test_apply_rect_transform_state_updates_edit_world_and_scene(self) -> None:
        self.scene_manager.create_entity(
            "Button",
            components={
                "RectTransform": {
                    "enabled": True,
                    "anchor_min_x": 0.5,
                    "anchor_min_y": 0.5,
                    "anchor_max_x": 0.5,
                    "anchor_max_y": 0.5,
                    "pivot_x": 0.5,
                    "pivot_y": 0.5,
                    "anchored_x": 0.0,
                    "anchored_y": 0.0,
                    "width": 200.0,
                    "height": 80.0,
                    "rotation": 0.0,
                    "scale_x": 1.0,
                    "scale_y": 1.0,
                }
            },
        )

        applied = self.scene_manager.apply_rect_transform_state(
            "Button",
            {"anchored_x": 32.0, "anchored_y": -16.0, "width": 240.0, "height": 96.0, "rotation": 15.0, "scale_x": 1.2, "scale_y": 0.8},
        )

        self.assertTrue(applied)
        edit_world = self.scene_manager.get_edit_world()
        button = edit_world.get_entity_by_name("Button")
        rect_transform = button.get_component(RectTransform)
        self.assertEqual(rect_transform.anchored_x, 32.0)
        self.assertEqual(rect_transform.height, 96.0)
        entity_data = self.scene_manager.find_entity_data("Button")
        self.assertEqual(entity_data["components"]["RectTransform"]["rotation"], 15.0)
        self.assertEqual(entity_data["components"]["RectTransform"]["scale_x"], 1.2)


if __name__ == "__main__":
    unittest.main()
