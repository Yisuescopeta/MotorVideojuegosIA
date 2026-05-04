from __future__ import annotations

import unittest

from engine.components.collider import Collider
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.physics.backend import MoveResult2D
from engine.physics.legacy_backend import LegacyAABBPhysicsBackend


def _make_entity(
    world: World,
    name: str,
    x: float,
    y: float,
    w: float = 32.0,
    h: float = 32.0,
    is_trigger: bool = False,
) -> Entity:
    entity = Entity(name=name)
    entity.add_component(Transform(x=x, y=y))
    entity.add_component(Collider(width=w, height=h, is_trigger=is_trigger))
    world.add_entity(entity)
    return entity


def _simulate(
    backend: LegacyAABBPhysicsBackend,
    world: World,
    entity: Entity,
    velocity: tuple[float, float],
    delta_time: float,
    max_frames: int = 200,
    **kwargs,
) -> MoveResult2D:
    result: MoveResult2D | None = None
    for _ in range(max_frames):
        result = backend.move_and_slide(world, entity, velocity, delta_time, **kwargs)
        if result.on_floor or result.on_wall or result.on_ceiling:
            break
    return result if result is not None else backend.move_and_slide(world, entity, velocity, delta_time)


class MoveAndSlideTests(unittest.TestCase):

    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
    # Helpers
    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

    def setUp(self) -> None:
        self.world = World()
        self.backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)

    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
    # Test 1: box vs floor (falling)
    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

    def test_move_and_slide_box_vs_floor(self) -> None:
        player = _make_entity(self.world, "Player", 100.0, 100.0, w=32.0, h=32.0)
        _make_entity(self.world, "Floor", 320.0, 350.0, w=640.0, h=32.0)

        result = _simulate(
            self.backend, self.world, player,
            velocity=(0.0, 200.0), delta_time=0.016,
        )

        # player bottom (center.y + 16) should meet floor top (334)
        # so center.y ≈ 318, near floor top 334 − half_height 16
        self.assertAlmostEqual(result.position_y, 318.0, places=0)
        self.assertTrue(result.on_floor)
        self.assertFalse(result.on_wall)
        self.assertFalse(result.on_ceiling)

    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
    # Test 2: box vs wall right
    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

    def test_move_and_slide_box_vs_wall_right(self) -> None:
        player = _make_entity(self.world, "Player", 100.0, 100.0, w=32.0, h=32.0)
        _make_entity(self.world, "Wall", 200.0, 100.0, w=32.0, h=128.0)

        result = _simulate(
            self.backend, self.world, player,
            velocity=(200.0, 0.0), delta_time=0.016,
        )

        # player right = center.x + 16 should hit wall left = 200 - 16 = 184
        # so center.x ≈ 168
        self.assertAlmostEqual(result.position_x, 168.0, places=0)
        self.assertTrue(result.on_wall)
        self.assertFalse(result.on_floor)
        self.assertFalse(result.on_ceiling)

    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
    # Test 3: box vs wall left
    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

    def test_move_and_slide_box_vs_wall_left(self) -> None:
        player = _make_entity(self.world, "Player", 200.0, 100.0, w=32.0, h=32.0)
        _make_entity(self.world, "Wall", 100.0, 100.0, w=32.0, h=128.0)

        result = _simulate(
            self.backend, self.world, player,
            velocity=(-200.0, 0.0), delta_time=0.016,
        )

        # player left = center.x - 16 should hit wall right = 100 + 16 = 116
        # so center.x ≈ 132
        self.assertAlmostEqual(result.position_x, 132.0, places=0)
        self.assertTrue(result.on_wall)
        self.assertFalse(result.on_floor)
        self.assertFalse(result.on_ceiling)

    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
    # Test 4: box vs ceiling
    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

    def test_move_and_slide_box_vs_ceiling(self) -> None:
        player = _make_entity(self.world, "Player", 100.0, 100.0, w=32.0, h=32.0)
        _make_entity(self.world, "Ceiling", 100.0, 0.0, w=640.0, h=32.0)

        result = _simulate(
            self.backend, self.world, player,
            velocity=(0.0, -300.0), delta_time=0.016,
        )

        # player top = center.y - 16 should hit ceiling bottom = 0 + 16 = 16
        # so center.y ≈ 32
        self.assertAlmostEqual(result.position_y, 32.0, places=0)
        self.assertTrue(result.on_ceiling)
        self.assertFalse(result.on_floor)
        self.assertFalse(result.on_wall)

    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
    # Test 5: no collision (free movement)
    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

    def test_move_and_slide_no_collision(self) -> None:
        player = _make_entity(self.world, "Player", 100.0, 100.0, w=32.0, h=32.0)

        dt = 0.016
        result = self.backend.move_and_slide(
            self.world, player, velocity=(100.0, 50.0), delta_time=dt,
        )

        self.assertAlmostEqual(result.position_x, 100.0 + 100.0 * dt, places=4)
        self.assertAlmostEqual(result.position_y, 100.0 + 50.0 * dt, places=4)
        self.assertFalse(result.on_floor)
        self.assertFalse(result.on_wall)
        self.assertFalse(result.on_ceiling)

    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
    # Test 6: trigger ignored (passes through)
    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

    def test_move_and_slide_trigger_ignored(self) -> None:
        player = _make_entity(self.world, "Player", 100.0, 100.0, w=32.0, h=32.0)
        _make_entity(self.world, "Trigger", 200.0, 100.0, w=32.0, h=128.0, is_trigger=True)

        dt = 0.016
        result = self.backend.move_and_slide(
            self.world, player, velocity=(200.0, 0.0), delta_time=dt,
        )

        # trigger should not block — player moves freely
        self.assertAlmostEqual(result.position_x, 100.0 + 200.0 * dt, places=4)
        self.assertFalse(result.on_wall)
        self.assertFalse(result.on_floor)
        self.assertFalse(result.on_ceiling)

    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
    # Test 7: floor snap
    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

    def test_move_and_slide_floor_snap(self) -> None:
        player = _make_entity(self.world, "Player", 100.0, 318.0, w=32.0, h=32.0)
        _make_entity(self.world, "Floor", 320.0, 350.0, w=640.0, h=32.0)

        # 1. land on floor to set was_on_floor flag
        result1 = self.backend.move_and_slide(
            self.world, player, velocity=(0.0, 200.0), delta_time=0.016,
            floor_snap_distance=4.0,
        )
        self.assertTrue(result1.on_floor)
        self.assertTrue(getattr(player, "_move_slide_was_on_floor", False))

        # 2. nudge player up 2px — bottom at 332, gap to floor top (334) = 2 ≤ snap 4
        player.get_component(Transform).y -= 2.0  # y → 316

        # 3. next frame with zero velocity — floor snap should pull player back
        result2 = self.backend.move_and_slide(
            self.world, player, velocity=(0.0, 0.0), delta_time=0.016,
            floor_snap_distance=4.0,
        )

        # snapped back to y ≈ 318 (bottom = 334 = floor top)
        self.assertAlmostEqual(result2.position_y, 318.0, places=0)
        self.assertTrue(result2.on_floor)
        self.assertFalse(result2.on_wall)
        self.assertFalse(result2.on_ceiling)

    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
    # Test 8: move_and_collide stops at first hit
    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––

    def test_move_and_collide_stops_at_first_hit(self) -> None:
        player = _make_entity(self.world, "Player", 100.0, 100.0, w=32.0, h=32.0)
        _make_entity(self.world, "Wall", 200.0, 100.0, w=32.0, h=128.0)

        result = _simulate(
            self.backend, self.world, player,
            velocity=(200.0, 0.0), delta_time=0.016,
        )

        # player should stop before penetrating wall (same as move_and_slide)
        self.assertAlmostEqual(result.position_x, 168.0, places=0)
        self.assertTrue(result.on_wall)
        self.assertFalse(result.on_floor)
        self.assertFalse(result.on_ceiling)


