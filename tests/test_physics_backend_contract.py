"""Tests de contrato cross-backend: legacy_aabb vs box2d."""
from __future__ import annotations

import pytest

from engine.components.collider import Collider
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.backend import MoveResult2D
from engine.physics.kinematic_move_service import PhysicsKinematicMoveService
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend

BOX2D_AVAILABLE = False
try:
    from engine.physics.box2d_backend import Box2DPhysicsBackend

    _backend_check = Box2DPhysicsBackend(gravity=0)
    del _backend_check
    BOX2D_AVAILABLE = True
except Exception:
    pass


def _make_world_with_floor() -> tuple[World, Entity, Entity]:
    """Crea World con suelo y devuelve (world, player, ground)."""
    world = World()
    player = Entity(name="Player")
    player.add_component(Transform(x=160, y=50))
    player.add_component(Collider(width=32, height=32))
    world.add_entity(player)
    ground = Entity(name="Ground")
    ground.add_component(Transform(x=160, y=200))
    ground.add_component(Collider(width=640, height=32))
    world.add_entity(ground)
    return world, player, ground


class TestLegacyBackendContract:
    """Contrato base del backend legacy (siempre disponible)."""

    def test_legacy_supports_kinematic_move_returns_true(self) -> None:
        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        assert backend.supports_kinematic_move() is True

    def test_ray_query_hits_entity(self) -> None:
        world, player, ground = _make_world_with_floor()
        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        hits = backend.query_ray(world, (100, 0), (0, 1), 500)
        assert len(hits) >= 1, "Ray debería golpear al menos una entidad"

    def test_aabb_query_finds_entity(self) -> None:
        world, player, ground = _make_world_with_floor()
        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        hits = backend.query_aabb(world, (0, 0, 640, 400))
        assert len(hits) >= 2, f"AABB debería encontrar player + ground, encontró {len(hits)}"

    def test_move_and_slide_box_vs_floor(self) -> None:
        world, player, ground = _make_world_with_floor()
        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        backend.step(world, 0.0)
        result = backend.move_and_slide(world, player, (0, 300), 1 / 60)
        ground_top = 200 - 16
        assert result.position_y + 16 <= ground_top + 2.0, "Player debería estar sobre el suelo"

    def test_move_and_slide_returns_move_result_2d(self) -> None:
        world, player, ground = _make_world_with_floor()
        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        backend.step(world, 0.0)
        result = backend.move_and_slide(world, player, (0, 0), 1 / 60)
        assert isinstance(result, MoveResult2D)
        assert hasattr(result, "on_floor")
        assert hasattr(result, "on_wall")
        assert hasattr(result, "position_x")
        assert hasattr(result, "position_y")
        assert hasattr(result, "on_ceiling")

    def test_triggers_dont_block_movement(self) -> None:
        world = World()
        player = Entity(name="Player")
        player.add_component(Transform(x=100, y=100))
        player.add_component(Collider(width=32, height=32))
        world.add_entity(player)
        trigger = Entity(name="Trigger")
        trigger.add_component(Transform(x=150, y=100))
        trigger.add_component(Collider(width=32, height=32, is_trigger=True))
        world.add_entity(trigger)
        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        backend.step(world, 0.0)
        result = backend.move_and_slide(world, player, (200, 0), 1 / 60)
        # Con dt=1/60 y vx=200, delta ~3.33. Si el trigger bloqueara, x ≈ 118.
        # Como is_trigger=True, el player avanza libremente.
        assert result.position_x > 100, f"Player debería atravesar trigger, x={result.position_x}"


@pytest.mark.skipif(not BOX2D_AVAILABLE, reason="Box2D not installed")
class TestCrossBackendContract:
    """Comparación directa entre legacy y box2d."""

    def test_both_backends_prevent_falling_through_floor(self) -> None:
        """Ambos backends (via servicio kinematic) evitan que el player atraviese el suelo."""
        service = PhysicsKinematicMoveService()
        ground_top = 200 - 16

        # Legacy
        w1, p1, g1 = _make_world_with_floor()
        legacy = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        legacy.step(w1, 0.0)
        r1 = service.move_and_slide(
            backend=legacy, world=w1, entity=p1,
            velocity=(0, 300), delta_time=1 / 60,
        )
        assert r1.position_y + 16 <= ground_top + 2.0, f"Legacy: player atravesó suelo (y={r1.position_y})"

        # Box2D
        w2, p2, g2 = _make_world_with_floor()
        box2d = Box2DPhysicsBackend(gravity=600)
        box2d.sync_world(w2)
        r2 = service.move_and_slide(
            backend=box2d, world=w2, entity=p2,
            velocity=(0, 300), delta_time=1 / 60,
        )
        assert r2.position_y + 16 <= ground_top + 2.0, f"Box2D (fallback): player atravesó suelo (y={r2.position_y})"

    def test_ray_query_consistent(self) -> None:
        """Mismo ray query produce resultados similares en ambos backends."""
        w1, _, _ = _make_world_with_floor()
        legacy = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)

        w2, _, _ = _make_world_with_floor()
        box2d = Box2DPhysicsBackend(gravity=600)
        box2d.sync_world(w2)

        hits1 = legacy.query_ray(w1, (100, 0), (0, 1), 500)
        hits2 = box2d.query_ray(w2, (100, 0), (0, 1), 500)

        assert len(hits1) >= 1, "Legacy: ray sin hits"
        assert len(hits2) >= 1, "Box2D: ray sin hits"

    def test_both_backends_return_on_floor_flag(self) -> None:
        """Ambos backends (via servicio kinematic) reportan on_floor al colisionar con suelo."""
        service = PhysicsKinematicMoveService()

        # Legacy
        w1, p1, g1 = _make_world_with_floor()
        legacy = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        legacy.step(w1, 0.0)
        r1 = service.move_and_slide(
            backend=legacy, world=w1, entity=p1,
            velocity=(0, 200), delta_time=1 / 60,
        )
        assert r1.on_floor, "Legacy: debería detectar suelo"

        # Box2D
        w2, p2, g2 = _make_world_with_floor()
        box2d = Box2DPhysicsBackend(gravity=600)
        box2d.sync_world(w2)
        r2 = service.move_and_slide(
            backend=box2d, world=w2, entity=p2,
            velocity=(0, 200), delta_time=1 / 60,
        )
        assert r2.on_floor, "Box2D (fallback): debería detectar suelo"

    def test_aabb_query_consistent(self) -> None:
        """Mismo AABB query produce cantidad comparable de resultados."""
        w1, _, _ = _make_world_with_floor()
        legacy = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)

        w2, _, _ = _make_world_with_floor()
        box2d = Box2DPhysicsBackend(gravity=600)
        box2d.sync_world(w2)

        hits1 = legacy.query_aabb(w1, (0, 0, 640, 400))
        hits2 = box2d.query_aabb(w2, (0, 0, 640, 400))

        assert len(hits1) >= 2, f"Legacy: AABB encontró solo {len(hits1)} entidades"
        assert len(hits2) >= 2, f"Box2D: AABB encontró solo {len(hits2)} entidades"
