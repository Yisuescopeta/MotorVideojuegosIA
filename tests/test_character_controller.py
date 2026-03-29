import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.components.charactercontroller2d import CharacterController2D


class CharacterControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project_root = self.root / "CharacterControllerProject"
        self.api = EngineAPI(project_root=self.project_root.as_posix(), global_state_dir=(self.root / "global_state").as_posix())

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def _write_scene(self, payload: dict) -> Path:
        path = self.project_root / "levels" / "character_scene.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def test_platform_scene_character_controller_moves_slides_and_jumps(self) -> None:
        scene_path = self._write_scene(
            {
                "name": "Platform Character",
                "entities": [
                    {
                        "name": "Hero",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            "CharacterController2D": {
                                "enabled": True,
                                "move_mode": "move_and_slide",
                                "move_speed": 120.0,
                                "jump_velocity": -260.0,
                                "gravity": 600.0,
                                "floor_snap_distance": 2.0,
                                "use_input_map": False,
                                "velocity_x": 120.0,
                            },
                        },
                    },
                    {
                        "name": "Ground",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 60.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 200.0, "height": 20.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                    {
                        "name": "Wall",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 50.0, "y": 20.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 80.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            }
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(24)
        hero = self.api.get_entity("Hero")
        controller = hero["components"]["CharacterController2D"]
        self.assertGreater(hero["components"]["Transform"]["x"], 0.0)
        self.assertLess(hero["components"]["Transform"]["x"], 50.0)
        self.assertTrue(controller["on_floor"])

        hero_entity = self.api.game.world.get_entity_by_name("Hero")
        controller_component = hero_entity.get_component(CharacterController2D)
        controller_component.velocity_y = controller_component.jump_velocity
        controller_component.on_floor = False
        self.api.step(4)
        hero_after_jump = self.api.get_entity("Hero")
        self.assertLess(hero_after_jump["components"]["Transform"]["y"], hero["components"]["Transform"]["y"])

    def test_character_controller_emits_collision_and_respects_layer_matrix(self) -> None:
        scene_path = self._write_scene(
            {
                "name": "Character Layers",
                "entities": [
                    {
                        "name": "Hero",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            "CharacterController2D": {"enabled": True, "use_input_map": False, "velocity_x": 120.0, "gravity": 0.0, "max_fall_speed": 0.0},
                        },
                    },
                    {
                        "name": "Wall",
                        "active": True,
                        "tag": "",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 30.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 40.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            }
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(20)
        event_names = [event.name for event in self.api.game._event_bus.get_recent_events()]
        self.assertIn("on_collision", event_names)

        self.api.stop()
        result = self.api.set_physics_layer_collision("Gameplay", "Gameplay", False)
        self.assertTrue(result["success"])
        hero_entity = self.api.game.world.get_entity_by_name("Hero")
        controller_component = hero_entity.get_component(CharacterController2D)
        hero_entity.get_component(type(hero_entity.get_component(CharacterController2D))).velocity_x = 120.0
        controller_component.velocity_x = 120.0
        self.api.play()
        self.api.step(20)
        hero = self.api.get_entity("Hero")
        self.assertGreater(hero["components"]["Transform"]["x"], 30.0)


if __name__ == "__main__":
    unittest.main()
