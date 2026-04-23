"""
engine/utils/viewport.py - Resolución de viewport en coordenadas de mundo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.components.camera2d import Camera2D
from engine.components.transform import Transform

if TYPE_CHECKING:
    from engine.ecs.world import World

DEFAULT_VIEWPORT_WIDTH: float = 800.0
DEFAULT_VIEWPORT_HEIGHT: float = 600.0
MIN_ZOOM_EPSILON: float = 1e-4


def resolve_world_viewport_rect(
    world: Optional["World"],
    viewport_size: Optional[tuple[float, float]] = None,
) -> tuple[float, float, float, float] | None:
    """Calcula el rect del viewport en coordenadas de mundo usando la cámara primaria."""
    if world is None or not hasattr(world, "get_entities_with"):
        return None

    primary_entity = None
    for entity in world.get_entities_with(Transform, Camera2D):
        camera_component = entity.get_component(Camera2D)
        if camera_component is not None and camera_component.enabled and camera_component.is_primary:
            primary_entity = entity
            break
    if primary_entity is None:
        return None

    transform = primary_entity.get_component(Transform)
    camera_component = primary_entity.get_component(Camera2D)
    if transform is None or camera_component is None:
        return None

    view_w = viewport_size[0] if viewport_size else DEFAULT_VIEWPORT_WIDTH
    view_h = viewport_size[1] if viewport_size else DEFAULT_VIEWPORT_HEIGHT
    zoom = max(float(camera_component.zoom), MIN_ZOOM_EPSILON)
    target_x = transform.x
    target_y = transform.y

    half_w = (view_w * 0.5) / zoom
    half_h = (view_h * 0.5) / zoom
    return (
        target_x - half_w,
        target_y - half_h,
        target_x + half_w,
        target_y + half_h,
    )
