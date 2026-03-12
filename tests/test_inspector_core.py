import os
import sys
import unittest

sys.path.append(os.getcwd())

from cli.script_executor import ScriptExecutor
from engine.api import EngineAPI


class InspectorCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = EngineAPI()
        self.api.load_level("levels/demo_level.json")
        self.inspector = self.api.game._inspector_system

    def tearDown(self) -> None:
        self.api.shutdown()

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
