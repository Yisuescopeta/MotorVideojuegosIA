"""
engine/utils/viewport.py - Viewport resolution in world coordinates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from engine.components.camera2d import Camera2D
from engine.components.transform import Transform

if TYPE_CHECKING:
    from engine.ecs.world import World

DEFAULT_VIEWPORT_WIDTH: float = 800.0
DEFAULT_VIEWPORT_HEIGHT: float = 600.0
MIN_ZOOM_EPSILON: float = 1e-4


@dataclass(frozen=True)
class ResolvedCamera2D:
    entity_name: str
    target_x: float
    target_y: float
    offset_x: float
    offset_y: float
    zoom: float
    rotation: float
    viewport_width: float
    viewport_height: float
    rect_left: float
    rect_top: float
    rect_right: float
    rect_bottom: float

    @property
    def rect_width(self) -> float:
        return self.rect_right - self.rect_left

    @property
    def rect_height(self) -> float:
        return self.rect_bottom - self.rect_top

    @property
    def rect_center_x(self) -> float:
        return self.rect_left + self.rect_width * 0.5

    @property
    def rect_center_y(self) -> float:
        return self.rect_top + self.rect_height * 0.5

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return (self.rect_left, self.rect_top, self.rect_right, self.rect_bottom)


def resolve_effective_camera2d(
    world: Optional["World"],
    viewport_size: Optional[tuple[float, float]] = None,
    camera_profile_id: Optional[str] = None,
    *,
    camera_entity: Any | None = None,
) -> ResolvedCamera2D | None:
    """Resolve the effective runtime camera and its visible world rect."""
    if world is None or not hasattr(world, "get_entities_with"):
        return None

    entity = camera_entity if camera_entity is not None else _find_primary_camera_entity(world)
    if entity is None:
        return None

    transform = entity.get_component(Transform)
    camera_component = entity.get_component(Camera2D)
    if transform is None or camera_component is None or not camera_component.enabled:
        return None

    view_w, view_h = _normalize_viewport_size(viewport_size)
    profile_override = _camera_profile_override(camera_component, camera_profile_id)

    target_x = float(transform.x)
    target_y = float(transform.y)
    follow_target = world.get_entity_by_name(camera_component.follow_entity) if camera_component.follow_entity else None
    if follow_target is not None and bool(getattr(follow_target, "active", True)):
        follow_transform = follow_target.get_component(Transform)
        if follow_transform is not None and bool(getattr(follow_transform, "enabled", True)):
            target_x, target_y = _resolve_camera_target(camera_component, follow_transform, (view_w, view_h))
            target_x += _profile_number(profile_override, "target_offset_x", 0.0)
            target_y += _profile_number(profile_override, "target_offset_y", 0.0)
    else:
        target_x = _profile_number(profile_override, "target_x", target_x)
        target_y = _profile_number(profile_override, "target_y", target_y)

    target_x, target_y = _apply_camera_clamp(camera_component, target_x, target_y)
    offset_x = _profile_number(profile_override, "offset_x", camera_component.offset_x)
    offset_y = _profile_number(profile_override, "offset_y", camera_component.offset_y)
    zoom = max(abs(_profile_number(profile_override, "zoom", camera_component.zoom)), MIN_ZOOM_EPSILON)
    rotation = _profile_number(profile_override, "rotation", camera_component.rotation)
    left, top, right, bottom = _camera_visible_rect(
        target_x,
        target_y,
        offset_x,
        offset_y,
        zoom,
        rotation,
        view_w,
        view_h,
    )
    return ResolvedCamera2D(
        entity_name=str(getattr(entity, "name", "")),
        target_x=target_x,
        target_y=target_y,
        offset_x=offset_x,
        offset_y=offset_y,
        zoom=zoom,
        rotation=rotation,
        viewport_width=view_w,
        viewport_height=view_h,
        rect_left=left,
        rect_top=top,
        rect_right=right,
        rect_bottom=bottom,
    )


def resolve_world_viewport_rect(
    world: Optional["World"],
    viewport_size: Optional[tuple[float, float]] = None,
    camera_profile_id: Optional[str] = None,
) -> tuple[float, float, float, float] | None:
    """Return the primary camera visible rect in world coordinates."""
    resolved = resolve_effective_camera2d(world, viewport_size, camera_profile_id)
    return resolved.rect if resolved is not None else None


def screen_to_viewport(
    screen_x: float,
    screen_y: float,
    *,
    viewport_rect: Any | None = None,
    viewport_size: Optional[tuple[float, float]] = None,
) -> tuple[float, float]:
    """Convert window/screen coordinates to logical viewport coordinates."""
    if viewport_rect is None:
        return float(screen_x), float(screen_y)

    rect_x, rect_y, rect_w, rect_h = _unpack_rect(viewport_rect)
    view_w, view_h = _normalize_viewport_size(viewport_size)
    if rect_w <= 0.0 or rect_h <= 0.0:
        return 0.0, 0.0
    return (
        (float(screen_x) - rect_x) * (view_w / rect_w),
        (float(screen_y) - rect_y) * (view_h / rect_h),
    )


def viewport_to_world(
    viewport_x: float,
    viewport_y: float,
    world: Optional["World"] = None,
    viewport_size: Optional[tuple[float, float]] = None,
    camera_profile_id: Optional[str] = None,
    *,
    camera_entity: Any | None = None,
) -> tuple[float, float]:
    """Convert logical viewport coordinates to world coordinates."""
    resolved = resolve_effective_camera2d(
        world,
        viewport_size=viewport_size,
        camera_profile_id=camera_profile_id,
        camera_entity=camera_entity,
    )
    if resolved is None:
        return float(viewport_x), float(viewport_y)
    return _screen_to_world(
        float(viewport_x),
        float(viewport_y),
        resolved.target_x,
        resolved.target_y,
        resolved.offset_x,
        resolved.offset_y,
        resolved.zoom,
        resolved.rotation,
    )


def screen_to_world(
    screen_x: float,
    screen_y: float,
    world: Optional["World"] = None,
    viewport_size: Optional[tuple[float, float]] = None,
    camera_profile_id: Optional[str] = None,
    *,
    viewport_rect: Any | None = None,
    camera_entity: Any | None = None,
) -> tuple[float, float]:
    """Convert window/screen coordinates to world coordinates."""
    viewport_x, viewport_y = screen_to_viewport(
        screen_x,
        screen_y,
        viewport_rect=viewport_rect,
        viewport_size=viewport_size,
    )
    return viewport_to_world(
        viewport_x,
        viewport_y,
        world=world,
        viewport_size=viewport_size,
        camera_profile_id=camera_profile_id,
        camera_entity=camera_entity,
    )


def _find_primary_camera_entity(world: "World") -> Any | None:
    for entity in world.get_entities_with(Transform, Camera2D):
        camera_component = entity.get_component(Camera2D)
        if camera_component is not None and camera_component.enabled and camera_component.is_primary:
            return entity
    return None


def _normalize_viewport_size(viewport_size: Optional[tuple[float, float]]) -> tuple[float, float]:
    if viewport_size is None:
        return DEFAULT_VIEWPORT_WIDTH, DEFAULT_VIEWPORT_HEIGHT
    return max(1.0, float(viewport_size[0])), max(1.0, float(viewport_size[1]))


def _unpack_rect(rect: Any) -> tuple[float, float, float, float]:
    if isinstance(rect, dict):
        return (
            float(rect.get("x", rect.get("left", 0.0))),
            float(rect.get("y", rect.get("top", 0.0))),
            float(rect.get("width", 0.0)),
            float(rect.get("height", 0.0)),
        )
    if isinstance(rect, (tuple, list)) and len(rect) >= 4:
        return float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
    return (
        float(getattr(rect, "x", getattr(rect, "left", 0.0))),
        float(getattr(rect, "y", getattr(rect, "top", 0.0))),
        float(getattr(rect, "width", 0.0)),
        float(getattr(rect, "height", 0.0)),
    )


def _camera_profile_override(camera_component: Camera2D, camera_profile_id: Optional[str]) -> dict[str, Any]:
    profile_id = str(camera_profile_id or "").strip()
    if not profile_id:
        return {}
    overrides = getattr(camera_component, "profile_overrides", {})
    if not isinstance(overrides, dict):
        return {}
    payload = overrides.get(profile_id, {})
    return payload if isinstance(payload, dict) else {}


def _profile_number(profile_override: dict[str, Any], key: str, fallback: float) -> float:
    if key not in profile_override:
        return float(fallback)
    try:
        return float(profile_override[key])
    except (TypeError, ValueError):
        return float(fallback)


def _resolve_camera_target(
    camera_component: Camera2D,
    follow_transform: Transform,
    viewport_size: tuple[float, float],
) -> tuple[float, float]:
    target_x = float(follow_transform.x)
    target_y = float(follow_transform.y)
    if camera_component.framing_mode != "platformer":
        camera_component._runtime_target_x = target_x
        camera_component._runtime_target_y = target_y
        camera_component._has_recentred = True
        return target_x, target_y

    view_w, view_h = viewport_size
    dead_zone_width = camera_component.dead_zone_width or (view_w * 0.18)
    dead_zone_height = camera_component.dead_zone_height or (view_h * 0.12)
    vertical_bias = max(0.0, view_h * 0.12)
    desired_y = target_y - vertical_bias

    if camera_component.recenter_on_play and not camera_component._has_recentred:
        camera_component._runtime_target_x = target_x
        camera_component._runtime_target_y = desired_y
        camera_component._has_recentred = True
        return target_x, desired_y

    current_x = camera_component._runtime_target_x
    current_y = camera_component._runtime_target_y
    if not camera_component._has_recentred:
        current_x = target_x
        current_y = desired_y
        camera_component._has_recentred = True

    half_dead_zone_x = dead_zone_width * 0.5
    half_dead_zone_y = dead_zone_height * 0.5
    if target_x > current_x + half_dead_zone_x:
        current_x = target_x - half_dead_zone_x
    elif target_x < current_x - half_dead_zone_x:
        current_x = target_x + half_dead_zone_x

    if desired_y > current_y + half_dead_zone_y:
        current_y = desired_y - half_dead_zone_y
    elif desired_y < current_y - half_dead_zone_y:
        current_y = desired_y + half_dead_zone_y

    camera_component._runtime_target_x = current_x
    camera_component._runtime_target_y = current_y
    return current_x, current_y


def _apply_camera_clamp(
    camera_component: Camera2D,
    target_x: float,
    target_y: float,
) -> tuple[float, float]:
    if camera_component.clamp_left is not None:
        target_x = max(float(camera_component.clamp_left), target_x)
    if camera_component.clamp_right is not None:
        target_x = min(float(camera_component.clamp_right), target_x)
    if camera_component.clamp_top is not None:
        target_y = max(float(camera_component.clamp_top), target_y)
    if camera_component.clamp_bottom is not None:
        target_y = min(float(camera_component.clamp_bottom), target_y)
    return target_x, target_y


def _camera_visible_rect(
    target_x: float,
    target_y: float,
    offset_x: float,
    offset_y: float,
    zoom: float,
    rotation: float,
    viewport_width: float,
    viewport_height: float,
) -> tuple[float, float, float, float]:
    corners = (
        _screen_to_world(0.0, 0.0, target_x, target_y, offset_x, offset_y, zoom, rotation),
        _screen_to_world(viewport_width, 0.0, target_x, target_y, offset_x, offset_y, zoom, rotation),
        _screen_to_world(viewport_width, viewport_height, target_x, target_y, offset_x, offset_y, zoom, rotation),
        _screen_to_world(0.0, viewport_height, target_x, target_y, offset_x, offset_y, zoom, rotation),
    )
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    return min(xs), min(ys), max(xs), max(ys)


def _screen_to_world(
    screen_x: float,
    screen_y: float,
    target_x: float,
    target_y: float,
    offset_x: float,
    offset_y: float,
    zoom: float,
    rotation: float,
) -> tuple[float, float]:
    dx = (screen_x - offset_x) / zoom
    dy = (screen_y - offset_y) / zoom
    radians = math.radians(-rotation)
    cos_r = math.cos(radians)
    sin_r = math.sin(radians)
    return (
        target_x + dx * cos_r - dy * sin_r,
        target_y + dx * sin_r + dy * cos_r,
    )
