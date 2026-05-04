from __future__ import annotations

import unittest

from engine.components.collider import Collider
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend
from engine.physics.shapes import AABBShape, CapsuleShape, CircleShape, PolygonShape, ShapeFactory


class ShapeFactoryTests(unittest.TestCase):

    # ── AABB vs AABB ──────────────────────────────────────────────

    def test_aabb_vs_aabb_intersect(self) -> None:
        a = AABBShape(10, 10, 16, 16)
        b = AABBShape(30, 10, 16, 16)
        self.assertTrue(a.intersects_shape(b))

    def test_aabb_vs_aabb_no_intersect(self) -> None:
        a = AABBShape(10, 10, 16, 16)
        b = AABBShape(50, 10, 16, 16)
        self.assertFalse(a.intersects_shape(b))

    # ── Circle vs Circle ─────────────────────────────────────────

    def test_circle_vs_circle_intersect(self) -> None:
        a = CircleShape(0, 0, 10)
        b = CircleShape(10, 0, 10)
        self.assertTrue(a.intersects_shape(b))

    def test_circle_vs_circle_no_intersect(self) -> None:
        a = CircleShape(0, 0, 5)
        b = CircleShape(20, 0, 5)
        self.assertFalse(a.intersects_shape(b))

    # ── Circle vs AABB ───────────────────────────────────────────

    def test_circle_vs_aabb_intersect(self) -> None:
        c = CircleShape(0, 0, 5)
        b = AABBShape(6, 0, 2, 2)
        self.assertTrue(c.intersects_shape(b))

    def test_circle_vs_aabb_no_intersect(self) -> None:
        c = CircleShape(0, 0, 3)
        b = AABBShape(10, 0, 2, 2)
        self.assertFalse(c.intersects_shape(b))

    # ── Capsule vs AABB ──────────────────────────────────────────

    def test_capsule_vs_aabb_intersect(self) -> None:
        cap = CapsuleShape(0, 0, 5, 20)
        box = AABBShape(4, 0, 2, 2)
        self.assertTrue(cap.intersects_shape(box))

    def test_capsule_vs_aabb_no_intersect(self) -> None:
        cap = CapsuleShape(0, 0, 3, 10)
        box = AABBShape(20, 0, 2, 2)
        self.assertFalse(cap.intersects_shape(box))

    # ── Capsule vs Circle ────────────────────────────────────────

    def test_capsule_vs_circle_intersect(self) -> None:
        cap = CapsuleShape(0, 0, 5, 20)
        c = CircleShape(10, -10, 5)
        self.assertTrue(cap.intersects_shape(c))

    # ── ShapeFactory ─────────────────────────────────────────────

    def test_shape_factory_builds_correct_types(self) -> None:
        self.assertIsInstance(
            ShapeFactory.build(Collider(shape_type="box", width=32, height=32), 0, 0),
            AABBShape,
        )
        self.assertIsInstance(
            ShapeFactory.build(Collider(shape_type="circle", radius=16), 0, 0),
            CircleShape,
        )
        self.assertIsInstance(
            ShapeFactory.build(Collider(shape_type="capsule", radius=10, capsule_height=20), 0, 0),
            CapsuleShape,
        )

    # ── move_and_slide helpers ───────────────────────────────────

    def _make_entity(
        self, world: World, name: str, x: float, y: float, **collider_kwargs
    ) -> Entity:
        e = Entity(name=name)
        e.add_component(Transform(x=x, y=y))
        e.add_component(Collider(**collider_kwargs))
        world.add_entity(e)
        return e

    def _simulate(
        self,
        backend: LegacyAABBPhysicsBackend,
        world: World,
        entity: Entity,
        velocity: tuple[float, float],
        delta_time: float,
        max_frames: int = 200,
    ):
        result = None
        for _ in range(max_frames):
            result = backend.move_and_slide(entity, velocity, delta_time)
            if result.on_floor or result.on_wall or result.on_ceiling:
                break
        return result if result is not None else backend.move_and_slide(entity, velocity, delta_time)

    # ── move_and_slide: circle player ────────────────────────────

    def test_legacy_move_and_slide_circle_player(self) -> None:
        world = World()
        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)

        player = self._make_entity(world, "Player", 100, 100, shape_type="circle", radius=16)
        self._make_entity(world, "Floor", 100, 300, width=640, height=32)
        backend._last_world = world

        result = self._simulate(backend, world, player, velocity=(0, 200), delta_time=0.016)

        # Floor top = 300 - 16 = 284. Circle radius = 16 → center stops at 268.
        self.assertAlmostEqual(result.position_y, 268, places=0)
        self.assertTrue(result.on_floor)
        self.assertFalse(result.on_wall)
        self.assertFalse(result.on_ceiling)

    # ── move_and_slide: capsule player ───────────────────────────

    def test_legacy_move_and_slide_capsule_player(self) -> None:
        world = World()
        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)

        player = self._make_entity(
            world, "Player", 100, 100,
            shape_type="capsule", radius=10, capsule_height=20,
        )
        self._make_entity(world, "Floor", 100, 300, width=640, height=32)
        backend._last_world = world

        result = self._simulate(backend, world, player, velocity=(0, 200), delta_time=0.016)

        # Floor top = 284. Capsule bottom = cy + radius + capsule_height/2 = cy + 20.
        # → cy = 264.
        self.assertAlmostEqual(result.position_y, 264, places=0)
        self.assertTrue(result.on_floor)
        self.assertFalse(result.on_wall)
        self.assertFalse(result.on_ceiling)

    # ── Polygon vs AABB ───────────────────────────────────────────

    def test_polygon_vs_aabb_intersect(self) -> None:
        """Triángulo que intersecta un AABB."""
        poly = PolygonShape([(5, 0), (15, 20), (0, 10)])
        aabb = AABBShape(10, 5, 20, 15)
        self.assertTrue(poly.intersects_shape(aabb))

    def test_polygon_vs_aabb_no_intersect(self) -> None:
        """Triángulo lejos de un AABB."""
        poly = PolygonShape([(5, 0), (15, 20), (0, 10)])
        aabb = AABBShape(100, 100, 10, 10)
        self.assertFalse(poly.intersects_shape(aabb))

    # ── Polygon vs Circle ─────────────────────────────────────────

    def test_polygon_vs_circle_intersect(self) -> None:
        """Círculo dentro de un polígono."""
        poly = PolygonShape([(0, 0), (20, 0), (20, 20), (0, 20)])
        circle = CircleShape(10, 10, 5)
        self.assertTrue(circle.intersects_shape(poly))

    def test_polygon_vs_circle_no_intersect(self) -> None:
        """Círculo fuera del polígono."""
        poly = PolygonShape([(0, 0), (20, 0), (20, 20), (0, 20)])
        circle = CircleShape(50, 50, 5)
        self.assertFalse(circle.intersects_shape(poly))

    # ── ShapeFactory polygon ──────────────────────────────────────

    def test_shape_factory_builds_polygon(self) -> None:
        """ShapeFactory.build con shape_type='polygon'."""
        collider = Collider(shape_type="polygon", points=[[0, 0], [32, 0], [16, 32]])
        shape = ShapeFactory.build(collider, 100, 100)
        self.assertIsInstance(shape, PolygonShape)
        self.assertEqual(len(shape.vertices), 3)

    # ── Capsule vs Capsule ────────────────────────────────────────

    def test_capsule_vs_capsule_intersect_aligned(self) -> None:
        """Dos cápsulas verticales alineadas que se tocan."""
        a = CapsuleShape(100, 100, 10, 32)
        b = CapsuleShape(100, 115, 10, 32)
        self.assertTrue(a.intersects_shape(b))

    def test_capsule_vs_capsule_no_intersect(self) -> None:
        """Dos cápsulas separadas horizontalmente."""
        a = CapsuleShape(100, 100, 10, 32)
        b = CapsuleShape(200, 100, 10, 32)
        self.assertFalse(a.intersects_shape(b))


if __name__ == "__main__":
    unittest.main()
