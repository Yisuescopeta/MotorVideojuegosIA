import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.components.transform import Transform
from engine.editor.undo_redo import UndoRedoManager
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene import Scene
from engine.scenes.scene_manager import SceneManager
from engine.scenes.scene_projection import SceneProjectionService


def _transform(x: float = 0.0, y: float = 0.0) -> dict[str, object]:
    return {
        "enabled": True,
        "x": x,
        "y": y,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


class SceneIncrementalCreationTests(unittest.TestCase):
    def test_large_scene_add_is_incremental_and_preserves_existing_objects(self) -> None:
        manager = SceneManager(create_default_registry())
        entities = [
            {
                "id": f"entity_{index}",
                "name": f"Entity_{index}",
                "components": {"Transform": _transform(float(index), 0.0)},
            }
            for index in range(2000)
        ]
        manager.load_scene(
            {
                "schema_version": 2,
                "name": "Large",
                "entities": entities,
                "rules": [],
                "feature_metadata": {},
            }
        )
        scene = manager.current_scene
        world = manager.get_edit_world()
        first_entity_data = scene.entities_data[0]

        with patch.object(
            SceneProjectionService,
            "create_world",
            side_effect=AssertionError("full rebuild"),
        ):
            self.assertTrue(manager.create_entity("Added", components={"Transform": _transform()}))

        self.assertIs(manager.get_edit_world(), world)
        self.assertIs(scene.entities_data[0], first_entity_data)
        self.assertEqual(len(scene.entities_data), 2001)
        self.assertIsNotNone(world.get_entity_by_name("Added"))

    def test_add_entity_rejects_duplicate_id_without_partial_mutation(self) -> None:
        scene = Scene(
            data={
                "schema_version": 2,
                "name": "DuplicateIds",
                "entities": [{"id": "shared", "name": "Existing", "components": {}}],
                "rules": [],
                "feature_metadata": {},
            }
        )
        before = list(scene.entities_data)

        added = scene.add_entity({"id": "shared", "name": "Added", "components": {}})

        self.assertFalse(added)
        self.assertEqual(scene.entities_data, before)
        self.assertIsNone(scene.find_entity("Added"))

    def test_world_runtime_mutation_does_not_change_scene_data(self) -> None:
        source = {
            "schema_version": 2,
            "name": "Isolation",
            "entities": [
                {
                    "id": "actor",
                    "name": "Actor",
                    "components": {
                        "Transform": _transform(5.0, 6.0),
                        "Line2D": {
                            "enabled": True,
                            "points": [[0.0, 0.0], [10.0, 10.0]],
                            "width": 2.0,
                            "color": [255, 255, 255, 255],
                            "joint_mode": "sharp",
                            "closed": False,
                            "cap_mode": "none",
                        },
                    },
                    "component_metadata": {"Line2D": {"origin": "test", "nested": {"value": 1}}},
                    "prefab_instance": {
                        "prefab_path": "missing.prefab",
                        "root_name": "Actor",
                        "overrides": {"operations": [{"op": "set_entity_property", "target": "", "field": "tag", "value": "A"}]},
                    },
                }
            ],
            "rules": [],
            "feature_metadata": {"custom": {"values": [1, 2]}},
        }
        scene = Scene(data=source)
        world = scene.create_world(create_default_registry())
        actor = world.get_entity_by_name("Actor")

        actor.get_component_by_name("Line2D").points[0][0] = 99.0
        actor.prefab_instance["overrides"]["operations"][0]["value"] = "Runtime"
        world.feature_metadata["custom"]["values"].append(3)

        scene_actor = scene.find_entity("Actor")
        self.assertEqual(scene_actor["components"]["Line2D"]["points"][0][0], 0.0)
        self.assertEqual(
            scene_actor["prefab_instance"]["overrides"]["operations"][0]["value"],
            "A",
        )
        self.assertEqual(scene.feature_metadata["custom"]["values"], [1, 2])

    def test_incremental_prefab_overrides_undo_redo_and_play_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prefab_path = root / "enemy.prefab"
            scene_path = root / "scene.json"
            prefab_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "root_name": "Enemy",
                        "entities": [
                            {"name": "Enemy", "components": {"Transform": _transform()}},
                            {
                                "name": "Weapon",
                                "parent": "",
                                "components": {"Transform": _transform(4.0, 0.0)},
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manager = SceneManager(create_default_registry())
            history = UndoRedoManager()
            manager.set_history_manager(history)
            manager.load_scene(
                {
                    "schema_version": 2,
                    "name": "PrefabScene",
                    "entities": [],
                    "rules": [],
                    "feature_metadata": {},
                },
                source_path=scene_path.as_posix(),
            )

            self.assertTrue(
                manager.create_entity_from_data(
                    {
                        "name": "EnemyA",
                        "components": {},
                        "prefab_instance": {
                            "prefab_path": "enemy.prefab",
                            "root_name": "Enemy",
                            "overrides": {
                                "": {"components": {"Transform": {"x": 20.0}}},
                                "Weapon": {"components": {"Transform": {"x": 12.0}}},
                            },
                        },
                    }
                )
            )
            edit_world = manager.get_edit_world()
            root_entity = edit_world.get_entity_by_name("EnemyA")
            weapon = edit_world.get_entity_by_name("EnemyA/Weapon")
            self.assertEqual(root_entity.get_component(Transform).x, 20.0)
            self.assertEqual(weapon.get_component(Transform).local_x, 12.0)

            runtime_world = manager.enter_play()
            runtime_world.get_entity_by_name("EnemyA").get_component(Transform).x = 99.0
            manager.exit_play()
            self.assertEqual(manager.current_scene.find_entity("EnemyA")["prefab_instance"]["root_name"], "Enemy")
            self.assertEqual(manager.get_edit_world().get_entity_by_name("EnemyA").get_component(Transform).x, 20.0)

            self.assertTrue(history.undo())
            self.assertIsNone(manager.current_scene.find_entity("EnemyA"))
            self.assertIsNone(manager.get_edit_world().get_entity_by_name("EnemyA/Weapon"))
            self.assertTrue(history.redo())
            self.assertIsNotNone(manager.get_edit_world().get_entity_by_name("EnemyA/Weapon"))


if __name__ == "__main__":
    unittest.main()
