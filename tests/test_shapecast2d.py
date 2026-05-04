import unittest

from engine.components.collider import Collider
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend


class ShapeCast2DTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.backend = LegacyAABBPhysicsBackend(None, None, None)

    def _create_wall(self, name: str, x: float, y: float, w: float = 32.0, h: float = 64.0) -> None:
        entity = self.world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(Collider(width=w, height=h))
        self.backend.create_shape(entity)

    def test_box_cast_hits_static_collider(self) -> None:
        self._create_wall("Wall", x=100.0, y=0.0)
        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="box",
            shape_size=(16.0, 16.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0]["entity"] == "Wall")
        self.assertLess(hits[0]["fraction"], 1.0)

    def test_circle_cast_hits_collider(self) -> None:
        self._create_wall("Wall", x=100.0, y=0.0)
        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="circle",
            shape_size=(16.0, 16.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["entity"], "Wall")

    def test_no_hit_in_opposite_direction(self) -> None:
        self._create_wall("Wall", x=100.0, y=0.0)
        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="box",
            shape_size=(16.0, 16.0),
            origin=(0.0, 0.0),
            direction=(-1.0, 0.0),
            max_distance=200.0,
        )
        self.assertEqual(len(hits), 0)

    def test_returns_first_hit(self) -> None:
        self._create_wall("NearWall", x=50.0, y=0.0, w=32.0, h=64.0)
        self._create_wall("FarWall", x=150.0, y=0.0, w=32.0, h=64.0)
        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="box",
            shape_size=(16.0, 16.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["entity"], "NearWall")

    def test_zero_distance_detects_immediate_overlap(self) -> None:
        self._create_wall("Wall", x=0.0, y=0.0, w=64.0, h=64.0)
        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="box",
            shape_size=(16.0, 16.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=100.0,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["fraction"], 0.0)

    def test_disabled_collider_ignored(self) -> None:
        entity = self.world.create_entity("DisabledWall")
        entity.add_component(Transform(x=100.0, y=0.0))
        collider = Collider(width=32.0, height=64.0)
        collider.enabled = False
        entity.add_component(collider)
        self.backend.create_shape(entity)

        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="box",
            shape_size=(16.0, 16.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertEqual(len(hits), 0)

    def test_normal_computed_from_aabb_overlap(self) -> None:
        self._create_wall("Wall", x=100.0, y=0.0, w=32.0, h=200.0)
        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="box",
            shape_size=(16.0, 16.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertEqual(len(hits), 1)
        normal = hits[0]["normal"]
        self.assertIn(normal["x"], (-1.0, 1.0))
        self.assertTrue(normal["x"] != 0.0 or normal["y"] != 0.0)


if __name__ == "__main__":
    unittest.main()
