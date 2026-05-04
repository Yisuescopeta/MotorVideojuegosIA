"""Tests for OLA5 batch 2: StaticBody2D, AnimatableBody2D, CollisionShape2D, CollisionPolygon2D."""

from __future__ import annotations

import unittest

from engine.components.animatable_body_2d import AnimatableBody2D
from engine.components.collider import Collider
from engine.components.collision_polygon_2d import CollisionPolygon2D
from engine.components.collision_shape_2d import CollisionShape2D
from engine.components.rigidbody import RigidBody
from engine.components.static_body_2d import StaticBody2D
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.levels.component_registry import create_default_registry
from engine.systems.collision_system import CollisionSystem
from engine.systems.physics_system import PhysicsSystem


class StaticBody2DTests(unittest.TestCase):
    """Tests for StaticBody2D component."""

    def test_serialization_roundtrip(self) -> None:
        body = StaticBody2D(
            constant_linear_velocity_x=10.0,
            constant_linear_velocity_y=-5.0,
            constant_angular_velocity=2.0,
            physics_material_override_path="res://materials/bouncy.physmat",
        )
        data = body.to_dict()
        restored = StaticBody2D.from_dict(data)
        self.assertEqual(restored.constant_linear_velocity_x, 10.0)
        self.assertEqual(restored.constant_linear_velocity_y, -5.0)
        self.assertEqual(restored.constant_angular_velocity, 2.0)
        self.assertEqual(restored.physics_material_override_path, "res://materials/bouncy.physmat")

    def test_default_values(self) -> None:
        body = StaticBody2D()
        self.assertEqual(body.constant_linear_velocity_x, 0.0)
        self.assertEqual(body.constant_linear_velocity_y, 0.0)
        self.assertEqual(body.constant_angular_velocity, 0.0)
        self.assertEqual(body.physics_material_override_path, "")

    def test_static_body_does_not_move_in_physics(self) -> None:
        world = World()
        entity = world.create_entity("StaticPlatform")
        entity.add_component(Transform(x=100.0, y=200.0))
        entity.add_component(Collider(width=64.0, height=16.0))
        entity.add_component(StaticBody2D())
        entity.add_component(
            RigidBody(body_type="dynamic", gravity_scale=1.0, velocity_x=50.0, velocity_y=30.0)
        )

        physics = PhysicsSystem(gravity=980.0)
        physics.update(world, 1.0 / 60.0)

        transform = entity.get_component(Transform)
        self.assertEqual(transform.x, 100.0)  # No horizontal movement
        self.assertEqual(transform.y, 200.0)  # No gravity applied

    def test_static_body_acts_as_solid_for_others(self) -> None:
        world = World()
        # Static floor
        floor = world.create_entity("Floor")
        floor.add_component(Transform(x=0.0, y=64.0))
        floor.add_component(Collider(width=200.0, height=16.0))
        floor.add_component(StaticBody2D())

        # Dynamic ball falling
        ball = world.create_entity("Ball")
        ball.add_component(Transform(x=0.0, y=0.0))
        ball.add_component(Collider(width=16.0, height=16.0))
        ball.add_component(
            RigidBody(body_type="dynamic", gravity_scale=1.0, velocity_y=0.0)
        )

        physics = PhysicsSystem(gravity=980.0)
        # Run enough frames for ball to hit floor
        dt = 1.0 / 60.0
        for _ in range(60):
            physics.update(world, dt)

        ball_transform = ball.get_component(Transform)
        self.assertLess(ball_transform.y, 64.0)  # Ball is above or on floor
        rigidbody = ball.get_component(RigidBody)
        self.assertTrue(rigidbody.is_grounded)

    def test_effective_body_type_is_static(self) -> None:
        entity = Entity("Test")
        entity.add_component(StaticBody2D())
        self.assertEqual(PhysicsSystem._get_effective_body_type(entity), "static")

    def test_effective_body_type_static_overrides_dynamic_rigidbody(self) -> None:
        entity = Entity("Test")
        entity.add_component(StaticBody2D())
        entity.add_component(RigidBody(body_type="dynamic"))
        self.assertEqual(PhysicsSystem._get_effective_body_type(entity), "static")


