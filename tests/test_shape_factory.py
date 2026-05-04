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
            result = backend.move_and_slide(world, entity, velocity, delta_time)
            if result.on_floor or result.on_wall or result.on_ceiling:
                break
        return result if result is not None else backend.move_and_slide(world, entity, velocity, delta_time)

    # ── move_and_slide: circle player ────────────────────────────

    def test_legacy_move_and_slide_circle_player(self) -> None:
        world = World()
        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)

        player = self._make_entity(world, "Player", 100, 100, shape_type="circle", radius=16)
        self._make_entity(world, "Floor", 100, 300, width=640, height=32)

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

    # ── collide_shape retorna normal y depth ─────────────────────

    def test_collide_shape_returns_manifold_with_normal_and_depth(self) -> None:
        """collide_shape() devuelve ContactManifold2D con normal y depth."""
        a = AABBShape(10, 10, 16, 16)
        b = AABBShape(30, 10, 16, 16)
        manifold = a.collide_shape(b)
        self.assertIsNotNone(manifold, "Deberían colisionar")
        self.assertGreater(
            manifold.depth, 0, f"Depth debería ser > 0, es {manifold.depth}",
        )
        self.assertTrue(
            abs(manifold.normal_x) > 0 or abs(manifold.normal_y) > 0,
            f"Normal no debería ser (0,0), es ({manifold.normal_x}, {manifold.normal_y})",
        )

    def test_circle_collide_aabb_returns_correct_normal(self) -> None:
        """Círculo colisionando con AABB devuelve normal correcta."""
        circle = CircleShape(50, 50, 20)
        aabb = AABBShape(100, 50, 30, 30)
        manifold = circle.collide_shape(aabb)
        self.assertIsNotNone(manifold)
        # La normal debe apuntar del círculo hacia fuera (hacia la izquierda aquí)
        self.assertTrue(
            manifold.normal_x < 0 or manifold.normal_y != 0,
            f"Normal debería apuntar fuera del círculo: "
            f"({manifold.normal_x}, {manifold.normal_y})",
        )

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

    # ── AABB manifold normal directions ───────────────────────────

    def test_aabb_manifold_normal_left(self) -> None:
        """AABB colisionando por la izquierda → normal no nula."""
        a = AABBShape(10, 10, 16, 16)
        b = AABBShape(30, 10, 16, 16)
        m = a.collide_shape(b)
        assert m is not None
        assert m.depth > 0
        assert abs(m.normal_x) > 0 or abs(m.normal_y) > 0, (
            f"Normal no nula: ({m.normal_x}, {m.normal_y})"
        )

    def test_aabb_manifold_normal_right(self) -> None:
        """AABB colisionando por la derecha."""
        a = AABBShape(50, 10, 16, 16)
        b = AABBShape(30, 10, 16, 16)
        m = a.collide_shape(b)
        assert m is not None
        assert m.depth > 0

    def test_aabb_manifold_normal_top(self) -> None:
        """AABB colisionando por arriba."""
        a = AABBShape(10, 10, 16, 16)
        b = AABBShape(10, 30, 16, 16)
        m = a.collide_shape(b)
        assert m is not None
        assert m.depth > 0

    def test_aabb_manifold_normal_bottom(self) -> None:
        """AABB colisionando por abajo."""
        a = AABBShape(10, 50, 16, 16)
        b = AABBShape(10, 30, 16, 16)
        m = a.collide_shape(b)
        assert m is not None
        assert m.depth > 0

    # ── Circle manifold depth ─────────────────────────────────────

    def test_circle_collide_circle_positive_depth(self) -> None:
        """Dos círculos solapados → depth > 0."""
        a = CircleShape(10, 10, 20)
        b = CircleShape(30, 10, 20)
        m = a.collide_shape(b)
        assert m is not None
        assert m.depth > 0
        assert m.contact_count >= 1

    # ── Capsule approximate manifold ──────────────────────────────

    def test_capsule_manifold_is_approximate(self) -> None:
        """Cápsula vs AABB: manifold existe pero es aproximado."""
        a = CapsuleShape(10, 10, 8, 32)
        b = AABBShape(30, 10, 16, 16)
        m = a.collide_shape(b)
        assert m is not None, "Cápsula debería detectar colisión con AABB"
        assert m.contact_count >= 1

    # ── Polygon SAT manifold ──────────────────────────────────────

    def test_polygon_sat_manifold_exists(self) -> None:
        """Polígono vs AABB vía SAT → manifold existe con depth > 0."""
        poly = PolygonShape([(5, 0), (15, 20), (0, 10)])
        aabb = AABBShape(10, 5, 20, 15)
        m = poly.collide_shape(aabb)
        assert m is not None, "SAT debería detectar colisión"
        assert m.depth > 0, f"Depth debería ser > 0, es {m.depth}"

    # ── No collision → None ───────────────────────────────────────

    def test_no_collision_returns_none(self) -> None:
        """Shapes separadas → collide_shape retorna None."""
        a = AABBShape(0, 0, 10, 10)
        b = AABBShape(100, 100, 10, 10)
        assert a.collide_shape(b) is None
        c = CircleShape(0, 0, 5)
        d = CircleShape(100, 0, 5)
        assert c.collide_shape(d) is None

    # ── intersects_shape wrapper ──────────────────────────────────

    def test_intersects_shape_still_works(self) -> None:
        """intersects_shape() sigue siendo wrapper válido de collide_shape()."""
        a = AABBShape(10, 10, 16, 16)
        b = AABBShape(30, 10, 16, 16)
        assert a.intersects_shape(b)
        c = AABBShape(100, 100, 10, 10)
        assert not a.intersects_shape(c)


if __name__ == "__main__":
    unittest.main()
