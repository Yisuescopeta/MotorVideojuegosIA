import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cli.script_executor import ScriptExecutor
from engine.api import EngineAPI
from engine.components.recttransform import RectTransform
from engine.components.transform import Transform


class InspectorCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project_root = self.workspace / "project"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.global_state_dir = self.workspace / "global_state"
        demo_level = Path(__file__).resolve().parents[1] / "levels" / "demo_level.json"
        target_level = self.project_root / "levels" / "demo_level.json"
        target_level.parent.mkdir(parents=True, exist_ok=True)
        target_level.write_text(demo_level.read_text(encoding="utf-8"), encoding="utf-8")
        self.api = EngineAPI(
            project_root=self.project_root.as_posix(),
            global_state_dir=self.global_state_dir.as_posix(),
        )
        self.api.load_level("levels/demo_level.json")
        self.inspector = self.api.game._inspector_system

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _create_probe(self, name: str, components: dict) -> None:
        result = self.api.create_entity(name, components=components)
        self.assertTrue(result["success"])

    def test_registry_covers_all_current_builtins(self) -> None:
        expected = {
            "Transform",
            "Sprite",
            "Collider",
            "RigidBody",
            "Animator",
            "Camera2D",
            "AudioSource",
            "InputMap",
            "PlayerController2D",
            "ScriptBehaviour",
        }
        self.assertTrue(expected.issubset(set(self.inspector.list_dedicated_editors())))

    def test_sprite_payload_edits_update_scene_and_support_undo_redo(self) -> None:
        self._create_probe(
            "InspectorSpriteProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Sprite": {
                    "enabled": True,
                    "texture_path": "assets/player.png",
                    "width": 32,
                    "height": 32,
                    "origin_x": 0.5,
                    "origin_y": 0.5,
                    "flip_x": False,
                    "flip_y": False,
                    "tint": [255, 255, 255, 255],
                },
            },
        )

        def update(payload: dict) -> None:
            payload["texture_path"] = "assets/player_alt.png"
            payload["tint"] = [128, 200, 255, 255]

        success = self.inspector.update_component_payload(self.api.game.world, "InspectorSpriteProbe", "Sprite", update)
        self.assertTrue(success)

        entity = self.api.get_entity("InspectorSpriteProbe")
        self.assertEqual(entity["components"]["Sprite"]["texture_path"], "assets/player_alt.png")
        self.assertEqual(entity["components"]["Sprite"]["texture"]["path"], "assets/player_alt.png")
        self.assertEqual(entity["components"]["Sprite"]["tint"], [128, 200, 255, 255])
        scene_sprite = self.api.scene_manager.current_scene.find_entity("InspectorSpriteProbe")["components"]["Sprite"]
        self.assertEqual(scene_sprite["tint"], [128, 200, 255, 255])

        self.assertTrue(self.api.undo()["success"])
        entity = self.api.get_entity("InspectorSpriteProbe")
        self.assertEqual(entity["components"]["Sprite"]["texture_path"], "assets/player.png")
        self.assertEqual(entity["components"]["Sprite"]["texture"]["path"], "assets/player.png")
        self.assertEqual(entity["components"]["Sprite"]["tint"], [255, 255, 255, 255])

        self.assertTrue(self.api.redo()["success"])
        entity = self.api.get_entity("InspectorSpriteProbe")
        self.assertEqual(entity["components"]["Sprite"]["texture_path"], "assets/player_alt.png")
        self.assertEqual(entity["components"]["Sprite"]["texture"]["path"], "assets/player_alt.png")
        self.assertEqual(entity["components"]["Sprite"]["tint"], [128, 200, 255, 255])

    def test_animator_payload_edits_use_serializable_source_and_history(self) -> None:
        self._create_probe(
            "InspectorAnimatorProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "Animator": {
                    "enabled": True,
                    "sprite_sheet": "assets/player_sheet.png",
                    "frame_width": 32,
                    "frame_height": 32,
                    "animations": {
                        "idle": {
                            "frames": [0, 1],
                            "slice_names": ["idle_0", "idle_1"],
                            "fps": 8.0,
                            "loop": True,
                            "on_complete": None,
                        }
                    },
                    "default_state": "idle",
                    "current_state": "idle",
                    "current_frame": 0,
                    "is_finished": False,
                },
            },
        )

        def update(payload: dict) -> None:
            payload["default_state"] = "run"
            payload["animations"]["run"] = {
                "frames": [2, 3, 4],
                "slice_names": ["run_0", "run_1", "run_2"],
                "fps": 12.0,
                "loop": True,
                "on_complete": None,
            }

        success = self.inspector.update_component_payload(self.api.game.world, "InspectorAnimatorProbe", "Animator", update)
        self.assertTrue(success)

        animator = self.api.get_entity("InspectorAnimatorProbe")["components"]["Animator"]
        self.assertEqual(animator["default_state"], "run")
        self.assertEqual(animator["animations"]["run"]["slice_names"], ["run_0", "run_1", "run_2"])
        scene_animator = self.api.scene_manager.current_scene.find_entity("InspectorAnimatorProbe")["components"]["Animator"]
        self.assertIn("run", scene_animator["animations"])

        self.assertTrue(self.api.undo()["success"])
        animator = self.api.get_entity("InspectorAnimatorProbe")["components"]["Animator"]
        self.assertEqual(animator["default_state"], "idle")
        self.assertNotIn("run", animator["animations"])

        self.assertTrue(self.api.redo()["success"])
        animator = self.api.get_entity("InspectorAnimatorProbe")["components"]["Animator"]
        self.assertEqual(animator["default_state"], "run")
        self.assertIn("run", animator["animations"])

    def test_script_behaviour_payload_edits_use_common_route_and_history(self) -> None:
        self._create_probe(
            "InspectorScriptProbe",
            {
                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                "ScriptBehaviour": {
                    "enabled": True,
                    "module_path": "platformer_character",
                    "run_in_edit_mode": False,
                    "public_data": {"health": 3, "coins": 0},
                },
            },
        )

        def update(payload: dict) -> None:
            payload["module_path"] = "enemy_brain"
            payload["public_data"] = {"health": 5, "coins": 2, "alive": True}

        success = self.inspector.update_component_payload(self.api.game.world, "InspectorScriptProbe", "ScriptBehaviour", update)
        self.assertTrue(success)

        script_data = self.api.get_entity("InspectorScriptProbe")["components"]["ScriptBehaviour"]
        self.assertEqual(script_data["module_path"], "enemy_brain")
        self.assertEqual(script_data["public_data"], {"health": 5, "coins": 2, "alive": True})
        scene_script = self.api.scene_manager.current_scene.find_entity("InspectorScriptProbe")["components"]["ScriptBehaviour"]
        self.assertEqual(scene_script["public_data"]["coins"], 2)

        self.assertTrue(self.api.undo()["success"])
        script_data = self.api.get_entity("InspectorScriptProbe")["components"]["ScriptBehaviour"]
        self.assertEqual(script_data["module_path"], "platformer_character")
        self.assertEqual(script_data["public_data"], {"health": 3, "coins": 0})

        self.assertTrue(self.api.redo()["success"])
        script_data = self.api.get_entity("InspectorScriptProbe")["components"]["ScriptBehaviour"]
        self.assertEqual(script_data["module_path"], "enemy_brain")
        self.assertEqual(script_data["public_data"]["alive"], True)

    def test_transform_editor_uses_serializable_local_values_for_child_entity(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "InspectorParent",
                {"Transform": {"enabled": True, "x": 100.0, "y": 200.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(
            self.api.create_child_entity(
                "InspectorParent",
                "InspectorChild",
                {"Transform": {"enabled": True, "x": 12.0, "y": 8.0, "rotation": 15.0, "scale_x": 1.5, "scale_y": 0.75}},
            )["success"]
        )

        child = self.api.game.world.get_entity_by_name("InspectorChild")
        transform = child.get_component(Transform)
        rendered_values: dict[str, float | bool] = {}

        def capture(label, value, *args, **kwargs):
            rendered_values[label] = value
            return args[4] + 1

        with patch.object(self.inspector, "_draw_component_field", side_effect=capture):
            self.inspector._draw_transform_editor(transform, child.id, 0, 0, 240, True, self.api.game.world)

        self.assertEqual(rendered_values["X"], 12.0)
        self.assertEqual(rendered_values["Y"], 8.0)
        self.assertEqual(rendered_values["Rotation"], 15.0)
        self.assertEqual(rendered_values["Scale X"], 1.5)
        self.assertEqual(rendered_values["Scale Y"], 0.75)

    def test_inspector_transform_edit_persists_local_transform_after_save_and_reload(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "InspectorParent",
                {"Transform": {"enabled": True, "x": 100.0, "y": 50.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(
            self.api.create_child_entity(
                "InspectorParent",
                "InspectorChild",
                {"Transform": {"enabled": True, "x": 12.0, "y": 8.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(self.api.scene_manager.set_selected_entity("InspectorChild"))
        self.assertTrue(self.inspector._apply_component_property(self.api.game.world, "InspectorChild", "Transform", "x", 30.0))
        self.assertTrue(self.inspector._apply_component_property(self.api.game.world, "InspectorChild", "Transform", "y", 40.0))

        child_data = self.api.scene_manager.current_scene.find_entity("InspectorChild")
        self.assertEqual(child_data["components"]["Transform"]["x"], 30.0)
        self.assertEqual(child_data["components"]["Transform"]["y"], 40.0)
        self.assertEqual(self.api.game.world.selected_entity_name, "InspectorChild")

        save_path = self.project_root / "levels" / "inspector_transform_scene.json"
        self.assertTrue(self.api.save_scene(path=save_path.as_posix())["success"])
        self.api.load_level(save_path.as_posix())

        child = self.api.game.world.get_entity_by_name("InspectorChild")
        transform = child.get_component(Transform)
        self.assertEqual(transform.local_x, 30.0)
        self.assertEqual(transform.local_y, 40.0)
        self.assertEqual(transform.x, 130.0)
        self.assertEqual(transform.y, 90.0)

    def test_inspector_rect_transform_edit_persists_after_save_and_reload(self) -> None:
        self._create_probe(
            "InspectorButton",
            {
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

        self.assertTrue(self.inspector._apply_component_property(self.api.game.world, "InspectorButton", "RectTransform", "anchored_x", 32.0))
        self.assertTrue(self.inspector._apply_component_property(self.api.game.world, "InspectorButton", "RectTransform", "height", 96.0))

        button_data = self.api.scene_manager.current_scene.find_entity("InspectorButton")
        self.assertEqual(button_data["components"]["RectTransform"]["anchored_x"], 32.0)
        self.assertEqual(button_data["components"]["RectTransform"]["height"], 96.0)

        save_path = self.project_root / "levels" / "inspector_rect_scene.json"
        self.assertTrue(self.api.save_scene(path=save_path.as_posix())["success"])
        self.api.load_level(save_path.as_posix())

        button = self.api.game.world.get_entity_by_name("InspectorButton")
        rect_transform = button.get_component(RectTransform)
        self.assertEqual(rect_transform.anchored_x, 32.0)
        self.assertEqual(rect_transform.height, 96.0)

    def test_script_executor_exposes_undo_redo_commands(self) -> None:
        executor = ScriptExecutor(self.api.game)
        executor.commands = [
            {"action": "INSPECT_EDIT", "args": {"entity": "Ground", "component": "Transform", "property": "x", "value": 700.0}},
            {"action": "UNDO", "args": {}},
            {"action": "REDO", "args": {}},
        ]

        self.assertTrue(executor.run_all())
        ground = self.api.get_entity("Ground")
        self.assertEqual(ground["components"]["Transform"]["x"], 700.0)


if __name__ == "__main__":
    unittest.main()