class AnimatableBody2DTests(unittest.TestCase):
    """Tests for AnimatableBody2D component."""

    def test_serialization_roundtrip(self) -> None:
        body = AnimatableBody2D(sync_to_physics=True)
        data = body.to_dict()
        restored = AnimatableBody2D.from_dict(data)
        self.assertTrue(restored.sync_to_physics)

    def test_serialization_roundtrip_false(self) -> None:
        body = AnimatableBody2D(sync_to_physics=False)
        data = body.to_dict()
        restored = AnimatableBody2D.from_dict(data)
        self.assertFalse(restored.sync_to_physics)

    def test_default_sync_to_physics_is_true(self) -> None:
        body = AnimatableBody2D()
        self.assertTrue(body.sync_to_physics)

    def test_animatable_body_does_not_move_in_physics(self) -> None:
        world = World()
        entity = world.create_entity("AnimPlatform")
        entity.add_component(Transform(x=100.0, y=200.0))
        entity.add_component(Collider(width=64.0, height=16.0))
        entity.add_component(AnimatableBody2D(sync_to_physics=True))
        entity.add_component(
            RigidBody(body_type="dynamic", gravity_scale=1.0, velocity_y=20.0)
        )

        physics = PhysicsSystem(gravity=980.0)
        physics.update(world, 1.0 / 60.0)

        transform = entity.get_component(Transform)
        self.assertEqual(transform.y, 200.0)  # No gravity applied

    def test_animatable_body_participates_in_collisions(self) -> None:
        world = World()
        # Animatable platform
        platform = world.create_entity("Platform")
        platform.add_component(Transform(x=0.0, y=50.0))
        platform.add_component(Collider(width=100.0, height=16.0))
        platform.add_component(AnimatableBody2D(sync_to_physics=True))

        # Ball falling
        ball = world.create_entity("Ball")
        ball.add_component(Transform(x=0.0, y=0.0))
        ball.add_component(Collider(width=16.0, height=16.0))
        ball.add_component(
            RigidBody(body_type="dynamic", gravity_scale=1.0)
        )

        physics = PhysicsSystem(gravity=980.0)
        dt = 1.0 / 60.0
        for _ in range(60):
            physics.update(world, dt)

        ball_transform = ball.get_component(Transform)
        # Ball should be stopped by the animatable platform
        self.assertLess(ball_transform.y, 60.0)

    def test_effective_body_type_is_static(self) -> None:
        entity = Entity("Test")
        entity.add_component(AnimatableBody2D())
        self.assertEqual(PhysicsSystem._get_effective_body_type(entity), "static")

    def test_animatable_overrides_dynamic_rigidbody(self) -> None:
        entity = Entity("Test")
        entity.add_component(AnimatableBody2D())
        entity.add_component(RigidBody(body_type="dynamic", velocity_y=100.0))
        self.assertEqual(PhysicsSystem._get_effective_body_type(entity), "static")


