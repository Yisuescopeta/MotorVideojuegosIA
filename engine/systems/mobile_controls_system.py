"""Runtime system for mobile virtual controls."""

from __future__ import annotations

import math
from typing import Any

from engine.components.inputmap import InputMap
from engine.components.mobile_controls_2d import MobileControls2D
from engine.ecs.world import World


class MobileControlsSystem:
    """Maps pointer/touch input into InputMap action state."""

    def __init__(self) -> None:
        self._pointer_state: dict[str, Any] | None = None
        self._active_targets: set[str] = set()

    def inject_pointer_state(
        self,
        x: float,
        y: float,
        *,
        down: bool = False,
        pressed: bool = False,
        released: bool = False,
        frames: int = 1,
    ) -> None:
        self._pointer_state = {
            "x": float(x),
            "y": float(y),
            "down": bool(down),
            "pressed": bool(pressed),
            "released": bool(released),
            "frames": max(1, int(frames)),
        }

    def update(self, world: World, viewport_size: tuple[float, float]) -> None:
        pointer = self._consume_pointer_state()
        if pointer is None:
            return

        next_active_targets: set[str] = set()
        width, height = float(viewport_size[0]), float(viewport_size[1])
        pointer_down = bool(pointer.get("down") or pointer.get("pressed"))

        for entity in world.get_entities_with(MobileControls2D):
            controls = entity.get_component(MobileControls2D)
            if controls is None or not controls.enabled:
                continue
            target = world.get_entity_by_name(controls.target_entity)
            input_map = target.get_component(InputMap) if target is not None else None
            if input_map is None or not input_map.enabled:
                continue

            state = dict(input_map.last_state)
            if pointer_down:
                state.update(self._state_from_pointer(controls, pointer, width, height))
                next_active_targets.add(controls.target_entity)
            elif controls.target_entity in self._active_targets or bool(pointer.get("released")):
                state.update({"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0})
            input_map.last_state = state

        self._active_targets = next_active_targets

    def _consume_pointer_state(self) -> dict[str, Any] | None:
        if self._pointer_state is None:
            return None
        payload = dict(self._pointer_state)
        frames = int(payload.get("frames", 1))
        if frames <= 1:
            self._pointer_state = None
        else:
            payload["frames"] = frames - 1
            self._pointer_state = payload
        return payload

    def _state_from_pointer(
        self,
        controls: MobileControls2D,
        pointer: dict[str, Any],
        width: float,
        height: float,
    ) -> dict[str, float]:
        x = float(pointer.get("x", 0.0))
        y = float(pointer.get("y", 0.0))
        state = {"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0}

        if controls.left_stick_enabled:
            cx = width * controls.left_stick_anchor_x
            cy = height * controls.left_stick_anchor_y
            dx = x - cx
            dy = y - cy
            distance = math.hypot(dx, dy)
            if distance <= controls.left_stick_radius and distance > 0.0:
                normalized = min(1.0, distance / controls.left_stick_radius)
                if normalized >= controls.deadzone:
                    scale = (normalized - controls.deadzone) / max(0.001, 1.0 - controls.deadzone)
                    state["horizontal"] = max(-1.0, min(1.0, (dx / distance) * scale))
                    state["vertical"] = max(-1.0, min(1.0, -(dy / distance) * scale))

        if controls.action_1_enabled and self._inside_circle(
            x, y, width * controls.action_1_anchor_x, height * controls.action_1_anchor_y, controls.action_1_radius
        ):
            state["action_1"] = 1.0
        if controls.action_2_enabled and self._inside_circle(
            x, y, width * controls.action_2_anchor_x, height * controls.action_2_anchor_y, controls.action_2_radius
        ):
            state["action_2"] = 1.0
        return state

    @staticmethod
    def _inside_circle(x: float, y: float, cx: float, cy: float, radius: float) -> bool:
        return math.hypot(x - cx, y - cy) <= radius
