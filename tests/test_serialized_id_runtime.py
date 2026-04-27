import unittest

from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.levels.component_registry import create_default_registry
from engine.scenes.scene import Scene


class NoValuesDict(dict):
    def values(self):  # type: ignore[override]
        raise AssertionError("get_entity_by_serialized_id must not scan entities")


class SerializedIdRuntimeTests(unittest.TestCase):
    def test_entity_to_dict_uses_string_serialized_id(self) -> None:
        entity = Entity("Hero")
        entity.serialized_id = " entity_hero "

        self.assertEqual(entity.to_dict()["id"], "entity_hero")
        self.assertIsInstance(entity.to_dict()["id"], str)

    def test_entity_to_dict_runtime_fallback_id_is_string(self) -> None:
        entity = Entity("RuntimeOnly")

        self.assertEqual(entity.to_dict()["id"], f"runtime_{entity.id}")
        self.assertIsInstance(entity.to_dict()["id"], str)

    def test_get_entity_by_serialized_id_uses_index(self) -> None:
        world = World()
        entity = world.create_entity("Hero")
        entity.serialized_id = "entity_hero"
        world._entities = NoValuesDict(world._entities)

        self.assertIs(world.get_entity_by_serialized_id("entity_hero"), entity)

    def test_entity_rename_preserves_serialized_id_lookup(self) -> None:
        world = World()
        entity = world.create_entity("Hero")
        entity.serialized_id = "entity_hero"

        entity.name = "RenamedHero"

        self.assertIs(world.get_entity_by_serialized_id("entity_hero"), entity)
        self.assertIs(world.get_entity_by_name("RenamedHero"), entity)

    def test_serialized_id_change_updates_index(self) -> None:
        world = World()
        entity = world.create_entity("Hero")
        entity.serialized_id = "entity_hero"

        entity.serialized_id = "entity_player"

        self.assertIsNone(world.get_entity_by_serialized_id("entity_hero"))
        self.assertIs(world.get_entity_by_serialized_id("entity_player"), entity)

    def test_remove_entity_cleans_serialized_id_index(self) -> None:
        world = World()
        entity = world.create_entity("Hero")
        entity.serialized_id = "entity_hero"

        world.remove_entity(entity.id)

        self.assertIsNone(world.get_entity_by_serialized_id("entity_hero"))
        self.assertNotIn("entity_hero", world._serialized_id_index)

    def test_clear_cleans_serialized_id_index(self) -> None:
        world = World()
        entity = world.create_entity("Hero")
        entity.serialized_id = "entity_hero"

        world.clear()

        self.assertIsNone(world.get_entity_by_serialized_id("entity_hero"))
        self.assertEqual(world._serialized_id_index, {})

    def test_scene_create_world_assigns_and_indexes_scene_entity_id(self) -> None:
        scene = Scene(
            data={
                "name": "SerializedScene",
                "entities": [
                    {
                        "id": "entity_hero",
                        "name": "Hero",
                        "components": {},
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        world = scene.create_world(create_default_registry())
        entity = world.get_entity_by_name("Hero")

        self.assertIsNotNone(entity)
        self.assertEqual(entity.serialized_id, "entity_hero")
        self.assertIs(world.get_entity_by_serialized_id("entity_hero"), entity)


if __name__ == "__main__":
    unittest.main()