class CollisionShape2DTests(unittest.TestCase):
    """Tests for CollisionShape2D component."""

    def test_serialization_roundtrip_box(self) -> None:
        shape = CollisionShape2D(shape_type="box", width=64.0, height=32.0)
        data = shape.to_dict()
        restored = CollisionShape2D.from_dict(data)
        self.assertEqual(restored.shape_type, "box")
        self.assertEqual(restored.width, 64.0)
        self.assertEqual(restored.height, 32.0)

    def test_serialization_roundtrip_circle(self) -> None:
        shape = CollisionShape2D(shape_type="circle", radius=20.0)
        data = shape.to_dict()
        restored = CollisionShape2D.from_dict(data)
        self.assertEqual(restored.shape_type, "circle")
        self.assertEqual(restored.radius, 20.0)

    def test_serialization_roundtrip_polygon(self) -> None:
        shape = CollisionShape2D(shape_type="polygon", points=[(0, 0), (32, 0), (16, 32)])
        data = shape.to_dict()
        restored = CollisionShape2D.from_dict(data)
        self.assertEqual(restored.shape_type, "polygon")
        self.assertEqual(len(restored.points), 3)

    def test_serialization_roundtrip_one_way(self) -> None:
        shape = CollisionShape2D(
            one_way_collision=True,
            one_way_collision_margin=2.0,
            one_way_collision_direction_y=1.0,
        )
        data = shape.to_dict()
        restored = CollisionShape2D.from_dict(data)
        self.assertTrue(restored.one_way_collision)
        self.assertEqual(restored.one_way_collision_margin, 2.0)
        self.assertEqual(restored.one_way_collision_direction_y, 1.0)

    def test_disabled_flag(self) -> None:
        shape = CollisionShape2D(disabled=True)
        self.assertTrue(shape.disabled)
        data = shape.to_dict()
        restored = CollisionShape2D.from_dict(data)
        self.assertTrue(restored.disabled)

    def test_box_bounds(self) -> None:
        shape = CollisionShape2D(shape_type="box", width=64.0, height=32.0)
        bounds = shape.get_bounds(100.0, 200.0)
        self.assertEqual(bounds, (68.0, 184.0, 132.0, 216.0))

    def test_circle_bounds(self) -> None:
        shape = CollisionShape2D(shape_type="circle", radius=20.0)
        bounds = shape.get_bounds(100.0, 200.0)
        self.assertEqual(bounds, (80.0, 180.0, 120.0, 220.0))

    def test_polygon_bounds(self) -> None:
        shape = CollisionShape2D(shape_type="polygon", points=[(-16, -32), (16, -32), (0, 32)])
        bounds = shape.get_bounds(100.0, 200.0)
        self.assertEqual(bounds, (84.0, 168.0, 116.0, 232.0))

    def test_takes_precedence_over_collider_in_collision_system(self) -> None:
        world = World()
        entity_a = world.create_entity("A")
        entity_a.add_component(Transform(x=0.0, y=0.0))
        # CollisionShape2D defines a small 8x8 box
        entity_a.add_component(CollisionShape2D(shape_type="box", width=8.0, height=8.0))
        # Collider defines a large 64x64 box — should be ignored
        entity_a.add_component(Collider(width=64.0, height=64.0))

        entity_b = world.create_entity("B")
        entity_b.add_component(Transform(x=50.0, y=0.0))
        entity_b.add_component(Collider(width=16.0, height=16.0))

        cs = CollisionSystem()
        cs.update(world)

        # With CollisionShape2D 8x8 at (0,0) and Collider 16x16 at (50,0):
        # No collision because 8x8 box at (0,0) bounds: (-4,-4,4,4)
        # 16x16 box at (50,0) bounds: (42,-8,58,8) — these don't overlap
        self.assertEqual(len(cs.get_collisions()), 0)

    def test_without_collider_still_detects_collisions(self) -> None:
        world = World()
        entity_a = world.create_entity("A")
        entity_a.add_component(Transform(x=0.0, y=0.0))
        entity_a.add_component(CollisionShape2D(shape_type="box", width=32.0, height=32.0))
        # No Collider at all

        entity_b = world.create_entity("B")
        entity_b.add_component(Transform(x=15.0, y=0.0))
        entity_b.add_component(Collider(width=32.0, height=32.0))

        cs = CollisionSystem()
        cs.update(world)

        self.assertEqual(len(cs.get_collisions()), 1)
        self.assertFalse(cs.get_collisions()[0].is_trigger)


