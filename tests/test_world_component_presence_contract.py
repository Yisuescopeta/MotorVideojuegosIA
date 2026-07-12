import inspect
import unittest
from unittest.mock import patch

from engine.app.runtime_controller import RuntimeController
from engine.ecs.component import Component
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.collision_system import CollisionSystem
from engine.systems.physics_system import PhysicsSystem


class Position(Component):
    pass


class Velocity(Component):
    pass


class ExplodingLegacyIndex(dict):
    def get(self, key: object, default: object = None) -> object:
        raise AssertionError("legacy fallback used after canonical hit")


class WorldComponentPresenceContractTests(unittest.TestCase):
    def test_canonical_hit_does_not_read_legacy_index(self) -> None:
        world = World()
        world.create_entity("Canonical").add_component(Position())
        world._entities_by_component = ExplodingLegacyIndex()

        self.assertTrue(world.has_any_component_type(Position))

    def test_legacy_fallback_does_not_query_or_scan_world(self) -> None:
        world = World()
        legacy_entity = Entity("Legacy")
        legacy_entity.add_component(Position())
        world._entities_by_component[Position].append(legacy_entity)

        with (
            patch.object(world, "get_entities_with", side_effect=AssertionError("query used")),
            patch.object(world, "iter_entities", side_effect=AssertionError("scan used")),
        ):
            self.assertTrue(world.has_any_component_type(Position))

    def test_miss_empty_and_multi_type_queries(self) -> None:
        world = World()
        world.create_entity("Position").add_component(Position())

        self.assertFalse(world.has_any_component_type())
        self.assertFalse(world.has_any_component_type(Velocity))
        self.assertTrue(world.has_any_component_type(Velocity, Position))

    def test_migrated_consumers_do_not_reference_private_component_indexes(self) -> None:
        for consumer in (CollisionSystem, PhysicsSystem, RuntimeController):
            with self.subTest(consumer=consumer.__name__):
                source = inspect.getsource(consumer)
                self.assertNotIn("_component_index", source)
                self.assertNotIn("_entities_by_component", source)


if __name__ == "__main__":
    unittest.main()
