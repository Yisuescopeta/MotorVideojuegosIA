"""
engine/systems/raycast_2d_system.py - Sistema que actualiza RayCast2D cada frame.

Usa query_physics_ray para lanzar un rayo desde la posicion de la entidad
hacia cast_to y poblacion los resultados de colision.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from engine.components.collision_filter_2d import CollisionFilter2D
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
            max_distance = math.sqrt(direction_x ** 2 + direction_y ** 2)

            hits = self._ray_cast_query(
                origin_x, origin_y, direction_x, direction_y, max_distance
            )

            filtered = self._filter_hits(
                hits, raycast, entity_name=entity.name, world=world,
            )

            if filtered:
                hit = filtered[0]
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

    @staticmethod
    def _filter_hits(
        hits: list[dict],
        raycast: RayCast2D,
        *,
        entity_name: str = "",
        world: Optional[World] = None,
    ) -> list[dict]:
        """Filtra hits segun configuracion de RayCast2D.

        Orden de filtrado:
          1. exclude_parent: descarta hit a la propia entidad o su padre.
          2. collide_with_areas: descarta is_trigger cuando False.
          3. collide_with_bodies: descarta not is_trigger cuando False.
          4. collision_mask: inspecciona CollisionFilter2D de la entidad golpeada.
        """
        result: list[dict] = []

        for hit in hits:
            hit_entity_name = str(hit.get("entity", ""))
            hit_entity_id = hit.get("entity_id", None)

            # 1. exclude_parent: descartar self
            if raycast.exclude_parent:
                if hit_entity_name == entity_name:
                    continue
                if hit_entity_id is not None and world is not None:
                    hit_entity = world.get_entity_by_name(hit_entity_name)
                    if hit_entity is not None and hasattr(hit_entity, "parent_name"):
                        parent = hit_entity.parent_name
                        if parent and parent == entity_name:
                            continue

            # 2. collide_with_areas
            if not raycast.collide_with_areas:
                if bool(hit.get("is_trigger", False)):
                    continue

            # 3. collide_with_bodies
            if not raycast.collide_with_bodies:
                if not bool(hit.get("is_trigger", False)):
                    continue

            # 4. collision_mask
            if raycast.collision_mask != 0xFFFFFFFF and world is not None:
                hit_layer = 1  # default: layer 1
                if hit_entity_name:
                    hit_entity = world.get_entity_by_name(hit_entity_name)
                    if hit_entity is not None:
                        hit_filter = hit_entity.get_component(CollisionFilter2D)
                        if hit_filter is not None:
                            hit_layer = hit_filter.layer
                if (raycast.collision_mask & hit_layer) == 0:
                    continue

            result.append(hit)

        return result
