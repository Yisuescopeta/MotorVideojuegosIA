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
        self._active_controls: dict[tuple[str, str], str] = {}

    def inject_pointer_state(
        self,
        x: float,
        y: float,
        *,
        down: bool = False,
        pressed: bool = False,
        released: bool = False,
        frames: int = 1,
        pointer_id: str | int = "legacy",
    ) -> None:
        self._pointer_state = {
            "id": str(pointer_id),
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

        pointers = self._normalize_pointer_payload(pointer)
        if not pointers:
            return

        next_active_controls: dict[tuple[str, str], str] = {}
        width, height = float(viewport_size[0]), float(viewport_size[1])

        for entity in world.get_entities_with(MobileControls2D):
            controls = entity.get_component(MobileControls2D)
            if controls is None or not controls.enabled:
                continue
            target = world.get_entity_by_name(controls.target_entity)
            input_map = target.get_component(InputMap) if target is not None else None
            if input_map is None or not input_map.enabled:
                continue

            state = dict(input_map.last_state)
            mobile_state = {"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0}
            has_mobile_input = False
            should_reset = False

            for active_pointer in pointers:
                pointer_id = str(active_pointer.get("id", "legacy"))
                capture_key = (controls.target_entity, pointer_id)
                pointer_down = bool(active_pointer.get("down") or active_pointer.get("pressed"))
                if pointer_down:
                    capture = self._active_controls.get(capture_key) or self._capture_control(
                        controls, active_pointer, width, height
                    )
                    if capture is not None:
                        partial = self._state_from_pointer(controls, active_pointer, width, height, capture=capture)
                        self._merge_mobile_state(mobile_state, partial, capture)
                        next_active_controls[capture_key] = capture
                        has_mobile_input = True
                elif capture_key in self._active_controls or bool(active_pointer.get("released")):
                    should_reset = True

            if has_mobile_input or should_reset:
                state.update(mobile_state)
            input_map.last_state = state

        self._active_controls = next_active_controls

    def _normalize_pointer_payload(self, pointer: dict[str, Any]) -> list[dict[str, Any]]:
        raw_pointers = pointer.get("pointers")
        if isinstance(raw_pointers, list):
            pointers: list[dict[str, Any]] = []
            for index, raw_pointer in enumerate(raw_pointers):
                if not isinstance(raw_pointer, dict):
                    continue
                normalized = dict(raw_pointer)
                normalized["id"] = str(normalized.get("id", index))
                pointers.append(normalized)
            return pointers
        return [dict(pointer)]

    @staticmethod
    def _merge_mobile_state(mobile_state: dict[str, float], partial: dict[str, float], capture: str) -> None:
        if capture == "left_stick":
            mobile_state["horizontal"] = partial["horizontal"]
            mobile_state["vertical"] = partial["vertical"]
        elif capture == "action_1":
            mobile_state["action_1"] = max(mobile_state["action_1"], partial["action_1"])
        elif capture == "action_2":
            mobile_state["action_2"] = max(mobile_state["action_2"], partial["action_2"])

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
        *,
        capture: str,
    ) -> dict[str, float]:
        x = float(pointer.get("x", 0.0))
        y = float(pointer.get("y", 0.0))
        state = {"horizontal": 0.0, "vertical": 0.0, "action_1": 0.0, "action_2": 0.0}

        if capture == "left_stick" and controls.left_stick_enabled:
            cx = width * controls.left_stick_anchor_x
            cy = height * controls.left_stick_anchor_y
            dx = x - cx
            dy = y - cy
            distance = math.hypot(dx, dy)
            if distance > 0.0:
                normalized = min(1.0, distance / controls.left_stick_radius)
                if normalized >= controls.deadzone:
                    if controls.movement_mode == "dpad":
                        if abs(dx) >= abs(dy):
                            state["horizontal"] = 1.0 if dx >= 0.0 else -1.0
                        else:
                            state["vertical"] = -1.0 if dy >= 0.0 else 1.0
                    else:
                        scale = (normalized - controls.deadzone) / max(0.001, 1.0 - controls.deadzone)
                        state["horizontal"] = max(-1.0, min(1.0, (dx / distance) * scale))
                        state["vertical"] = max(-1.0, min(1.0, -(dy / distance) * scale))

        if capture == "action_1" and controls.action_1_enabled:
            state["action_1"] = 1.0
        if capture == "action_2" and controls.action_2_enabled:
            state["action_2"] = 1.0
        return state

    @staticmethod
    def _inside_circle(x: float, y: float, cx: float, cy: float, radius: float) -> bool:
        return math.hypot(x - cx, y - cy) <= radius

    def _capture_control(
        self,
        controls: MobileControls2D,
        pointer: dict[str, Any],
        width: float,
        height: float,
    ) -> str | None:
        x = float(pointer.get("x", 0.0))
        y = float(pointer.get("y", 0.0))
        if controls.left_stick_enabled and self._inside_circle(
            x,
            y,
            width * controls.left_stick_anchor_x,
            height * controls.left_stick_anchor_y,
            controls.left_stick_radius * 1.35,
        ):
            return "left_stick"
        if controls.action_1_enabled and self._inside_circle(
            x,
            y,
            width * controls.action_1_anchor_x,
            height * controls.action_1_anchor_y,
            controls.action_1_radius * 1.35,
        ):
            return "action_1"
        if controls.action_2_enabled and self._inside_circle(
            x,
            y,
            width * controls.action_2_anchor_x,
            height * controls.action_2_anchor_y,
            controls.action_2_radius * 1.35,
        ):
            return "action_2"
        return None
