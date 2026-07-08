import unittest
from unittest.mock import patch

from engine.ecs.component import Component
from engine.ecs.world import World


class Position(Component):
    def __init__(self, enabled: bool = True, value: int = 0) -> None:
        self.enabled = enabled
        self.value = value


class Velocity(Component):
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled


class Acceleration(Component):
    pass


class ECSIndexTests(unittest.TestCase):
    def test_add_remove_and_replace_component_keep_indexes_synchronized(self) -> None:
        world = World()
        entity = world.create_entity("Actor")
        first = Position(value=1)
        replacement = Position(value=2)

        entity.add_component(first)
        self.assertEqual(world.get_entities_with(Position), [entity])
        self.assertEqual(world._entities_by_component[Position], [entity])
        self.assertIs(world.get_entity_by_component_instance(first), entity)

        entity.add_component(replacement)
        self.assertEqual(world.get_entities_with(Position), [entity])
        self.assertEqual(world._entities_by_component[Position], [entity])
        self.assertIsNone(world.get_entity_by_component_instance(first))
        self.assertIs(world.get_entity_by_component_instance(replacement), entity)

        entity.remove_component(Position)
        self.assertEqual(world.get_entities_with(Position), [])
        self.assertNotIn(Position, world._entities_by_component)
        self.assertIsNone(world.get_entity_by_component_instance(replacement))

    def test_remove_entity_cleans_canonical_and_legacy_indexes_incrementally(self) -> None:
        world = World()
        first = world.create_entity("First")
        second = world.create_entity("Second")
        first.add_component(Position())
        second.add_component(Position())

        legacy_list = world._entities_by_component[Position]
        world.remove_entity(first.id)

        self.assertIs(world._entities_by_component[Position], legacy_list)
        self.assertEqual(legacy_list, [second])
        self.assertIsNone(world.get_entity_by_name("First"))
        self.assertEqual(world.get_entities_with(Position), [second])

    def test_name_groups_and_active_changes_preserve_deterministic_queries(self) -> None:
        world = World()
        beta = world.create_entity("Beta")
        alpha = world.create_entity("Alpha")
        for entity in (beta, alpha):
            entity.groups = ("Actors",)
            entity.add_component(Position())

        self.assertEqual(world.group_registry.get_entity_names("Actors"), ["Alpha", "Beta"])
        alpha.name = "Zulu"
        self.assertEqual(world.group_registry.get_entity_names("Actors"), ["Beta", "Zulu"])

        beta.groups = ("Enemies",)
        self.assertEqual(world.group_registry.get_entity_names("Actors"), ["Zulu"])
        self.assertEqual(world.group_registry.get_entity_names("Enemies"), ["Beta"])

        beta.active = False
        self.assertEqual(world.get_entities_with(Position), [alpha])
        beta.active = True
        self.assertEqual(world.get_entities_with(Position), [beta, alpha])

    def test_group_order_cache_is_reused_and_invalidated(self) -> None:
        world = World()
        beta = world.create_entity("Beta")
        alpha = world.create_entity("Alpha")
        beta.groups = ("Actors",)
        alpha.groups = ("Actors",)

        with patch("builtins.sorted", wraps=sorted) as sorted_mock:
            self.assertEqual(world.group_registry.get_entity_names("Actors"), ["Alpha", "Beta"])
            first_sort_count = sorted_mock.call_count
            self.assertEqual(world.group_registry.get_entity_names("Actors"), ["Alpha", "Beta"])
            self.assertEqual(sorted_mock.call_count, first_sort_count)

            alpha.name = "Zulu"
            self.assertEqual(world.group_registry.get_entity_names("Actors"), ["Beta", "Zulu"])
            self.assertGreater(sorted_mock.call_count, first_sort_count)

    def test_component_query_cache_preserves_active_and_enabled_semantics(self) -> None:
        world = World()
        first = world.create_entity("First")
        second = world.create_entity("Second")
        first.add_component(Position())
        first.add_component(Velocity())
        second.add_component(Position())
        second.add_component(Velocity(enabled=False))

        self.assertEqual(world.get_entities_with(Position, Velocity), [first])
        first.get_component(Velocity).enabled = False
        second.get_component(Velocity).enabled = True
        self.assertEqual(world.get_entities_with(Position, Velocity), [second])

    def test_component_query_cache_invalidates_only_queries_using_changed_component(self) -> None:
        world = World()
        position_only = world.create_entity("PositionOnly")
        velocity_only = world.create_entity("VelocityOnly")
        position_only.add_component(Position())
        velocity_only.add_component(Velocity())

        self.assertEqual(world.get_entities_with(Position), [position_only])
        self.assertEqual(world.get_entities_with(Velocity), [velocity_only])
        self.assertEqual(world.get_entities_with(Position, Velocity), [])
        cached_position_ids = world._component_query_cache[(Position,)]
        initial_misses = world._component_query_cache_misses

        position_only.add_component(Velocity())

        self.assertIs(world._component_query_cache[(Position,)], cached_position_ids)
        self.assertNotIn((Velocity,), world._component_query_cache)
        self.assertNotIn((Position, Velocity), world._component_query_cache)
        self.assertEqual(world._component_query_cache_invalidations, 2)
        self.assertEqual(world.get_entities_with(Position), [position_only])
        self.assertEqual(world._component_query_cache_hits, 1)
        self.assertEqual(world._component_query_cache_misses, initial_misses)
        self.assertEqual(world.get_entities_with(Velocity), [position_only, velocity_only])
        self.assertEqual(world.get_entities_with(Position, Velocity), [position_only])

    def test_unrelated_component_membership_keeps_existing_query_cache(self) -> None:
        world = World()
        position_entity = world.create_entity("Position")
        other_entity = world.create_entity("Other")
        position_entity.add_component(Position())

        self.assertEqual(world.get_entities_with(Position), [position_entity])
        cached_position_ids = world._component_query_cache[(Position,)]

        other_entity.add_component(Acceleration())

        self.assertIs(world._component_query_cache[(Position,)], cached_position_ids)
        self.assertEqual(world._component_query_cache_invalidations, 0)
        self.assertEqual(world.get_entities_with(Position), [position_entity])
        self.assertEqual(world._component_query_cache_hits, 1)

    def test_legacy_fallback_uses_component_lists_without_world_scan(self) -> None:
        world = World()
        entity = world.create_entity("Legacy")
        component = Position()
        entity._components[Position] = component
        world._entities_by_component[Position].append(entity)

        with patch.object(world, "iter_entities", side_effect=AssertionError("full scan")):
            self.assertEqual(world.get_entities_with(Position), [entity])


if __name__ == "__main__":
    unittest.main()
