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


if __name__ == "__main__":
    unittest.main()