# ──────────────────────────────────────────────────────────────
# Box2D tests — solo ejecutan si Box2D instalado
# ──────────────────────────────────────────────────────────────
from unittest import mock

import pytest

try:
    from engine.physics.box2d_backend import Box2DPhysicsBackend

    _backend_check = Box2DPhysicsBackend(gravity=0)
    del _backend_check
    BOX2D_AVAILABLE = True
except Exception:
    BOX2D_AVAILABLE = False


class KinematicFallbackTests(unittest.TestCase):
    """Punto 2: servicio kinematic redirige a legacy cuando backend no soporta o es None."""

    def test_kinematic_service_handles_none_backend(self) -> None:
        """PhysicsKinematicMoveService no crashea con backend=None."""
        from engine.physics.kinematic_move_service import PhysicsKinematicMoveService

        world = World()
        player = Entity(name="Player")
        player.add_component(Transform(x=160, y=50))
        player.add_component(Collider(width=32, height=32))
        world.add_entity(player)

        ground = Entity(name="Ground")
        ground.add_component(Transform(x=160, y=200))
        ground.add_component(Collider(width=640, height=32))
        world.add_entity(ground)

        service = PhysicsKinematicMoveService()
        result = service.move_and_slide(
            backend=None, world=world, entity=player,
            velocity=(0, 300), delta_time=1 / 60,
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, MoveResult2D)
        self.assertLess(
            result.position_y, 200,
            f"Fallback legacy debería funcionar con backend=None, y={result.position_y}",
        )

    def test_kinematic_service_falls_back_to_legacy_when_backend_unsupported(self) -> None:
        """PhysicsKinematicMoveService usa legacy cuando backend no soporta."""
        from engine.physics.kinematic_move_service import PhysicsKinematicMoveService

        world = World()
        player = Entity(name="Player")
        player.add_component(Transform(x=160, y=50))
        player.add_component(Collider(width=32, height=32))
        world.add_entity(player)

        ground = Entity(name="Ground")
        ground.add_component(Transform(x=160, y=200))
        ground.add_component(Collider(width=640, height=32))
        world.add_entity(ground)

        backend = LegacyAABBPhysicsBackend(physics_system=None, collision_system=None)
        with mock.patch.object(
            backend, "supports_kinematic_move", return_value=False,
        ):
            service = PhysicsKinematicMoveService()
            result = service.move_and_slide(
                backend=backend, world=world, entity=player,
                velocity=(0, 300), delta_time=1 / 60,
            )
            self.assertLess(
                result.position_y, 200,
                f"Fallback debería funcionar, y={result.position_y}",
            )


