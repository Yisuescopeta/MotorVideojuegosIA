"""PhysicsKinematicMoveService — Fachada para movimiento kinematic character.

Encapsula la decisión: backend.move_and_slide() vs legacy solver AABB.
CharacterControllerSystem no guarda backend como estado permanente.
"""

from __future__ import annotations
from typing import Any, Optional
from engine.physics.backend import MoveResult2D, PhysicsBackend


class PhysicsKinematicMoveService:
    """Servicio de movimiento kinematic independiente del backend."""

    def __init__(self) -> None:
        self._legacy_solver: Optional[Any] = None  # LegacyAABBPhysicsBackend lazy

    def move_and_slide(
        self,
        backend: PhysicsBackend,
        world: Any,
        entity: Any,
        velocity: tuple[float, float],
        delta_time: float,
        floor_max_angle: float = 0.785398,
        floor_snap_distance: float = 2.0,
        up_direction: tuple[float, float] = (0.0, -1.0),
        wall_min_slide_angle: float = 0.261799,
        max_slides: int = 4,
    ) -> MoveResult2D:
        """Ejecuta move_and_slide usando el mejor solver disponible.

        Si el backend soporta kinematic move, lo usa directamente.
        Si no, usa el legacy AABB solver como fallback.
        """
        if backend.supports_kinematic_move():
            return backend.move_and_slide(
                world=world, entity=entity, velocity=velocity,
                delta_time=delta_time, floor_max_angle=floor_max_angle,
                floor_snap_distance=floor_snap_distance,
                up_direction=up_direction, wall_min_slide_angle=wall_min_slide_angle,
                max_slides=max_slides,
            )

        # Fallback: usar legacy solver
        if self._legacy_solver is None:
            from engine.physics.legacy_backend import LegacyAABBPhysicsBackend
            self._legacy_solver = LegacyAABBPhysicsBackend(
                physics_system=None, collision_system=None,
            )

        return self._legacy_solver.move_and_slide(
            world=world, entity=entity, velocity=velocity,
            delta_time=delta_time, floor_max_angle=floor_max_angle,
            floor_snap_distance=floor_snap_distance,
            up_direction=up_direction, wall_min_slide_angle=wall_min_slide_angle,
            max_slides=max_slides,
        )

    def move_and_collide(
        self,
        backend: PhysicsBackend,
        world: Any,
        entity: Any,
        velocity: tuple[float, float],
        delta_time: float,
        max_collisions: int = 1,
    ) -> MoveResult2D:
        """Ejecuta move_and_collide usando el mejor solver disponible."""
        if backend.supports_kinematic_move():
            return backend.move_and_collide(
                world=world, entity=entity, velocity=velocity,
                delta_time=delta_time, max_collisions=max_collisions,
            )

        if self._legacy_solver is None:
            from engine.physics.legacy_backend import LegacyAABBPhysicsBackend
            self._legacy_solver = LegacyAABBPhysicsBackend(
                physics_system=None, collision_system=None,
            )

        return self._legacy_solver.move_and_collide(
            world=world, entity=entity, velocity=velocity,
            delta_time=delta_time, max_collisions=max_collisions,
        )
