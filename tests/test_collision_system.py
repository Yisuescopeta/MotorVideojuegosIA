import unittest

from engine.components.collider import Collider
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.events.event_bus import EventBus
from engine.systems.collision_system import CollisionSystem


class CollisionSystemTests(unittest.TestCase):
    def _make_entity(
        self,
        world: World,
        name: str,
        *,
        x: float,
        y: float = 0.0,
        width: float = 10.0,
        height: float = 10.0,
        is_trigger: bool = False,
        layer: str = "Gameplay",
    ):
        entity = world.create_entity(name)
        entity.layer = layer
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(Collider(width=width, height=height, is_trigger=is_trigger))
        return entity

    def test_update_emits_collision_and_trigger_events_with_local_candidates(self) -> None:
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
        event_bus = EventBus()
        collision_system = CollisionSystem(event_bus=event_bus)

        self._make_entity(world, "Player", x=0.0)
        self._make_entity(world, "Wall", x=6.0)
        self._make_entity(world, "Trigger", x=-6.0, is_trigger=True)
        self._make_entity(world, "FarA", x=400.0)
        self._make_entity(world, "FarB", x=900.0)

        collision_system.update(world)
        metrics = collision_system.get_step_metrics()
        event_names = [event.name for event in event_bus.get_recent_events()]

        self.assertEqual(len(collision_system.get_collisions()), 2)
        self.assertIn("on_collision", event_names)
        self.assertIn("on_trigger_enter", event_names)
        self.assertLess(metrics["candidate_pairs"], 10)
        self.assertEqual(metrics["actual_collisions"], 2)

    def test_update_respects_layer_matrix(self) -> None:
        world = World()
        world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": False}}}
        event_bus = EventBus()
        collision_system = CollisionSystem(event_bus=event_bus)

        self._make_entity(world, "Player", x=0.0)
        self._make_entity(world, "Wall", x=6.0)

        collision_system.update(world)

        self.assertEqual(collision_system.get_collisions(), [])
        self.assertEqual(event_bus.get_recent_events(), [])
        self.assertEqual(collision_system.get_step_metrics()["actual_collisions"], 0)

    def test_multicell_pairs_do_not_duplicate_collisions(self) -> None:
        world = World()
        event_bus = EventBus()
        collision_system = CollisionSystem(event_bus=event_bus)

        self._make_entity(world, "LargeA", x=0.0, width=320.0)
        self._make_entity(world, "LargeB", x=100.0, width=320.0)

        collision_system.update(world)
        metrics = collision_system.get_step_metrics()

        self.assertEqual(len(collision_system.get_collisions()), 1)
        self.assertEqual(metrics["candidate_pairs"], 1)
        self.assertEqual(metrics["actual_collisions"], 1)

    def test_default_and_deterministic_debug_detect_same_collisions_and_metrics(self) -> None:
        def build_world() -> World:
            world = World()
            world.feature_metadata = {"physics_2d": {"layer_matrix": {"Gameplay|Gameplay": True}}}
            self._make_entity(world, "Player", x=0.0)
            self._make_entity(world, "Wall", x=6.0)
            self._make_entity(world, "Trigger", x=-6.0, is_trigger=True)
            self._make_entity(world, "FarA", x=400.0)
            self._make_entity(world, "FarB", x=900.0)
            return world

        default_bus = EventBus()
        debug_bus = EventBus()
        default_system = CollisionSystem(event_bus=default_bus)
        debug_system = CollisionSystem(event_bus=debug_bus, deterministic_debug=True)

        default_system.update(build_world())
        debug_system.update(build_world())

        self.assertEqual(
            self._collision_pairs(default_system),
            self._collision_pairs(debug_system),
        )
        self.assertEqual(
            self._event_pairs(default_bus),
            self._event_pairs(debug_bus),
        )
        self.assertEqual(default_system.get_step_metrics(), debug_system.get_step_metrics())

    def test_update_clears_reused_entries_between_frames(self) -> None:
        world = World()
        event_bus = EventBus()
        collision_system = CollisionSystem(event_bus=event_bus)

        first = self._make_entity(world, "First", x=0.0)
        second = self._make_entity(world, "Second", x=6.0)

        collision_system.update(world)
        self.assertEqual(self._collision_pairs(collision_system), {("First", "Second")})

        second.get_component(Transform).x = 300.0
        event_bus.clear_history()
        collision_system.update(world)
        self.assertEqual(collision_system.get_collisions(), [])
        self.assertEqual(event_bus.get_recent_events(), [])
        self.assertEqual(collision_system.get_step_metrics()["actual_collisions"], 0)

        second.get_component(Collider).enabled = False
        collision_system.update(world)
        self.assertNotIn(int(second.id), collision_system._entries_by_id)

        world.remove_entity(first.id)
        collision_system.update(world)
        self.assertEqual(collision_system._entries_by_id, {})
        self.assertEqual(collision_system._query_buffer, set())
        self.assertEqual(collision_system.get_step_metrics()["candidate_pairs"], 0)

    def test_update_reuses_internal_buffers_across_frames(self) -> None:
        world = World()
        collision_system = CollisionSystem()

        self._make_entity(world, "First", x=0.0)
        self._make_entity(world, "Second", x=6.0)

        grid_id = id(collision_system._grid)
        entries_id = id(collision_system._entries_by_id)
        checked_pairs_id = id(collision_system._checked_pairs)
        query_buffer_id = id(collision_system._query_buffer)

        collision_system.update(world)
        collision_system.update(world)

        self.assertEqual(id(collision_system._grid), grid_id)
        self.assertEqual(id(collision_system._entries_by_id), entries_id)
        self.assertEqual(id(collision_system._checked_pairs), checked_pairs_id)
        self.assertEqual(id(collision_system._query_buffer), query_buffer_id)

    def _collision_pairs(self, collision_system: CollisionSystem) -> set[tuple[str, str]]:
        return {
            tuple(sorted((collision.entity_a.name, collision.entity_b.name)))
            for collision in collision_system.get_collisions()
        }

    def _event_pairs(self, event_bus: EventBus) -> set[tuple[str, str, bool]]:
        return {
            tuple(
                [
                    *sorted((event.data["entity_a"], event.data["entity_b"])),
                    event.name == "on_trigger_enter",
                ]
            )
            for event in event_bus.get_recent_events()
        }


if __name__ == "__main__":
    unittest.main()
