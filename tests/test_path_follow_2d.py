"""tests/test_path_follow_2d.py — Tests for Curve2D, PathFollower2D component and PathFollowSystem."""

from __future__ import annotations

import math
import unittest

from engine.components.path_follower_2d import PathFollower2D
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.resources.curve_2d import Curve2D
from engine.systems.path_follow_system import PathFollowSystem


class TestCurve2DMath(unittest.TestCase):
    """Tests for Curve2D: bezier sampling, baking, length, closest point."""

    def test_empty_curve_defaults(self):
        curve = Curve2D()
        self.assertEqual(curve.point_count, 0)
        self.assertEqual(curve.get_baked_length(), 0.0)
        self.assertEqual(curve.get_baked_points(), [])

    def test_single_point_curve(self):
        curve = Curve2D()
        curve.add_point((100, 200))
        self.assertEqual(curve.point_count, 1)
        result = curve.sample_baked(0)
        self.assertAlmostEqual(result["x"], 100)
        self.assertAlmostEqual(result["y"], 200)

    def test_straight_line_bezier(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((100, 0))
        x, y = curve.sample(0, 0.5)
        self.assertAlmostEqual(x, 50, delta=1e-6)
        self.assertAlmostEqual(y, 0, delta=1e-6)

    def test_straight_line_with_handles(self):
        curve = Curve2D()
        curve.add_point((0, 0), out_vec=(50, 0))
        curve.add_point((100, 0), in_vec=(-50, 0))
        x, y = curve.sample(0, 0.5)
        self.assertAlmostEqual(x, 50, delta=1e-6)
        self.assertAlmostEqual(y, 0, delta=1e-6)

    def test_samplef_multi_segment(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((100, 0))
        curve.add_point((200, 100))
        x, y = curve.samplef(0.5)
        self.assertAlmostEqual(x, 50, delta=1e-6)
        self.assertAlmostEqual(y, 0, delta=1e-6)
        x, y = curve.samplef(1.5)
        self.assertAlmostEqual(x, 150, delta=1e-6)
        self.assertAlmostEqual(y, 50, delta=1e-6)

    def test_add_remove_clear_points(self):
        curve = Curve2D()
        curve.add_point((10, 20))
        curve.add_point((30, 40), index=0)
        self.assertEqual(curve.point_count, 2)
        self.assertEqual(curve.get_points()[0]["x"], 30)

        curve.remove_point(0)
        self.assertEqual(curve.point_count, 1)
        self.assertEqual(curve.get_points()[0]["x"], 10)

        curve.clear_points()
        self.assertEqual(curve.point_count, 0)

    def test_bake_straight_line(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((300, 400))
        baked = curve.get_baked_points()
        self.assertGreaterEqual(len(baked), 2)
        self.assertAlmostEqual(baked[0]["x"], 0)
        self.assertAlmostEqual(baked[0]["y"], 0)
        self.assertAlmostEqual(baked[-1]["x"], 300)
        self.assertAlmostEqual(baked[-1]["y"], 400)

    def test_baked_length(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((300, 0))
        curve.add_point((300, 400))
        length = curve.get_baked_length()
        self.assertAlmostEqual(length, 700, delta=5.0)

    def test_sample_baked_midpoint(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((200, 0))
        length = curve.get_baked_length()
        result = curve.sample_baked(length / 2)
        self.assertAlmostEqual(result["x"], 100, delta=1.0)
        self.assertAlmostEqual(result["y"], 0, delta=1.0)

    def test_sample_baked_cubic(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((100, 0))
        curve.add_point((200, 0))
        curve.add_point((300, 0))
        length = curve.get_baked_length()
        result = curve.sample_baked(length / 2, cubic=True)
        self.assertAlmostEqual(result["x"], 150, delta=1.0)
        self.assertAlmostEqual(result["y"], 0, delta=1.0)

    def test_closest_point(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((100, 0))
        best = curve.get_closest_point((50, 10))
        self.assertAlmostEqual(best["x"], 50, delta=5)
        self.assertAlmostEqual(best["y"], 0, delta=5)

    def test_closest_offset(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((200, 0))
        offset = curve.get_closest_offset((150, 5))
        self.assertAlmostEqual(offset, 150, delta=10)

    def test_forward_vector(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((100, 0))
        fwd = curve.get_forward_vector(50)
        self.assertAlmostEqual(fwd["x"], 1.0, delta=1e-3)
        self.assertAlmostEqual(fwd["y"], 0.0, delta=1e-3)

    def test_forward_vector_vertical(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((0, 100))
        fwd = curve.get_forward_vector(50)
        self.assertAlmostEqual(fwd["x"], 0.0, delta=1e-3)
        self.assertAlmostEqual(fwd["y"], 1.0, delta=1e-3)

    def test_serialization_roundtrip(self):
        curve = Curve2D()
        curve.add_point((10, 20), out_vec=(30, -5))
        curve.add_point((100, 200), in_vec=(-20, 10))
        data = curve.to_dict()
        restored = Curve2D.from_dict(data)
        self.assertEqual(restored.point_count, 2)
        self.assertEqual(restored.get_points()[0]["x"], 10)
        self.assertEqual(restored.get_points()[0]["out_x"], 30)
        self.assertEqual(restored.get_points()[1]["in_y"], 10)
        self.assertAlmostEqual(restored.bake_interval, 5.0)

    def test_single_point_forward(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        fwd = curve.get_forward_vector(0)
        self.assertAlmostEqual(fwd["x"], 1.0)
        self.assertAlmostEqual(fwd["y"], 0.0)

    def test_no_points_forward(self):
        curve = Curve2D()
        fwd = curve.get_forward_vector(0)
        self.assertAlmostEqual(fwd["x"], 1.0)
        self.assertAlmostEqual(fwd["y"], 0.0)


class TestPathFollower2DSerialization(unittest.TestCase):
    """Tests for PathFollower2D component to_dict / from_dict."""

    def test_default_serialization(self):
        pf = PathFollower2D()
        data = pf.to_dict()
        self.assertEqual(data["speed"], 80.0)
        self.assertTrue(data["loop"])
        self.assertTrue(data["cubic_interp"])
        self.assertTrue(data["rotates"])
        self.assertTrue(data["start_active"])

    def test_serialization_with_curve(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((100, 100))
        pf = PathFollower2D(curve=curve, speed=120, loop=False)
        data = pf.to_dict()
        self.assertEqual(data["speed"], 120)
        self.assertFalse(data["loop"])
        self.assertIsNotNone(data["curve"])
        self.assertEqual(len(data["curve"]["points"]), 2)

    def test_deserialization_roundtrip(self):
        curve = Curve2D()
        curve.add_point((10, 20), out_vec=(5, 5))
        curve.add_point((200, 300), in_vec=(-5, -5))
        pf = PathFollower2D(curve=curve, speed=150, loop=False, rotates=False, h_offset=10, v_offset=-5)
        pf.progress = 42.0
        data = pf.to_dict()
        restored = PathFollower2D.from_dict(data)
        self.assertEqual(restored.speed, 150)
        self.assertFalse(restored.loop)
        self.assertFalse(restored.rotates)
        self.assertEqual(restored.h_offset, 10)
        self.assertEqual(restored.v_offset, -5)
        self.assertEqual(restored.progress, 42.0)
        self.assertIsNotNone(restored.curve)
        self.assertEqual(restored.curve.point_count, 2)

    def test_deserialization_none_curve(self):
        pf = PathFollower2D.from_dict({"speed": 50, "loop": False, "curve": None})
        self.assertIsNone(pf.curve)
        self.assertEqual(pf.speed, 50)

    def test_progress_ratio(self):
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((100, 0))
        pf = PathFollower2D(curve=curve)
        self.assertAlmostEqual(pf.progress_ratio, 0.0)
        pf.progress = pf.curve.get_baked_length() / 2
        self.assertAlmostEqual(pf.progress_ratio, 0.5, delta=0.01)
        pf.progress_ratio = 0.25
        self.assertAlmostEqual(pf.progress, pf.curve.get_baked_length() * 0.25, delta=1.0)

    def test_progress_ratio_none_curve(self):
        pf = PathFollower2D(curve=None)
        self.assertAlmostEqual(pf.progress_ratio, 0.0)
        pf.progress_ratio = 0.5
        self.assertAlmostEqual(pf.progress, 0.0)
        self.assertAlmostEqual(pf.progress_ratio, 0.0)


class TestPathFollowSystem(unittest.TestCase):
    """Integration tests for PathFollowSystem + PathFollower2D + Transform."""

    def setUp(self):
        self.world = World()
        self.system = PathFollowSystem()
        self.event_bus = _MockEventBus()

    def _make_follower_entity(
        self,
        name: str = "Follower1",
        x: float = 0.0,
        y: float = 0.0,
        speed: float = 80.0,
        loop: bool = True,
        rotates: bool = False,
        cubic: bool = False,
    ) -> tuple[Entity, Transform, PathFollower2D]:
        entity = self.world.create_entity(name=name)
        transform = Transform(x=x, y=y)
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((200, 0))
        curve.add_point((200, 200))
        follower = PathFollower2D(curve=curve, speed=speed, loop=loop, rotates=rotates, cubic_interp=cubic)
        entity.add_component(transform)
        entity.add_component(follower)
        return entity, transform, follower

    def test_basic_movement(self):
        _, transform, _ = self._make_follower_entity(speed=100, loop=False)
        self.system.update(self.world, 0.5, self.event_bus)
        self.assertAlmostEqual(transform.x, 50, delta=5)
        self.assertAlmostEqual(transform.y, 0, delta=5)

    def test_movement_two_steps(self):
        _, transform, _ = self._make_follower_entity(speed=100, loop=False)
        self.system.update(self.world, 0.5, self.event_bus)
        x1 = transform.x
        self.system.update(self.world, 0.5, self.event_bus)
        x2 = transform.x
        self.assertGreater(x2, x1)

    def test_loop_wrapping(self):
        entity, transform, follower = self._make_follower_entity(speed=500, loop=True)
        self.system.update(self.world, 5.0, self.event_bus)
        curve_length = follower.curve.get_baked_length()
        self.assertLess(follower.progress, curve_length)
        self.assertTrue(0 <= transform.x <= 210)
        self.assertTrue(0 <= transform.y <= 210)

    def test_loop_event_emitted(self):
        entity, _, follower = self._make_follower_entity(speed=1000, loop=True)
        self.system.update(self.world, 1.0, self.event_bus)
        loops = [e for e in self.event_bus.events if e["name"] == "path_follower_loop"]
        self.assertGreater(len(loops), 0)
        self.assertEqual(loops[0]["data"]["entity"], entity.name)

    def test_non_loop_completed_event(self):
        entity, _, follower = self._make_follower_entity(speed=1000, loop=False)
        self.system.update(self.world, 10.0, self.event_bus)
        completed = [e for e in self.event_bus.events if e["name"] == "path_follower_completed"]
        self.assertGreater(len(completed), 0)
        self.assertEqual(completed[0]["data"]["entity"], entity.name)
        event_count = len(self.event_bus.events)
        self.system.update(self.world, 10.0, self.event_bus)
        self.assertEqual(len(self.event_bus.events), event_count)

    def test_rotation_alignment(self):
        _, transform, _ = self._make_follower_entity(speed=100, loop=False, rotates=True)
        self.system.update(self.world, 0.5, self.event_bus)
        self.assertAlmostEqual(transform.rotation, 0.0, delta=0.1)

    def test_rotation_vertical(self):
        entity = self.world.create_entity(name="VertFollower")
        transform = Transform(x=0, y=0)
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((0, 200))
        follower = PathFollower2D(curve=curve, speed=100, loop=False, rotates=True)
        entity.add_component(transform)
        entity.add_component(follower)
        self.system.update(self.world, 0.5, self.event_bus)
        self.assertAlmostEqual(transform.rotation, math.pi / 2, delta=0.15)

    def test_offset_lateral(self):
        """h_offset=30 should move entity perpendicular to the right of forward."""
        entity = self.world.create_entity(name="SideFollower")
        transform = Transform(x=0, y=0)
        curve = Curve2D()
        curve.add_point((0, 0))
        curve.add_point((200, 0))
        follower = PathFollower2D(curve=curve, speed=100, loop=False, h_offset=30, v_offset=0)
        entity.add_component(transform)
        entity.add_component(follower)
        self.system.update(self.world, 0.5, self.event_bus)
        # Forward=(1,0), lateral perpendicular = (-fy, fx) = (0, 1) = DOWN
        # h_offset=30 * (0, 1) = (0, 30)
        self.assertAlmostEqual(transform.y, 30, delta=5)

    def test_offset_forward(self):
        """v_offset=50 should move entity along the forward direction."""
        entity = self.world.create_entity(name="FwdFollower")
        transform = Transform(x=0, y=0)
        curve = Curve2D()
        curve.add_point((0, 100))
        curve.add_point((0, 300))
        follower = PathFollower2D(curve=curve, speed=100, loop=False, h_offset=0, v_offset=50)
        entity.add_component(transform)
        entity.add_component(follower)
        self.system.update(self.world, 0.5, self.event_bus)
        # Forward=(0,1) downward, base position ~(0, 150), v_offset=50 along forward
        # Position = (0, 150) + (0,1)*50 = (0, 200)
        self.assertAlmostEqual(transform.y, 200, delta=10)

    def test_disabled_skips(self):
        _, transform, follower = self._make_follower_entity(speed=100)
        follower.enabled = False
        self.system.update(self.world, 1.0, self.event_bus)
        self.assertAlmostEqual(transform.x, 0.0)
        self.assertAlmostEqual(transform.y, 0.0)

    def test_no_curve_skips(self):
        entity = self.world.create_entity(name="NoCurve")
        transform = Transform(x=0, y=0)
        follower = PathFollower2D(curve=None, speed=100)
        entity.add_component(transform)
        entity.add_component(follower)
        self.system.update(self.world, 1.0, self.event_bus)
        self.assertAlmostEqual(transform.x, 0.0)
        self.assertAlmostEqual(transform.y, 0.0)

    def test_less_than_two_points_skips(self):
        entity = self.world.create_entity(name="OnePoint")
        transform = Transform(x=0, y=0)
        curve = Curve2D()
        curve.add_point((100, 100))
        follower = PathFollower2D(curve=curve, speed=100)
        entity.add_component(transform)
        entity.add_component(follower)
        self.system.update(self.world, 1.0, self.event_bus)
        self.assertAlmostEqual(transform.x, 0.0)
        self.assertAlmostEqual(transform.y, 0.0)

    def test_zero_speed_manual_progress(self):
        entity, transform, follower = self._make_follower_entity(speed=0, loop=False)
        follower.progress = 50
        self.system.update(self.world, 1.0, self.event_bus)
        self.assertAlmostEqual(transform.x, 50, delta=5)
        self.assertAlmostEqual(transform.y, 0, delta=5)

    def test_system_reset(self):
        entity, _, follower = self._make_follower_entity(speed=1000, loop=False)
        self.system.update(self.world, 5.0, self.event_bus)
        self.assertEqual(len(self.event_bus.events), 1)
        self.system.reset()
        follower.progress = 0
        self.system.update(self.world, 5.0, self.event_bus)
        completed = [e for e in self.event_bus.events if e["name"] == "path_follower_completed"]
        self.assertGreaterEqual(len(completed), 2)

    def test_default_curve_is_none(self):
        pf = PathFollower2D()
        self.assertIsNone(pf.curve)


class _MockEventBus:
    def __init__(self):
        self.events: list[dict] = []

    def emit(self, name: str, data: dict) -> None:
        self.events.append({"name": name, "data": data})


if __name__ == "__main__":
    unittest.main()
