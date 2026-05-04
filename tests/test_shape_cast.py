import unittest

from engine.components.collider import Collider
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend


class ShapeCastTests(unittest.TestCase):
    def _make_world(self) -> World:
        return World()

    def _make_wall(self, world: World, name: str, x: float, y: float, w: float, h: float) -> Entity:
        entity = world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(Collider(width=w, height=h))
        return entity

    def _make_backend(self, world: World) -> LegacyAABBPhysicsBackend:
        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        backend.sync_world(world)
        return backend

    def test_box_cast_hits_wall(self) -> None:
        world = self._make_world()
        self._make_wall(world, "Wall", x=100.0, y=0.0, w=32.0, h=64.0)
        backend = self._make_backend(world)

        hits = backend.query_shape_cast(
            world,
            shape_type="box",
            shape_size=(32.0, 32.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["entity"], "Wall")

    def test_box_cast_clear_path(self) -> None:
        world = self._make_world()
        self._make_wall(world, "Wall", x=300.0, y=0.0, w=32.0, h=64.0)
        backend = self._make_backend(world)

        hits = backend.query_shape_cast(
            world,
            shape_type="box",
            shape_size=(32.0, 32.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertEqual(len(hits), 0)

    def test_circle_cast_hits_wall(self) -> None:
        world = self._make_world()
        self._make_wall(world, "Wall", x=80.0, y=0.0, w=32.0, h=64.0)
        backend = self._make_backend(world)

        hits = backend.query_shape_cast(
            world,
            shape_type="circle",
            shape_size=(16.0, 16.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertGreaterEqual(len(hits), 1)

    def test_shape_cast_returns_fraction(self) -> None:
        world = self._make_world()
        self._make_wall(world, "Wall", x=100.0, y=0.0, w=32.0, h=64.0)
        backend = self._make_backend(world)

        hits = backend.query_shape_cast(
            world,
            shape_type="box",
            shape_size=(32.0, 32.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=500.0,
        )
        self.assertGreaterEqual(len(hits), 1)
        self.assertIn("fraction", hits[0])
        self.assertGreater(hits[0]["fraction"], 0.0)
        self.assertLessEqual(hits[0]["fraction"], 1.0)

    def test_shape_cast_returns_normal(self) -> None:
        world = self._make_world()
        self._make_wall(world, "Wall", x=100.0, y=0.0, w=32.0, h=64.0)
        backend = self._make_backend(world)

        hits = backend.query_shape_cast(
            world,
            shape_type="box",
            shape_size=(32.0, 32.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertGreaterEqual(len(hits), 1)
        self.assertIn("normal", hits[0])
        self.assertIn("x", hits[0]["normal"])
        self.assertIn("y", hits[0]["normal"])

    def test_shape_cast_returns_position(self) -> None:
        world = self._make_world()
        self._make_wall(world, "Wall", x=100.0, y=0.0, w=32.0, h=64.0)
        backend = self._make_backend(world)

        hits = backend.query_shape_cast(
            world,
            shape_type="box",
            shape_size=(32.0, 32.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertGreaterEqual(len(hits), 1)
        self.assertIn("position", hits[0])
        self.assertIn("x", hits[0]["position"])
        self.assertIn("y", hits[0]["position"])

    def test_zero_direction_returns_empty(self) -> None:
        world = self._make_world()
        self._make_wall(world, "Wall", x=100.0, y=0.0, w=32.0, h=64.0)
        backend = self._make_backend(world)

        hits = backend.query_shape_cast(
            world,
            shape_type="box",
            shape_size=(32.0, 32.0),
            origin=(0.0, 0.0),
            direction=(0.0, 0.0),
            max_distance=200.0,
        )
        self.assertEqual(len(hits), 0)

    def test_cast_upward_hits_ceiling(self) -> None:
        world = self._make_world()
        self._make_wall(world, "Ceiling", x=0.0, y=-100.0, w=200.0, h=16.0)
        backend = self._make_backend(world)

        hits = backend.query_shape_cast(
            world,
            shape_type="box",
            shape_size=(32.0, 32.0),
            origin=(0.0, 0.0),
            direction=(0.0, -1.0),
            max_distance=200.0,
        )
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0]["entity"], "Ceiling")
