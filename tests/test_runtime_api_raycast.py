"""tests/test_runtime_api_raycast.py — Tests for RuntimeAPI.get_raycast_result."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from engine.api._runtime_api import RuntimeAPI
from engine.components.raycast_2d import RayCast2D


class FakeContextWithWorld:
    """Contexto con runtime y world para testear get_raycast_result."""

    def __init__(self, world, runtime):
        self.api = MagicMock()
        self.api.game = runtime
        self._runtime = runtime
        self._world = world

    @property
    def runtime(self):
        return self._runtime

    @property
    def scene_authoring(self):
        return None

    def ok(self, message, data=None):
        return {"success": True, "message": message, "data": data}

    def fail(self, message):
        return {"success": False, "message": message, "data": None}


def _make_mock_entity(raycast: RayCast2D | None = None) -> MagicMock:
    entity = MagicMock()
    entity.get_component.return_value = raycast
    entity.name = "player"
    return entity


class TestRuntimeAPIRaycast(unittest.TestCase):
    """Tests for get_raycast_result method."""

    def setUp(self) -> None:
        self.raycast = RayCast2D()
        mock_entity = _make_mock_entity(self.raycast)

        mock_world = MagicMock()
        mock_world.get_entity_by_name.return_value = mock_entity

        mock_runtime = MagicMock()
        mock_runtime.world = mock_world

        self.ctx = FakeContextWithWorld(mock_world, mock_runtime)
        self.api = RuntimeAPI(self.ctx)

    def test_get_raycast_result_returns_dict(self) -> None:
        self.raycast.is_colliding = True
        self.raycast.collision_point_x = 42.0
        self.raycast.collision_point_y = 17.0
        self.raycast.collision_normal_x = -1.0
        self.raycast.collision_normal_y = 0.0
        self.raycast.collider_entity = "wall"

        result = self.api.get_raycast_result("player")

        self.assertIsInstance(result, dict)
        self.assertTrue(result["is_colliding"])
        self.assertEqual(result["collision_point_x"], 42.0)
        self.assertEqual(result["collision_point_y"], 17.0)
        self.assertEqual(result["collision_normal_x"], -1.0)
        self.assertEqual(result["collision_normal_y"], 0.0)
        self.assertEqual(result["collider_entity"], "wall")

    def test_get_raycast_result_not_colliding(self) -> None:
        self.raycast.is_colliding = False

        result = self.api.get_raycast_result("player")

        self.assertFalse(result["is_colliding"])

    def test_get_raycast_result_entity_not_found(self) -> None:
        mock_world = MagicMock()
        mock_world.get_entity_by_name.return_value = None
        mock_runtime = MagicMock()
        mock_runtime.world = mock_world

        ctx = FakeContextWithWorld(mock_world, mock_runtime)
        api = RuntimeAPI(ctx)

        result = api.get_raycast_result("nonexistent")
        self.assertEqual(result, {})

    def test_get_raycast_result_no_raycast_component(self) -> None:
        entity_no_rc = _make_mock_entity(raycast=None)
        mock_world = MagicMock()
        mock_world.get_entity_by_name.return_value = entity_no_rc
        mock_runtime = MagicMock()
        mock_runtime.world = mock_world

        ctx = FakeContextWithWorld(mock_world, mock_runtime)
        api = RuntimeAPI(ctx)

        result = api.get_raycast_result("no_rc")
        self.assertEqual(result, {})

    def test_get_raycast_result_no_runtime(self) -> None:
        ctx = FakeContextWithWorld(None, None)
        api = RuntimeAPI(ctx)
        result = api.get_raycast_result("player")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