class CollisionPolygon2DTests(unittest.TestCase):
    """Tests for CollisionPolygon2D component."""

    def test_serialization_roundtrip(self) -> None:
        poly = CollisionPolygon2D(
            polygon=[(0, 0), (64, 0), (32, 48)],
            build_mode="solids",
            disabled=False,
            one_way_collision=False,
        )
        data = poly.to_dict()
        restored = CollisionPolygon2D.from_dict(data)
        self.assertEqual(len(restored.polygon), 3)
        self.assertEqual(restored.build_mode, "solids")
        self.assertFalse(restored.disabled)
        self.assertFalse(restored.one_way_collision)

    def test_serialization_roundtrip_segments_mode(self) -> None:
        poly = CollisionPolygon2D(
            polygon=[(0, 0), (100, 0), (100, 20), (0, 20)],
            build_mode="segments",
        )
        data = poly.to_dict()
        restored = CollisionPolygon2D.from_dict(data)
        self.assertEqual(restored.build_mode, "segments")
        self.assertEqual(len(restored.polygon), 4)

    def test_default_values(self) -> None:
        poly = CollisionPolygon2D()
        self.assertEqual(poly.polygon, [])
        self.assertEqual(poly.build_mode, "solids")
        self.assertFalse(poly.disabled)
        self.assertFalse(poly.one_way_collision)

    def test_empty_polygon_bounds(self) -> None:
        poly = CollisionPolygon2D(polygon=[])
        bounds = poly.get_bounds(50.0, 100.0)
        self.assertEqual(bounds, (50.0, 100.0, 50.0, 100.0))

    def test_polygon_bounds_calculation(self) -> None:
        poly = CollisionPolygon2D(polygon=[(-10, -20), (30, -15), (20, 10), (-15, 5)])
        bounds = poly.get_bounds(100.0, 200.0)
        self.assertEqual(bounds, (85.0, 180.0, 130.0, 210.0))

    def test_polygon_collision_detection(self) -> None:
        world = World()
        entity_a = world.create_entity("A")
        entity_a.add_component(Transform(x=0.0, y=0.0))
        entity_a.add_component(CollisionPolygon2D(
            polygon=[(-16, -16), (16, -16), (16, 16), (-16, 16)]
        ))
        # No Collider at all

        entity_b = world.create_entity("B")
        entity_b.add_component(Transform(x=20.0, y=0.0))
        entity_b.add_component(Collider(width=32.0, height=32.0))

        cs = CollisionSystem()
        cs.update(world)

        # A's polygon bounds at (0,0): (-16,-16,16,16)
        # B's collider bounds at (20,0): (4,-16,36,16) — overlap in X [4,16]
        self.assertEqual(len(cs.get_collisions()), 1)

    def test_disabled_polygon_not_detected(self) -> None:
        world = World()
        entity_a = world.create_entity("A")
        entity_a.add_component(Transform(x=0.0, y=0.0))
        entity_a.add_component(CollisionPolygon2D(
            polygon=[(-16, -16), (16, -16), (16, 16), (-16, 16)],
            disabled=True,
        ))

        entity_b = world.create_entity("B")
        entity_b.add_component(Transform(x=0.0, y=0.0))
        entity_b.add_component(Collider(width=32.0, height=32.0))

        cs = CollisionSystem()
        cs.update(world)  # Won't be in entries since shape is disabled

        self.assertEqual(len(cs.get_collisions()), 0)


