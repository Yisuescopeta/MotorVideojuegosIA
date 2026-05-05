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

    def _create_capsule(self, name: str, x: float, y: float, radius: float = 8.0, height: float = 16.0) -> None:
        entity = self.world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(Collider(shape_type="capsule", radius=radius, capsule_height=height, width=radius * 2, height=height + radius * 2))
        self.backend.create_shape(entity)

    def _create_polygon(self, name: str, x: float, y: float, verts: list[list[float]]) -> None:
        entity = self.world.create_entity(name)
        entity.add_component(Transform(x=x, y=y))
        entity.add_component(Collider(shape_type="polygon", points=verts, width=32.0, height=32.0))
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

    # --- New tests: swept collision real ---

    def test_capsule_cast_hits_wall(self) -> None:
        self._create_wall("Wall", x=100.0, y=0.0)
        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="capsule",
            shape_size=(16.0, 32.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
            shape_params={"radius": 8.0, "height": 16.0},
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["entity"], "Wall")
        self.assertGreater(hits[0]["fraction"], 0.0)

    def test_polygon_cast_hits_wall(self) -> None:
        self._create_wall("Wall", x=100.0, y=0.0)
        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="polygon",
            shape_size=(32.0, 32.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
            shape_params={"vertices": [(-8.0, -8.0), (8.0, -8.0), (8.0, 8.0), (-8.0, 8.0)]},
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["entity"], "Wall")

    def test_fraction_not_quantized(self) -> None:
        self._create_wall("Wall", x=100.0, y=0.0, w=32.0, h=64.0)
        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="box",
            shape_size=(16.0, 16.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        fract = hits[0]["fraction"]
        # Should not be one of the old 20-step quantized values
        quantized_steps = [i / 20.0 for i in range(21)]
        for q in quantized_steps:
            self.assertNotAlmostEqual(fract, q, delta=0.001)

    def test_thin_wall_1px(self) -> None:
        self._create_wall("ThinWall", x=100.0, y=0.0, w=1.0, h=64.0)
        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="box",
            shape_size=(16.0, 16.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["entity"], "ThinWall")

    def test_normal_from_swept_collision(self) -> None:
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
        # Normal should point back toward sweep origin (against sweep direction)
        self.assertAlmostEqual(abs(normal["x"]), 1.0, delta=0.1)

    def test_capsule_shaped_target_hit(self) -> None:
        self._create_capsule("CapTarget", x=100.0, y=0.0, radius=8.0, height=16.0)
        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="box",
            shape_size=(16.0, 16.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["entity"], "CapTarget")

    def test_polygon_shaped_target_hit(self) -> None:
        self._create_polygon("PolyTarget", x=100.0, y=0.0, verts=[(-8.0, -8.0), (8.0, -8.0), (8.0, 8.0), (-8.0, 8.0)])
        hits = self.backend.query_shape_cast(
            self.world,
            shape_type="box",
            shape_size=(16.0, 16.0),
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_distance=200.0,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["entity"], "PolyTarget")


if __name__ == "__main__":
    unittest.main()
