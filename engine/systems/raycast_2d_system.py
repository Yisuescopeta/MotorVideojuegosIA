"""
engine/systems/raycast_2d_system.py - Sistema que actualiza RayCast2D cada frame.

Usa query_physics_ray para lanzar un rayo desde la posicion de la entidad
hacia cast_to y poblacion los resultados de colision.
"""

from __future__ import annotations

from typing import Callable, Optional

from engine.components.raycast_2d import RayCast2D
from engine.components.transform import Transform
from engine.ecs.world import World

RayCastQueryFn = Callable[
    [float, float, float, float, float],
    list[dict],
]


class RayCast2DSystem:
    """Actualiza todos los RayCast2D lanzando rayos y poblando resultados."""

    def __init__(self, ray_cast_query: Optional[RayCastQueryFn] = None) -> None:
        self._ray_cast_query: Optional[RayCastQueryFn] = ray_cast_query

    def set_ray_cast_query(self, fn: RayCastQueryFn) -> None:
        self._ray_cast_query = fn

    def update(self, world: World, dt: float) -> None:
        if self._ray_cast_query is None:
            return

        for entity in world.get_entities_with(RayCast2D, Transform):
            raycast = entity.get_component(RayCast2D)
            transform = entity.get_component(Transform)
            if raycast is None or transform is None or not raycast.enabled:
                continue

            origin_x = transform.x
            origin_y = transform.y
            direction_x = raycast.cast_to_x
            direction_y = raycast.cast_to_y
            import math
            max_distance = math.sqrt(direction_x ** 2 + direction_y ** 2)

            hits = self._ray_cast_query(
                origin_x, origin_y, direction_x, direction_y, max_distance
            )

            if hits:
                hit = hits[0]
                raycast.is_colliding = True
                point = hit.get("point", {})
                normal = hit.get("normal", {})
                raycast.collision_point_x = float(point.get("x", 0.0))
                raycast.collision_point_y = float(point.get("y", 0.0))
                raycast.collision_normal_x = float(normal.get("x", 0.0))
                raycast.collision_normal_y = float(normal.get("y", 0.0))
                raycast.collider_entity = str(hit.get("entity", ""))
            else:
                raycast.is_colliding = False
                raycast.collision_point_x = 0.0
                raycast.collision_point_y = 0.0
                raycast.collision_normal_x = 0.0
                raycast.collision_normal_y = 0.0
                raycast.collider_entity = ""