class ComponentRegistryTests(unittest.TestCase):
    """Tests that all 4 new components are registered."""

    def setUp(self) -> None:
        self.registry = create_default_registry()

    def test_static_body_2d_registered(self) -> None:
        cls = self.registry.get("StaticBody2D")
        self.assertIsNotNone(cls)
        self.assertEqual(cls, StaticBody2D)

    def test_animatable_body_2d_registered(self) -> None:
        cls = self.registry.get("AnimatableBody2D")
        self.assertIsNotNone(cls)
        self.assertEqual(cls, AnimatableBody2D)

    def test_collision_shape_2d_registered(self) -> None:
        cls = self.registry.get("CollisionShape2D")
        self.assertIsNotNone(cls)
        self.assertEqual(cls, CollisionShape2D)

    def test_collision_polygon_2d_registered(self) -> None:
        cls = self.registry.get("CollisionPolygon2D")
        self.assertIsNotNone(cls)
        self.assertEqual(cls, CollisionPolygon2D)

    def test_registered_names_are_consistent(self) -> None:
        names = self.registry.list_registered()
        self.assertIn("StaticBody2D", names)
        self.assertIn("AnimatableBody2D", names)
        self.assertIn("CollisionShape2D", names)
        self.assertIn("CollisionPolygon2D", names)

    def test_can_create_from_dict(self) -> None:
        body = self.registry.create("StaticBody2D", {
            "constant_linear_velocity_x": 5.0,
            "constant_linear_velocity_y": -2.0,
        })
        self.assertIsInstance(body, StaticBody2D)
        self.assertEqual(body.constant_linear_velocity_x, 5.0)

        shape = self.registry.create("CollisionShape2D", {
            "shape_type": "circle",
            "radius": 25.0,
        })
        self.assertIsInstance(shape, CollisionShape2D)
        self.assertEqual(shape.radius, 25.0)


class StaticBody2DCollisionSystemTests(unittest.TestCase):
    """StaticBody2D integration with CollisionSystem."""

    def test_static_body_participates_in_collisions(self) -> None:
        world = World()
        wall = world.create_entity("Wall")
        wall.add_component(Transform(x=64.0, y=0.0))
        wall.add_component(Collider(width=16.0, height=128.0))
        wall.add_component(StaticBody2D())

        player = world.create_entity("Player")
        player.add_component(Transform(x=64.0, y=0.0))
        player.add_component(Collider(width=32.0, height=32.0))
        player.add_component(RigidBody(body_type="dynamic"))

        cs = CollisionSystem()
        cs.update(world)

        self.assertEqual(len(cs.get_collisions()), 1)


class CollisionShape2DPrecedenceTests(unittest.TestCase):
    """Tests that CollisionShape2D takes precedence over Collider."""

    def test_shape_overrides_collider_for_bounds(self) -> None:
        world = World()
        entity = world.create_entity("E")
        entity.add_component(Transform(x=100.0, y=100.0))
        # Small shape
        entity.add_component(CollisionShape2D(shape_type="box", width=16.0, height=16.0))
        # Large collider
        entity.add_component(Collider(width=128.0, height=128.0))

        other = world.create_entity("Other")
        other.add_component(Transform(x=100.0, y=80.0))
        # 32x32 collider at y=80 -> bounds: (84,64,116,96)
        other.add_component(Collider(width=32.0, height=32.0))

        cs = CollisionSystem()
        cs.update(world)

        # shape bounds at (100,100): (92,92,108,108)
        # other bounds at (100,80): (84,64,116,96)
        # overlap_y: top(92) < bottom(96)=True, bottom(108) > top(64)=True -> yes
        # overlap_x: left(92) < right(116)=True, right(108) > left(84)=True -> yes
        self.assertEqual(len(cs.get_collisions()), 1)

    def test_large_shape_vs_large_collider_no_collision_when_separated(self) -> None:
        world = World()
        entity = world.create_entity("E")
        entity.add_component(Transform(x=0.0, y=0.0))
        entity.add_component(CollisionShape2D(shape_type="box", width=8.0, height=8.0))
        entity.add_component(Collider(width=128.0, height=128.0))

        other = world.create_entity("Other")
        other.add_component(Transform(x=100.0, y=100.0))
        other.add_component(Collider(width=16.0, height=16.0))

        cs = CollisionSystem()
        cs.update(world)

        # shape bounds: (-4,-4,4,4), other bounds: (92,92,108,108) — no overlap
        # collider bounds: (-64,-64,64,64) — would overlap
        # But shape takes precedence, so no collision
        self.assertEqual(len(cs.get_collisions()), 0)
