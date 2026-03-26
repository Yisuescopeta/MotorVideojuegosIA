import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from engine.api import EngineAPI
from engine.components.renderorder2d import RenderOrder2D
from engine.components.transform import Transform
from engine.project.project_service import ProjectService
from engine.systems.render_system import RenderSystem


def _scene_payload(name: str = "TestScene") -> dict:
    return {"name": name, "entities": [], "rules": [], "feature_metadata": {}}


class UnityRuntimeBaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        ProjectService(self.root)
        self.level_path = self.root / "levels" / "test_scene.json"
        self.level_path.write_text(json.dumps(_scene_payload(), indent=4), encoding="utf-8")
        self.api = EngineAPI(project_root=self.root.as_posix())
        self.api.load_level("levels/test_scene.json")

    def tearDown(self) -> None:
        self.api.shutdown()
        self._temp_dir.cleanup()

    def test_hierarchy_round_trip_and_play_stop_preserve_relationships(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "Parent",
                {"Transform": {"enabled": True, "x": 100.0, "y": 200.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(
            self.api.create_child_entity(
                "Parent",
                "Child",
                {"Transform": {"enabled": True, "x": 12.0, "y": 8.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(self.api.scene_manager.set_selected_entity("Child"))
        self.assertTrue(self.api.scene_manager.save_scene_to_file(self.level_path.as_posix()))

        saved = json.loads(self.level_path.read_text(encoding="utf-8"))
        child_data = next(entity for entity in saved["entities"] if entity["name"] == "Child")
        self.assertEqual(child_data["parent"], "Parent")

        child = self.api.game.world.get_entity_by_name("Child")
        transform = child.get_component(Transform)
        self.assertEqual(transform.x, 112.0)
        self.assertEqual(transform.y, 208.0)

        self.api.play()
        self.assertEqual(self.api.game.world.selected_entity_name, "Child")
        self.api.stop()
        self.assertEqual(self.api.game.world.selected_entity_name, "Child")

        self.api.load_level(self.level_path.as_posix())
        reloaded_child = self.api.game.world.get_entity_by_name("Child")
        reloaded_transform = reloaded_child.get_component(Transform)
        self.assertEqual(reloaded_transform.x, 112.0)
        self.assertEqual(reloaded_transform.y, 208.0)

    def test_prefab_instance_save_apply_and_unpack(self) -> None:
        prefab_path = self.root / "prefabs" / "enemy.prefab"
        prefab_path.write_text(
            json.dumps(
                {
                    "root_name": "Enemy",
                    "entities": [
                        {
                            "name": "Enemy",
                            "active": True,
                            "tag": "Enemy",
                            "layer": "Actors",
                            "components": {
                                "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                                "Collider": {"enabled": True, "width": 16.0, "height": 16.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                            },
                        },
                        {
                            "name": "Weapon",
                            "parent": "",
                            "active": True,
                            "tag": "Weapon",
                            "layer": "Actors",
                            "components": {
                                "Transform": {"enabled": True, "x": 4.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}
                            },
                        },
                    ],
                },
                indent=4,
            ),
            encoding="utf-8",
        )

        self.assertTrue(
            self.api.instantiate_prefab(
                "prefabs/enemy.prefab",
                name="EnemyA",
                overrides={"": {"components": {"Transform": {"x": 40.0, "y": 50.0}}}},
            )["success"]
        )
        self.assertIsNotNone(self.api.game.world.get_entity_by_name("EnemyA"))
        self.assertIsNotNone(self.api.game.world.get_entity_by_name("EnemyA/Weapon"))

        self.assertTrue(self.api.scene_manager.save_scene_to_file(self.level_path.as_posix()))
        saved = json.loads(self.level_path.read_text(encoding="utf-8"))
        self.assertEqual(len(saved["entities"]), 1)
        self.assertEqual(saved["entities"][0]["name"], "EnemyA")
        self.assertIn("prefab_instance", saved["entities"][0])

        self.assertTrue(self.api.edit_component("EnemyA/Weapon", "Transform", "x", 12.0)["success"])
        self.assertTrue(self.api.apply_prefab_overrides("EnemyA")["success"])

        prefab_data = json.loads(prefab_path.read_text(encoding="utf-8"))
        weapon_data = next(entity for entity in prefab_data["entities"] if entity["name"] == "Weapon")
        self.assertEqual(weapon_data["components"]["Transform"]["x"], 12.0)
        root_scene = self.api.scene_manager.current_scene.find_entity("EnemyA")
        self.assertEqual(root_scene["prefab_instance"]["overrides"], {})

        self.assertTrue(self.api.unpack_prefab("EnemyA")["success"])
        explicit_scene = self.api.scene_manager.current_scene.to_dict()
        explicit_names = [entity["name"] for entity in explicit_scene["entities"]]
        self.assertIn("EnemyA", explicit_names)
        self.assertIn("EnemyA/Weapon", explicit_names)
        self.assertTrue(all("prefab_instance" not in entity for entity in explicit_scene["entities"]))

    def test_render_sorting_uses_sorting_layer_and_order_in_layer(self) -> None:
        for name in ("Back", "Mid", "Front"):
            self.assertTrue(
                self.api.create_entity(
                    name,
                    {"Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
                )["success"]
            )
        self.assertTrue(self.api.set_sorting_layers(["Background", "Gameplay", "Foreground"])["success"])
        self.assertTrue(self.api.set_render_order("Back", "Background", 0)["success"])
        self.assertTrue(self.api.set_render_order("Mid", "Gameplay", 10)["success"])
        self.assertTrue(self.api.set_render_order("Front", "Foreground", -5)["success"])

        ordered = [entity.name for entity in RenderSystem()._sorted_render_entities(self.api.game.world)]
        self.assertEqual(ordered[:3], ["Back", "Mid", "Front"])

    def test_render_sorting_persists_after_save_and_reload(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "Hero",
                {"Transform": {"enabled": True, "x": 8.0, "y": 8.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(self.api.set_sorting_layers(["", "Background", "Background", "Foreground"])["success"])
        self.assertTrue(self.api.set_render_order("Hero", "Foreground", 9)["success"])
        self.assertTrue(self.api.scene_manager.save_scene_to_file(self.level_path.as_posix()))

        raw = json.loads(self.level_path.read_text(encoding="utf-8"))
        self.assertEqual(raw["feature_metadata"]["render_2d"]["sorting_layers"], ["Default", "Background", "Foreground"])
        hero_data = next(entity for entity in raw["entities"] if entity["name"] == "Hero")
        self.assertEqual(hero_data["components"]["RenderOrder2D"]["sorting_layer"], "Foreground")
        self.assertEqual(hero_data["components"]["RenderOrder2D"]["order_in_layer"], 9)

        self.api.load_level(self.level_path.as_posix())
        hero = self.api.game.world.get_entity_by_name("Hero")
        render_order = hero.get_component(RenderOrder2D)
        self.assertEqual(render_order.sorting_layer, "Foreground")
        self.assertEqual(render_order.order_in_layer, 9)

    def test_render_sorting_validates_layer_and_clamps_order(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "SpriteA",
                {"Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}},
            )["success"]
        )
        self.assertTrue(self.api.set_sorting_layers(["Gameplay"])["success"])

        invalid_layer = self.api.set_render_order("SpriteA", "MissingLayer", 0)
        self.assertFalse(invalid_layer["success"])

        self.assertTrue(self.api.set_render_order("SpriteA", "Gameplay", 999999)["success"])
        sprite = self.api.get_entity("SpriteA")
        self.assertEqual(sprite["components"]["RenderOrder2D"]["order_in_layer"], 32767)

    def test_physics_body_types_and_layer_matrix(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "DynamicBody",
                {
                    "Transform": {"enabled": True, "x": 20.0, "y": 10.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 1.0, "is_grounded": False},
                    "Collider": {"enabled": True, "width": 10.0, "height": 10.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                },
            )["success"]
        )
        self.assertTrue(
            self.api.create_entity(
                "KinematicBody",
                {
                    "Transform": {"enabled": True, "x": 40.0, "y": 10.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "RigidBody": {"enabled": True, "body_type": "kinematic", "gravity_scale": 1.0, "velocity_x": 0.0, "velocity_y": 0.0},
                    "Collider": {"enabled": True, "width": 10.0, "height": 10.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                },
            )["success"]
        )
        self.assertTrue(
            self.api.create_entity(
                "Wall",
                {
                    "Transform": {"enabled": True, "x": 70.0, "y": 10.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "Collider": {"enabled": True, "width": 10.0, "height": 50.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                },
            )["success"]
        )
        self.assertTrue(self.api.set_entity_layer("DynamicBody", "Hero")["success"])
        self.assertTrue(self.api.set_entity_layer("Wall", "Walls")["success"])
        self.assertTrue(self.api.set_physics_layer_collision("Hero", "Walls", False)["success"])

        self.assertTrue(
            self.api.create_entity(
                "Mover",
                {
                    "Transform": {"enabled": True, "x": 40.0, "y": 80.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 0.0, "velocity_x": 120.0, "velocity_y": 0.0},
                    "Collider": {"enabled": True, "width": 10.0, "height": 10.0, "offset_x": 0.0, "offset_y": 0.0, "is_trigger": False},
                },
            )["success"]
        )
        self.assertTrue(self.api.set_entity_layer("Mover", "Hero")["success"])

        self.api.play()
        self.api.step(20)

        dynamic_body = self.api.game.world.get_entity_by_name("DynamicBody")
        kinematic_body = self.api.game.world.get_entity_by_name("KinematicBody")
        mover = self.api.game.world.get_entity_by_name("Mover")

        self.assertGreater(dynamic_body.get_component(Transform).y, 10.0)
        self.assertEqual(kinematic_body.get_component(Transform).y, 10.0)
        self.assertGreater(mover.get_component(Transform).x, 70.0)

    def test_rigidbody_constraints_freeze_axes_and_persist(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "Crate",
                {
                    "Transform": {"enabled": True, "x": 10.0, "y": 10.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 1.0},
                },
            )["success"]
        )
        self.assertTrue(self.api.set_rigidbody_constraints("Crate", ["FreezePositionX"])["success"])
        crate = self.api.get_entity("Crate")
        rb = crate["components"]["RigidBody"]
        self.assertTrue(rb["freeze_x"])
        self.assertFalse(rb["freeze_y"])
        self.assertEqual(rb["constraints"], ["FreezePositionX"])

        self.assertTrue(self.api.set_rigidbody_constraints("Crate", ["FreezePosition"])["success"])
        crate = self.api.get_entity("Crate")
        rb = crate["components"]["RigidBody"]
        self.assertTrue(rb["freeze_x"])
        self.assertTrue(rb["freeze_y"])
        self.assertEqual(rb["constraints"], ["FreezePositionX", "FreezePositionY"])

        self.assertTrue(self.api.scene_manager.save_scene_to_file(self.level_path.as_posix()))
        self.api.load_level(self.level_path.as_posix())
        crate = self.api.get_entity("Crate")
        rb = crate["components"]["RigidBody"]
        self.assertEqual(rb["constraints"], ["FreezePositionX", "FreezePositionY"])

        self.assertTrue(self.api.edit_component("Crate", "RigidBody", "freeze_x", False)["success"])
        crate = self.api.get_entity("Crate")
        rb = crate["components"]["RigidBody"]
        self.assertEqual(rb["constraints"], ["FreezePositionY"])

    def test_rigidbody_constraints_validate_supported_values(self) -> None:
        self.assertTrue(
            self.api.create_entity(
                "BodyA",
                {
                    "Transform": {"enabled": True, "x": 0.0, "y": 0.0, "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0},
                    "RigidBody": {"enabled": True, "body_type": "dynamic", "gravity_scale": 1.0},
                },
            )["success"]
        )
        result = self.api.set_rigidbody_constraints("BodyA", ["FreezeRotation"])
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
