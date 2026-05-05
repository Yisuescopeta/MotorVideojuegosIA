from __future__ import annotations

import math
from typing import Optional

from engine.physics.shapes import ShapeFactory, ShapeInstance


def swept_shape_toi(
    shape_type: str,
    shape_params: dict[str, float],
    origin: tuple[float, float],
    direction: tuple[float, float],
    max_distance: float,
    target_shape: ShapeInstance,
    target_info: dict,
    epsilon: float = 0.001,
    max_iter: int = 64,
) -> Optional[dict]:
    """Binary-search swept collision TOI between sweep shape and target shape.

    Returns dict with hit/fraction/position/normal/entity or None if no hit.
    """
    ox, oy = float(origin[0]), float(origin[1])
    dx, dy = float(direction[0]), float(direction[1])
    length = math.hypot(dx, dy)
    if length <= 1e-6:
        if _overlap_at(shape_type, shape_params, ox, oy, target_shape):
            return _make_hit(0.0, ox, oy, target_shape, target_info, shape_type, shape_params)
        return None
    dx /= length
    dy /= length

    # Quick overlap test at origin
    if _overlap_at(shape_type, shape_params, ox, oy, target_shape):
        return _make_hit(0.0, ox, oy, target_shape, target_info, shape_type, shape_params)

    # Check overlap at max_distance
    mx = ox + dx * max_distance
    my = oy + dy * max_distance
    overlaps_at_end = _overlap_at(shape_type, shape_params, mx, my, target_shape)

    if not overlaps_at_end:
        # If no overlap at either end, check if we sweep across the target
        if not _swept_aabb_check(shape_type, shape_params, ox, oy, dx, dy, max_distance, target_shape):
            return None
        # Need to find any t where overlap occurs -> linear scan then binary search
        return _scan_and_refine(
            shape_type, shape_params, ox, oy, dx, dy, max_distance,
            target_shape, target_info, epsilon,
        )

    # Standard case: overlap at max_distance, binary search [0, max]
    return _binary_search_hit(
        shape_type, shape_params, ox, oy, dx, dy, max_distance,
        target_shape, target_info, epsilon, max_iter, 0.0, max_distance,
    )


def _overlap_at(
    shape_type: str,
    shape_params: dict[str, float],
    px: float,
    py: float,
    target_shape: ShapeInstance,
) -> bool:
    s = ShapeFactory.build_from_params(shape_type, px, py, **shape_params)
    return s.intersects_shape(target_shape)


def _make_hit(
    fraction: float,
    hit_x: float,
    hit_y: float,
    target_shape: ShapeInstance,
    target_info: dict,
    shape_type: str,
    shape_params: dict[str, float],
) -> dict:
    hit_shape = ShapeFactory.build_from_params(shape_type, hit_x, hit_y, **shape_params)
    manifold = hit_shape.collide_shape(target_shape)
    normal_x = 0.0
    normal_y = 0.0
    if manifold is not None:
        normal_x = float(manifold.normal_x)
        normal_y = float(manifold.normal_y)
    return {
        "hit": True,
        "fraction": fraction,
        "position": {"x": hit_x, "y": hit_y},
        "normal": {"x": normal_x, "y": normal_y},
        "entity": str(target_info.get("entity", "")),
        "entity_id": int(target_info.get("entity_id", 0)),
        "is_trigger": bool(target_info.get("is_trigger", False)),
    }


def _swept_aabb_check(
    shape_type: str,
    shape_params: dict[str, float],
    ox: float,
    oy: float,
    dx: float,
    dy: float,
    max_distance: float,
    target_shape: ShapeInstance,
) -> bool:
    """Check if sweep shape AABB sweeps across target shape AABB."""
    sweep_origin = ShapeFactory.build_from_params(shape_type, ox, oy, **shape_params)
    sweep_end = ShapeFactory.build_from_params(
        shape_type, ox + dx * max_distance, oy + dy * max_distance, **shape_params
    )
    sw_aabb = sweep_origin.get_aabb()
    se_aabb = sweep_end.get_aabb()
    t_aabb = target_shape.get_aabb()

    sweep_left = min(sw_aabb[0], se_aabb[0])
    sweep_top = min(sw_aabb[1], se_aabb[1])
    sweep_right = max(sw_aabb[2], se_aabb[2])
    sweep_bottom = max(sw_aabb[3], se_aabb[3])

    return (
        sweep_left < t_aabb[2]
        and sweep_right > t_aabb[0]
        and sweep_top < t_aabb[3]
        and sweep_bottom > t_aabb[1]
    )


def _scan_and_refine(
    shape_type: str,
    shape_params: dict[str, float],
    ox: float,
    oy: float,
    dx: float,
    dy: float,
    max_distance: float,
    target_shape: ShapeInstance,
    target_info: dict,
    epsilon: float,
) -> Optional[dict]:
    """Linear scan to find first overlap, then binary search between last clear and first hit."""
    scan_steps = 20
    last_clear = 0.0
    for i in range(1, scan_steps + 1):
        t = max_distance * (i / float(scan_steps))
        px = ox + dx * t
        py = oy + dy * t
        if _overlap_at(shape_type, shape_params, px, py, target_shape):
            return _binary_search_hit(
                shape_type, shape_params, ox, oy, dx, dy, max_distance,
                target_shape, target_info, epsilon, 64,
                last_clear, t,
            )
        last_clear = t
    return None


def _binary_search_hit(
    shape_type: str,
    shape_params: dict[str, float],
    ox: float,
    oy: float,
    dx: float,
    dy: float,
    max_distance: float,
    target_shape: ShapeInstance,
    target_info: dict,
    epsilon: float,
    max_iter: int,
    lo: float,
    hi: float,
) -> dict:
    """Binary search for TOI in [lo, hi] where lo is clear and hi has overlap."""
    for _ in range(max_iter):
        if hi - lo <= epsilon:
            break
        mid = (lo + hi) / 2.0
        px = ox + dx * mid
        py = oy + dy * mid
        if _overlap_at(shape_type, shape_params, px, py, target_shape):
            hi = mid
        else:
            lo = mid

    fraction = hi / max_distance if max_distance > 0.0 else 0.0
    hit_x = ox + dx * hi
    hit_y = oy + dy * hi

    # Precise normal via collide_shape
    hit_shape = ShapeFactory.build_from_params(shape_type, hit_x, hit_y, **shape_params)
    manifold = hit_shape.collide_shape(target_shape)

    normal_x = 0.0
    normal_y = 0.0
    if manifold is not None:
        normal_x = float(manifold.normal_x)
        normal_y = float(manifold.normal_y)
    else:
        normal_x = -dx
        normal_y = -dy

    # Ensure normal points against sweep direction (toward origin)
    if normal_x * dx + normal_y * dy > 0:
        normal_x = -normal_x
        normal_y = -normal_y

    return {
        "hit": True,
        "fraction": fraction,
        "position": {"x": hit_x, "y": hit_y},
        "normal": {"x": normal_x, "y": normal_y},
        "entity": str(target_info.get("entity", "")),
        "entity_id": int(target_info.get("entity_id", 0)),
        "is_trigger": bool(target_info.get("is_trigger", False)),
    }
