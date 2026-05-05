import unittest

from engine.physics.shapes import AABBShape, CapsuleShape, CircleShape, ShapeInstance
from engine.physics.swept_collision import swept_shape_toi


class SweptCollisionBoxVsBoxTests(unittest.TestCase):
    def _target_box(self, cx: float = 100.0, cy: float = 0.0, hw: float = 16.0, hh: float = 32.0) -> AABBShape:
        return AABBShape(cx, cy, hw, hh)

    def _sweep_params(self, width: float = 16.0, height: float = 16.0) -> dict:
        return {"width": width, "height": height}

    def _sweep(
        self,
        target: ShapeInstance,
        origin: tuple[float, float] = (0.0, 0.0),
        direction: tuple[float, float] = (1.0, 0.0),
        max_dist: float = 200.0,
        shape_type: str = "box",
        shape_params: dict | None = None,
        epsilon: float = 0.001,
    ):
        return swept_shape_toi(
            shape_type=shape_type,
            shape_params=shape_params or self._sweep_params(),
            origin=origin,
            direction=direction,
            max_distance=max_dist,
            target_shape=target,
            target_info={"entity": "Wall", "entity_id": 1, "is_trigger": False},
            epsilon=epsilon,
        )

    def test_precise_fraction_box_vs_box(self) -> None:
        target = self._target_box(cx=100.0, cy=0.0, hw=16.0, hh=32.0)
        # Sweep shape is 16x16 box from (0,0) going right. It hits at target_left - sweep_half_w = 100-16-8 = 76
        # Sweep half_w = 8, target left = 84, so hit at 84 - 8 = 76
        hit = self._sweep(target, origin=(0.0, 0.0), direction=(1.0, 0.0), max_dist=200.0)
        self.assertIsNotNone(hit)
        self.assertTrue(hit["hit"])
        self.assertAlmostEqual(hit["fraction"], 76.0 / 200.0, delta=0.01)
        self.assertAlmostEqual(hit["position"]["x"], 76.0, delta=1.0)

    def test_overlap_at_origin_returns_zero_fraction(self) -> None:
        target = self._target_box(cx=0.0, cy=0.0, hw=32.0, hh=32.0)
        hit = self._sweep(target, origin=(0.0, 0.0), direction=(1.0, 0.0), max_dist=100.0)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["fraction"], 0.0)

    def test_no_hit_returns_none(self) -> None:
        target = self._target_box(cx=500.0, cy=0.0, hw=16.0, hh=32.0)
        hit = self._sweep(target, origin=(0.0, 0.0), direction=(1.0, 0.0), max_dist=100.0)
        self.assertIsNone(hit)

    def test_circle_vs_box(self) -> None:
        target = self._target_box(cx=100.0, cy=0.0, hw=16.0, hh=32.0)
        hit = self._sweep(
            target,
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_dist=200.0,
            shape_type="circle",
            shape_params={"radius": 8.0},
        )
        self.assertIsNotNone(hit)
        self.assertGreater(hit["fraction"], 0.0)
        self.assertLess(hit["fraction"], 1.0)

    def test_capsule_vs_box(self) -> None:
        target = self._target_box(cx=100.0, cy=0.0, hw=16.0, hh=32.0)
        hit = self._sweep(
            target,
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_dist=200.0,
            shape_type="capsule",
            shape_params={"radius": 8.0, "height": 16.0},
        )
        self.assertIsNotNone(hit)
        self.assertGreater(hit["fraction"], 0.0)

    def test_normal_precise(self) -> None:
        target = self._target_box(cx=100.0, cy=0.0, hw=16.0, hh=32.0)
        hit = self._sweep(target, origin=(0.0, 0.0), direction=(1.0, 0.0), max_dist=200.0)
        self.assertIsNotNone(hit)
        normal = hit["normal"]
        self.assertIn("x", normal)
        self.assertIn("y", normal)
        # Should have a non-zero normal
        self.assertTrue(abs(normal["x"]) > 0.0 or abs(normal["y"]) > 0.0)

    def test_epsilon_convergence(self) -> None:
        target = self._target_box(cx=100.0, cy=0.0, hw=16.0, hh=32.0)
        # Tight epsilon
        hit_tight = self._sweep(target, origin=(0.0, 0.0), direction=(1.0, 0.0), max_dist=200.0, epsilon=0.0001)
        # Loose epsilon
        hit_loose = self._sweep(target, origin=(0.0, 0.0), direction=(1.0, 0.0), max_dist=200.0, epsilon=0.1)
        self.assertIsNotNone(hit_tight)
        self.assertIsNotNone(hit_loose)
        # Both should be reasonable
        self.assertLess(abs(hit_tight["fraction"] - hit_loose["fraction"]), 0.05)

    def test_grazing_edge(self) -> None:
        # Thin wall at y=32, sweep barely clips edge
        target = AABBShape(100.0, 32.0, 16.0, 1.0)
        hit = self._sweep(
            target,
            origin=(0.0, 0.0),
            direction=(1.0, 0.0),
            max_dist=200.0,
            shape_params={"width": 16.0, "height": 16.0},
        )
        # Sweep box is 16 tall centered at 0: top=8, bottom=-8. Wall at y=32, hh=1: top=33, bottom=31.
        # No collision since 8 < 31.
        self.assertIsNone(hit)

    def test_returns_entity_data(self) -> None:
        target = self._target_box(cx=100.0, cy=0.0, hw=16.0, hh=32.0)
        hit = self._sweep(target, origin=(0.0, 0.0), direction=(1.0, 0.0), max_dist=200.0)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["entity"], "Wall")
        self.assertEqual(hit["entity_id"], 1)
        self.assertFalse(hit["is_trigger"])

    def test_zero_direction_overlaps_at_origin(self) -> None:
        target = self._target_box(cx=5.0, cy=0.0, hw=32.0, hh=32.0)
        hit = self._sweep(target, origin=(0.0, 0.0), direction=(0.0, 0.0), max_dist=100.0)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["fraction"], 0.0)

    def test_zero_direction_no_overlap_returns_none(self) -> None:
        target = self._target_box(cx=500.0, cy=0.0, hw=16.0, hh=32.0)
        hit = self._sweep(target, origin=(0.0, 0.0), direction=(0.0, 0.0), max_dist=100.0)
        self.assertIsNone(hit)


if __name__ == "__main__":
    unittest.main()
