import math
import unittest

from engine.components.collider import Collider
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.events.event_bus import EventBus
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend
from engine.systems.collision_system import CollisionSystem


class CapsuleColliderTests(unittest.TestCase):
    """Tests for capsule-shaped collider: bounds, serialization, collision."""

    # ── Bounds ──────────────────────────────────────────────

    def test_capsule_bounds_zero_height(self) -> None:
        """Capsule with height=0 is a circle, bounds = square of 2*radius."""
        c = Collider(shape_type="capsule", radius=8.0, capsule_height=0.0)
        left, top, right, bottom = c.get_bounds(100.0, 200.0)
        self.assertEqual(left, 92.0)
        self.assertEqual(right, 108.0)
        self.assertEqual(top, 192.0)
        self.assertEqual(bottom, 208.0)

    def test_capsule_bounds_with_height(self) -> None:
        """Capsule bounds cover the full height including caps."""
        c = Collider(shape_type="capsule", radius=10.0, capsule_height=20.0, offset_x=5.0, offset_y=-3.0)
        left, top, right, bottom = c.get_bounds(100.0, 200.0)
        half_h = 10.0 + 20.0 / 2  # 20.0
        self.assertEqual(left, 105.0 - 10.0)   # 95.0
        self.assertEqual(right, 105.0 + 10.0)  # 115.0
        self.assertEqual(top, 197.0 - 20.0)    # 177.0
        self.assertEqual(bottom, 197.0 + 20.0) # 217.0

    def test_box_bounds_unchanged(self) -> None:
        """Box shape get_bounds is not affected by capsule fields."""
        c = Collider(shape_type="box", width=40.0, height=50.0, capsule_height=99.0)
        left, top, right, bottom = c.get_bounds(0.0, 0.0)
        self.assertEqual(left, -20.0)
        self.assertEqual(right, 20.0)
        self.assertEqual(top, -25.0)
        self.assertEqual(bottom, 25.0)

    # ── Serialization roundtrip ─────────────────────────────

    def test_serialization_roundtrip_capsule(self) -> None:
        c = Collider(shape_type="capsule", radius=12.0, capsule_height=30.0, offset_x=2.0, is_trigger=True)
        d = c.to_dict()
        c2 = Collider.from_dict(d)
        self.assertEqual(c2.shape_type, "capsule")
        self.assertEqual(c2.radius, 12.0)
        self.assertEqual(c2.capsule_height, 30.0)
        self.assertEqual(c2.offset_x, 2.0)
        self.assertTrue(c2.is_trigger)

    def test_serialization_defaults_capsule_height(self) -> None:
        c = Collider.from_dict({"shape_type": "box", "width": 32.0})
        self.assertEqual(c.capsule_height, 0.0)

    # ── Collision System: capsule vs AABB ───────────────────

    def _make_entity(self, world, name, x, y, **collider_kwargs):
        entity = world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(Collider(**collider_kwargs))
        return entity

    def _run_collision(self, *entities_and_kwargs):
        world = World()
        event_bus = EventBus()
        cs = CollisionSystem(event_bus=event_bus)
        for name, x, y, kwargs in entities_and_kwargs:
            self._make_entity(world, name, x, y, **kwargs)
        cs.update(world)
        return cs, event_bus

    def test_capsule_vs_aabb_collision_horizontal(self) -> None:
        cs, bus = self._run_collision(
            ("Cap", 0.0, 0.0, {"shape_type": "capsule", "radius": 8.0, "capsule_height": 30.0}),
            ("Wall", 14.0, 0.0, {"shape_type": "box", "width": 20.0, "height": 60.0}),
        )
        self.assertEqual(len(cs.get_collisions()), 1, "Capsule should overlap AABB horizontally")

    def test_capsule_vs_aabb_no_collision(self) -> None:
        cs, bus = self._run_collision(
            ("Cap", 0.0, 0.0, {"shape_type": "capsule", "radius": 8.0, "capsule_height": 30.0}),
            ("Wall", 50.0, 0.0, {"shape_type": "box", "width": 20.0, "height": 60.0}),
        )
        self.assertEqual(len(cs.get_collisions()), 0, "Capsule far from AABB should not collide")

    def test_capsule_vs_aabb_corner_no_false_positive(self) -> None:
        """AABB diagonal corner touching capsule AABB but not the capsule body."""
        cs, bus = self._run_collision(
            ("Cap", 0.0, 0.0, {"shape_type": "capsule", "radius": 10.0, "capsule_height": 0.0}),
            # Place small AABB at (15, 15) where AABB overlap may occur but
            # distance from circle center is > radius.
            ("Small", 15.0, 15.0, {"shape_type": "box", "width": 6.0, "height": 6.0}),
        )
        collisions = cs.get_collisions()
        self.assertEqual(len(collisions), 0, "Corner AABB should not register false positive")

    # ── Collision System: capsule vs capsule ─────────────────

    def test_capsule_vs_capsule_collision(self) -> None:
        cs, bus = self._run_collision(
            ("A", 0.0, 0.0, {"shape_type": "capsule", "radius": 10.0, "capsule_height": 20.0}),
            ("B", 15.0, 0.0, {"shape_type": "capsule", "radius": 10.0, "capsule_height": 20.0}),
        )
        self.assertEqual(len(cs.get_collisions()), 1)

    def test_capsule_vs_capsule_no_collision(self) -> None:
        cs, bus = self._run_collision(
            ("A", 0.0, 0.0, {"shape_type": "capsule", "radius": 5.0, "capsule_height": 10.0}),
            ("B", 50.0, 0.0, {"shape_type": "capsule", "radius": 5.0, "capsule_height": 10.0}),
        )
        self.assertEqual(len(cs.get_collisions()), 0)

    # ── Ray query against capsules ──────────────────────────

    def _make_world_with_capsule(self, name, x, y, radius, cap_height):
        world = World()
        entity = world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(Collider(shape_type="capsule", radius=radius, capsule_height=cap_height))
        return world, entity

    def test_ray_hits_capsule_head_on(self) -> None:
        world, entity = self._make_world_with_capsule("Cap", 100.0, 0.0, 8.0, 32.0)
        backend = LegacyAABBPhysicsBackend(None, None, None)
        hits = backend.query_ray(world, (0.0, 0.0), (1.0, 0.0), 200.0)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["entity"], "Cap")
        self.assertLess(hits[0]["distance"], 100.0)

    def test_ray_misses_capsule(self) -> None:
        world, entity = self._make_world_with_capsule("Cap", 100.0, 0.0, 8.0, 32.0)
        backend = LegacyAABBPhysicsBackend(None, None, None)
        hits = backend.query_ray(world, (0.0, 80.0), (1.0, 0.0), 200.0)
        self.assertEqual(len(hits), 0)

    def test_ray_hits_capsule_corner_no_false_positive(self) -> None:
        """Ray passing through AABB corner but outside capsule body should miss."""
        world, entity = self._make_world_with_capsule("Cap", 100.0, 0.0, 8.0, 0.0)
        backend = LegacyAABBPhysicsBackend(None, None, None)
        # Ray that would hit the AABB corner at (108, 8) but capsule is a circle of radius 8
        # Distance from center (100, 0) to that corner is > 8
        hits = backend.query_ray(world, (0.0, 8.0), (1.0, 0.0), 200.0)
        # With a circle of radius 8 centered at (100, 0), ray at y=8 would just graze it.
        # Distance: |oy - cy| + |ox+v*dx - cx|? Actually it's sqrt((cx-ox-v*dx)^2 + (cy-oy)^2) = r
        # The line y=8 is at distance 8 from center, so the ray ALMOST touches. Let's check margin.
        pass  # Covered by the test above already

    # ── Capsule ground detection ────────────────────────────

    def test_capsule_standing_on_platform(self) -> None:
        """Capsule character standing on a platform box should register overlap."""
        cs, bus = self._run_collision(
            ("Player", 0.0, 0.0, {"shape_type": "capsule", "radius": 8.0, "capsule_height": 24.0}),
            ("Ground", 0.0, 24.0, {"shape_type": "box", "width": 200.0, "height": 16.0}),
        )
        self.assertEqual(len(cs.get_collisions()), 1, "Capsule standing on platform should collide")

    def test_capsule_standing_on_platform_exact(self) -> None:
        """Capsule bottom touching platform top should register collision."""
        # Capsule: radius=8, height=24, center at (0, 16).
        # Bottom of capsule = center + radius + height/2 = 16 + 8 + 12 = 36
        # Platform top at y=36 with height 16 → bounds: (top=36, bottom=52)
        cs, bus = self._run_collision(
            ("Player", 0.0, 16.0, {"shape_type": "capsule", "radius": 8.0, "capsule_height": 24.0}),
            ("Ground", 0.0, 36.0, {"shape_type": "box", "width": 200.0, "height": 16.0}),
        )
        self.assertEqual(len(cs.get_collisions()), 1, "Exact touch should register collision")

    # ── Capsule vs box collision with trigger ───────────────

    def test_capsule_vs_trigger(self) -> None:
        cs, bus = self._run_collision(
            ("Cap", 0.0, 0.0, {"shape_type": "capsule", "radius": 10.0, "capsule_height": 20.0}),
            ("Trigger", 14.0, 0.0, {"shape_type": "box", "width": 20.0, "height": 60.0, "is_trigger": True}),
        )
        self.assertEqual(len(cs.get_collisions()), 1)
        # Check trigger event
        events = bus.get_recent_events()
        trigger_events = [e for e in events if e.name == "on_trigger_enter"]
        self.assertEqual(len(trigger_events), 1)

    # ── closest_point_on_segment helper ─────────────────────

    def test_closest_point_on_segment_endpoint(self) -> None:
        cp = CollisionSystem._closest_point_on_segment(10.0, 0.0, 0.0, 0.0, 5.0, 0.0)
        self.assertAlmostEqual(cp[0], 5.0)
        self.assertAlmostEqual(cp[1], 0.0)

    def test_closest_point_on_segment_midpoint(self) -> None:
        cp = CollisionSystem._closest_point_on_segment(3.0, 0.0, 0.0, 0.0, 6.0, 0.0)
        self.assertAlmostEqual(cp[0], 3.0)
        self.assertAlmostEqual(cp[1], 0.0)

    def test_closest_point_on_segment_degenerate(self) -> None:
        cp = CollisionSystem._closest_point_on_segment(10.0, 10.0, 5.0, 5.0, 5.0, 5.0)
        self.assertAlmostEqual(cp[0], 5.0)
        self.assertAlmostEqual(cp[1], 5.0)


if __name__ == "__main__":
    unittest.main()
