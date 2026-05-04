import json
import tempfile
import unittest
from pathlib import Path

from engine.api import EngineAPI
from engine.components.charactercontroller2d import CharacterController2D
from engine.components.collider import Collider
from engine.components.collision_filter_2d import CollisionFilter2D


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

    # --- NEW CharacterBody2D upgrade tests ---

    def test_floor_snap_every_frame(self) -> None:
        """Floor snap persists on every frame while walking on ground."""
        scene_path = self._write_scene(
            {
                "name": "SnapScene",
                "entities": [
                    {
                        "name": "Hero",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 50.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 8.0, "height": 8.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            "CharacterController2D": {"enabled": True, "use_input_map": False, "velocity_x": 50.0, "gravity": 600.0, "floor_snap_distance": 20.0},
                        },
                    },
                    {
                        "name": "Ground",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 64.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 200.0, "height": 16.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            }
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(10)
        hero = self.api.get_entity("Hero")
        self.assertTrue(hero["components"]["CharacterController2D"]["on_floor"])

    def test_one_way_platform_pass_through_below(self) -> None:
        """Character moving up through a one-way platform passes through."""
        scene_path = self._write_scene(
            {
                "name": "OneWayPassThrough",
                "entities": [
                    {
                        "name": "Hero",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 100.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            "CharacterController2D": {"enabled": True, "use_input_map": False, "velocity_y": -200.0, "gravity": 0.0, "max_fall_speed": 0.0},
                        },
                    },
                    {
                        "name": "OneWayPlatform",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 80.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 100.0, "height": 8.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False, "one_way_collision": True, "one_way_collision_direction_y": -1.0},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            }
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(30)
        hero = self.api.get_entity("Hero")
        # Hero should have passed through the platform (y < 76 = platform top)
        self.assertLess(hero["components"]["Transform"]["y"], 76.0)

    def test_one_way_platform_stand_on_top(self) -> None:
        """Character falling onto a one-way platform should land on top."""
        scene_path = self._write_scene(
            {
                "name": "OneWayLand",
                "entities": [
                    {
                        "name": "Hero",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 40.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            "CharacterController2D": {"enabled": True, "use_input_map": False, "gravity": 600.0, "floor_snap_distance": 4.0},
                        },
                    },
                    {
                        "name": "OneWayPlatform",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 80.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 100.0, "height": 8.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False, "one_way_collision": True, "one_way_collision_direction_y": -1.0},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            }
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(30)
        hero = self.api.get_entity("Hero")
        self.assertTrue(hero["components"]["CharacterController2D"]["on_floor"])

    def test_wall_classification(self) -> None:
        """Horizontal collision against a wall sets on_wall flag."""
        scene_path = self._write_scene(
            {
                "name": "WallTest",
                "entities": [
                    {
                        "name": "Hero",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 40.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            "CharacterController2D": {"enabled": True, "use_input_map": False, "velocity_x": 200.0, "gravity": 0.0, "max_fall_speed": 0.0},
                        },
                    },
                    {
                        "name": "Wall",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 30.0, "y": 40.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 64.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            }
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(6)
        hero = self.api.get_entity("Hero")
        self.assertTrue(hero["components"]["CharacterController2D"]["on_wall"])

    def test_ceiling_classification(self) -> None:
        """Vertical collision against a ceiling sets on_ceiling flag."""
        scene_path = self._write_scene(
            {
                "name": "CeilingTest",
                "entities": [
                    {
                        "name": "Hero",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 60.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            "CharacterController2D": {"enabled": True, "use_input_map": False, "velocity_y": -300.0, "gravity": 0.0, "max_fall_speed": 0.0},
                        },
                    },
                    {
                        "name": "Ceiling",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 20.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 100.0, "height": 8.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            }
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(5)
        hero = self.api.get_entity("Hero")
        self.assertTrue(hero["components"]["CharacterController2D"]["on_ceiling"])

    def test_backward_compatible_from_dict(self) -> None:
        """Old scene data without new fields loads correctly with defaults."""
        old_data = {
            "enabled": True,
            "move_mode": "move_and_slide",
            "move_speed": 150.0,
            "jump_velocity": -300.0,
            "gravity": 500.0,
            "max_fall_speed": 800.0,
            "air_control": 0.5,
            "floor_snap_distance": 3.0,
            "use_input_map": False,
            "velocity_x": 0.0,
            "velocity_y": 0.0,
            "on_floor": True,
            "collision_normal_x": 0.0,
            "collision_normal_y": -1.0,
            "last_hit_entity": "Ground",
        }
        cc = CharacterController2D.from_dict(old_data)
        self.assertEqual(cc.move_speed, 150.0)
        self.assertEqual(cc.gravity, 500.0)
        self.assertEqual(cc.up_direction_x, 0.0)
        self.assertEqual(cc.up_direction_y, -1.0)
        self.assertAlmostEqual(cc.floor_max_angle, 0.785398, places=5)
        self.assertAlmostEqual(cc.wall_min_slide_angle, 0.261799, places=5)
        self.assertFalse(cc.on_wall)
        self.assertFalse(cc.on_ceiling)
        self.assertFalse(cc.floor_stop_on_slope)
        self.assertTrue(cc.floor_block_on_wall)
        self.assertEqual(cc.platform_velocity_x, 0.0)
        self.assertEqual(cc.platform_velocity_y, 0.0)

    def test_backward_compatible_collider_from_dict(self) -> None:
        """Old Collider data without one_way fields loads correctly."""
        old_data = {"enabled": True, "width": 24.0, "height": 8.0}
        collider = Collider.from_dict(old_data)
        self.assertFalse(collider.one_way_collision)
        self.assertEqual(collider.one_way_collision_direction_y, -1.0)

    def test_collision_filter_2d_integration(self) -> None:
        """CollisionFilter2D blocks collision between entities with non-matching masks."""
        scene_path = self._write_scene(
            {
                "name": "FilterScene",
                "entities": [
                    {
                        "name": "Hero",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 60.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            "CharacterController2D": {"enabled": True, "use_input_map": False, "velocity_x": 120.0, "gravity": 0.0, "max_fall_speed": 0.0},
                        },
                    },
                    {
                        "name": "Wall",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 30.0, "y": 60.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 40.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            }
        )
        self.api.load_level(scene_path.as_posix())
        # Set collision filters so Hero (layer 1) does NOT collide with Wall (layer 2)
        self.api.set_collision_filter("Hero", layer=1, mask=1)  # Only collides with layer 1
        self.api.set_collision_filter("Wall", layer=2, mask=2)  # Only collides with layer 2
        self.api.play()
        self.api.step(30)
        hero = self.api.get_entity("Hero")
        # Without collision, hero should move past the wall (wall center at x=30)
        self.assertGreater(hero["components"]["Transform"]["x"], 30.0)

    def test_slide_collisions_tracking(self) -> None:
        """Slide collisions list is cleared each frame (empty when no sliding)."""
        scene_path = self._write_scene(
            {
                "name": "SlideScene",
                "entities": [
                    {
                        "name": "Hero",
                        "active": True,
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {"enabled": True, "x": 0.0, "y": 60.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                            "Collider": {"enabled": True, "width": 12.0, "height": 24.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            "CharacterController2D": {"enabled": True, "use_input_map": False, "gravity": 0.0, "max_fall_speed": 0.0},
                        },
                    },
                ],
                "rules": [],
                "feature_metadata": {"physics_2d": {"backend": "legacy_aabb"}},
            }
        )
        self.api.load_level(scene_path.as_posix())
        self.api.play()
        self.api.step(5)
        hero_entity = self.api.game.world.get_entity_by_name("Hero")
        cc = hero_entity.get_component(CharacterController2D)
        self.assertEqual(len(cc.slide_collisions), 0)


if __name__ == "__main__":
    unittest.main()
