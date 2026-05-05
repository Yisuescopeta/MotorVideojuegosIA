"""engine/systems/path_follow_system.py — PathFollowSystem: updates PathFollower2D entities."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from engine.components.path_follower_2d import PathFollower2D
from engine.components.transform import Transform

if TYPE_CHECKING:
    from engine.ecs.world import World


class PathFollowSystem:
    """Advances entities with PathFollower2D along their Curve2D path."""

    def __init__(self) -> None:
        self._completed: set[int] = set()

    def reset(self) -> None:
        self._completed.clear()

    def update(self, world: "World", dt: float, event_bus: Any = None) -> None:
        step = max(0.0, float(dt))
        if step <= 0.0:
            return
        if not hasattr(world, "get_entities_with"):
            return

        for entity in world.get_entities_with(Transform, PathFollower2D):
            follower = entity.get_component(PathFollower2D)
            transform = entity.get_component(Transform)
            if follower is None or transform is None:
                continue
            if not follower.enabled or follower.curve is None:
                continue

            curve = follower.curve
            if curve.point_count < 2:
                continue

            curve_length = curve.get_baked_length()
            if curve_length <= 1e-9:
                continue

            entity_id = int(entity.id)
            if entity_id in self._completed:
                continue

            if follower.speed > 0.0:
                follower.progress += follower.speed * step

            while follower.progress < 0.0 and follower.loop:
                follower.progress += curve_length

            if follower.loop:
                if follower.progress >= curve_length:
                    follower.progress = follower.progress % curve_length
                    self._emit_event(event_bus, "path_follower_loop", entity, follower)
            else:
                if follower.progress < 0.0:
                    follower.progress = 0.0
                if follower.progress >= curve_length:
                    follower.progress = curve_length
                    if entity_id not in self._completed:
                        self._completed.add(entity_id)
                        self._emit_event(event_bus, "path_follower_completed", entity, follower)
                        continue

            sampled = curve.sample_baked(follower.progress, cubic=follower.cubic_interp)
            base_x = float(sampled["x"])
            base_y = float(sampled["y"])

            h_off = float(follower.h_offset)
            v_off = float(follower.v_offset)

            if abs(h_off) > 1e-9 or abs(v_off) > 1e-9:
                fwd = curve.get_forward_vector(follower.progress)
                fx, fy = float(fwd["x"]), float(fwd["y"])
                left_x = -fy
                left_y = fx
                final_x = base_x + left_x * h_off + fx * v_off
                final_y = base_y + left_y * h_off + fy * v_off
            else:
                final_x = base_x
                final_y = base_y

            transform.x = final_x
            transform.y = final_y

            if follower.rotates:
                fwd = curve.get_forward_vector(follower.progress)
                transform.rotation = math.atan2(float(fwd["y"]), float(fwd["x"]))

            world.touch_transform()

    def _emit_event(
        self,
        event_bus: Any,
        event_name: str,
        entity: Any,
        follower: PathFollower2D,
    ) -> None:
        if event_bus is None:
            return
        event_bus.emit(
            event_name,
            {
                "entity": entity.name,
                "progress": follower.progress,
                "progress_ratio": follower.progress_ratio,
                "speed": follower.speed,
                "loop": follower.loop,
            },
        )
