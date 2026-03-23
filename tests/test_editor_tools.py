import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.getcwd())

import pyray as rl

from engine.components.recttransform import RectTransform
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.core.game import Game
from engine.ecs.entity import Entity
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
