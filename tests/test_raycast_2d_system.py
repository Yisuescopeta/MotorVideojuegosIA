"""tests/test_raycast_2d_system.py — Unit tests for RayCast2DSystem."""

from __future__ import annotations

import unittest

from engine.components.raycast_2d import RayCast2D
from engine.components.transform import Transform
from engine.ecs.world import World
from engine.systems.raycast_2d_system import RayCast2DSystem


class RayCast2DSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World()
        self.system = RayCast2DSystem()

    def _create_entity(self, name: str, cast_to_x: float = 50.0, cast_to_y: float = 0.0) -> tuple:
        entity = self.world.create_entity(name)
        entity.add_component(Transform(x=10.0, y=20.0))
        raycast = RayCast2D()
        raycast.cast_to_x = cast_to_x
        raycast.cast_to_y = cast_to_y
        entity.add_component(raycast)
        return entity, raycast

    def test_no_query_no_crash(self) -> None:
        self._create_entity("e1")
        self.system.update(self.world, 0.1)

    def test_hit_populates_fields(self) -> None:
        def mock_query(ox, oy, dx, dy, md):
            return [
                {
                    "point": {"x": 25.0, "y": 20.0},
                    "normal": {"x": -1.0, "y": 0.0},
                    "entity": "wall",
                }
            ]

        self.system.set_ray_cast_query(mock_query)
        _entity, raycast = self._create_entity("player")

        self.system.update(self.world, 0.1)

        self.assertTrue(raycast.is_colliding)
        self.assertEqual(raycast.collision_point_x, 25.0)
        self.assertEqual(raycast.collision_point_y, 20.0)
        self.assertEqual(raycast.collision_normal_x, -1.0)
        self.assertEqual(raycast.collision_normal_y, 0.0)
        self.assertEqual(raycast.collider_entity, "wall")

    def test_no_hit_resets_fields(self) -> None:
        def mock_query(ox, oy, dx, dy, md):
            return []

        _entity, raycast = self._create_entity("player")
        raycast.is_colliding = True
        raycast.collision_point_x = 99.0
        raycast.collider_entity = "old_wall"

        self.system.set_ray_cast_query(mock_query)
        self.system.update(self.world, 0.1)

        self.assertFalse(raycast.is_colliding)
        self.assertEqual(raycast.collision_point_x, 0.0)
        self.assertEqual(raycast.collision_point_y, 0.0)
        self.assertEqual(raycast.collision_normal_x, 0.0)
        self.assertEqual(raycast.collision_normal_y, 0.0)
        self.assertEqual(raycast.collider_entity, "")

    def test_disabled_skips(self) -> None:
        calls: list = []

        def mock_query(ox, oy, dx, dy, md):
            calls.append(1)
            return [{"point": {"x": 1.0, "y": 2.0}, "normal": {"x": 0.0, "y": 1.0}, "entity": "x"}]

        self.system.set_ray_cast_query(mock_query)
        _entity, raycast = self._create_entity("disabled_entity")
        raycast.enabled = False

        self.system.update(self.world, 0.1)

        self.assertEqual(len(calls), 0)
        self.assertFalse(raycast.is_colliding)

    def test_multiple_entities(self) -> None:
        hits_log: list[str] = []

        def mock_query(ox, oy, dx, dy, md):
            return [{"point": {"x": ox + dx, "y": oy + dy}, "normal": {"x": 0.0, "y": 0.0}, "entity": "hit"}]

        self.system.set_ray_cast_query(mock_query)

        e1, r1 = self._create_entity("e1", cast_to_x=10.0, cast_to_y=0.0)
        e2, r2 = self._create_entity("e2", cast_to_x=0.0, cast_to_y=30.0)
        e3, r3 = self._create_entity("e3", cast_to_x=5.0, cast_to_y=5.0)
        r3.enabled = False

        self.system.update(self.world, 0.1)

        self.assertTrue(r1.is_colliding)
        self.assertEqual(r1.collider_entity, "hit")

        self.assertTrue(r2.is_colliding)
        self.assertEqual(r2.collider_entity, "hit")

        self.assertFalse(r3.is_colliding)

    def test_init_with_query_fn(self) -> None:
        def mock_query(ox, oy, dx, dy, md):
            return [{"point": {"x": 0.0, "y": 0.0}, "normal": {"x": 0.0, "y": 0.0}, "entity": ""}]

        system = RayCast2DSystem(ray_cast_query=mock_query)
        _entity, raycast = self._create_entity("player")
        system.update(self.world, 0.1)
        self.assertTrue(raycast.is_colliding)

    def test_set_ray_cast_query_replaces(self) -> None:
        def first_query(ox, oy, dx, dy, md):
            return [{"point": {"x": 5.0, "y": 5.0}, "normal": {"x": 0.0, "y": 0.0}, "entity": "first"}]

        def second_query(ox, oy, dx, dy, md):
            return [{"point": {"x": 9.0, "y": 9.0}, "normal": {"x": 1.0, "y": 0.0}, "entity": "second"}]

        _entity, raycast = self._create_entity("player")

        self.system.set_ray_cast_query(first_query)
        self.system.update(self.world, 0.1)
        self.assertEqual(raycast.collider_entity, "first")

        self.system.set_ray_cast_query(second_query)
        self.system.update(self.world, 0.1)
        self.assertEqual(raycast.collider_entity, "second")


if __name__ == "__main__":
    unittest.main()