@pytest.mark.skipif(not BOX2D_AVAILABLE, reason="Box2D not installed")
class TestBox2DKinematicMove:
    """Verifica que Box2D NO soporta kinematic move y que el servicio redirige a legacy."""

    def test_box2d_does_not_support_kinematic_move(self) -> None:
        """Box2D backend debe devolver False en supports_kinematic_move."""
        backend = Box2DPhysicsBackend(gravity=600)
        assert not backend.supports_kinematic_move(), \
            "Box2D no debe soportar kinematic move directamente"

    def test_box2d_move_and_slide_raises_not_implemented(self) -> None:
        """Llamar move_and_slide directamente en Box2D debe lanzar NotImplementedError."""
        world = World()
        player = Entity(name="Player")
        player.add_component(Transform(x=160, y=0))
        player.add_component(Collider(width=32, height=32))
        world.add_entity(player)

        backend = Box2DPhysicsBackend(gravity=600)
        backend.sync_world(world)

        with pytest.raises(NotImplementedError):
            backend.move_and_slide(
                world, player, velocity=(0, 300), delta_time=1 / 60,
            )

    def test_kinematic_service_falls_back_to_legacy_for_box2d(self) -> None:
        """El servicio usa legacy solver cuando el backend no soporta kinematic move."""
        from engine.physics.kinematic_move_service import PhysicsKinematicMoveService

        world = World()
        player = Entity(name="Player")
        player.add_component(Transform(x=160, y=100))
        player.add_component(Collider(width=32, height=32))
        world.add_entity(player)

        ground = Entity(name="Ground")
        ground.add_component(Transform(x=160, y=200))
        ground.add_component(Collider(width=640, height=32))
        world.add_entity(ground)

        backend = Box2DPhysicsBackend(gravity=600)
        backend.sync_world(world)

        service = PhysicsKinematicMoveService()

        # Debe usar legacy porque Box2D no soporta kinematic move
        result = service.move_and_slide(
            backend=backend,
            world=world,
            entity=player,
            velocity=(0, 300),
            delta_time=1 / 60,
        )

        player_bottom = result.position_y + 16
        ground_top = 200 - 16
        assert player_bottom <= ground_top + 2.0, \
            f"Player atravesó suelo: {player_bottom} > {ground_top}"


if __name__ == "__main__":
    unittest.main()
