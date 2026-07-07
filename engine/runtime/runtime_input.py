"""Runtime input snapshots exposed to ScriptBehaviour contexts."""

from __future__ import annotations

from typing import Any, Iterable, NamedTuple, Optional

from engine.utils.viewport import screen_to_viewport, viewport_to_world


class RuntimePoint2D(NamedTuple):
    x: float
    y: float


class NullRuntimeInput:
    mouse_screen = RuntimePoint2D(0.0, 0.0)
    mouse_viewport = RuntimePoint2D(0.0, 0.0)
    mouse_world = RuntimePoint2D(0.0, 0.0)
    left_down = False
    left_pressed = False
    left_released = False

    def key_pressed(self, key_name: str) -> bool:
        return False


class RuntimeInputService:
    """Stores current-frame runtime input without exposing pyray to scripts."""

    def __init__(self) -> None:
        self.mouse_screen = RuntimePoint2D(0.0, 0.0)
        self.mouse_viewport = RuntimePoint2D(0.0, 0.0)
        self.mouse_world = RuntimePoint2D(0.0, 0.0)
        self.left_down: bool = False
        self.left_pressed: bool = False
        self.left_released: bool = False
        self._pressed_keys: set[str] = set()

    def reset(self) -> None:
        self.mouse_screen = RuntimePoint2D(0.0, 0.0)
        self.mouse_viewport = RuntimePoint2D(0.0, 0.0)
        self.mouse_world = RuntimePoint2D(0.0, 0.0)
        self.left_down = False
        self.left_pressed = False
        self.left_released = False
        self._pressed_keys = set()

    def update(
        self,
        pointer_state: dict[str, Any] | None,
        *,
        world: Any | None = None,
        viewport_size: Optional[tuple[float, float]] = None,
        viewport_rect: Any | None = None,
        camera_profile_id: str | None = None,
        keys_pressed: Iterable[str] | None = None,
    ) -> None:
        payload = pointer_state or {}

        screen_x = _float(payload.get("screen_x", payload.get("x", self.mouse_screen.x)))
        screen_y = _float(payload.get("screen_y", payload.get("y", self.mouse_screen.y)))
        if "viewport_x" in payload or "viewport_y" in payload:
            viewport_x = _float(payload.get("viewport_x", screen_x))
            viewport_y = _float(payload.get("viewport_y", screen_y))
        else:
            viewport_x, viewport_y = screen_to_viewport(
                screen_x,
                screen_y,
                viewport_rect=viewport_rect,
                viewport_size=viewport_size,
            )

        world_x, world_y = viewport_to_world(
            viewport_x,
            viewport_y,
            world=world,
            viewport_size=viewport_size,
            camera_profile_id=camera_profile_id,
        )

        self.mouse_screen = RuntimePoint2D(screen_x, screen_y)
        self.mouse_viewport = RuntimePoint2D(float(viewport_x), float(viewport_y))
        self.mouse_world = RuntimePoint2D(float(world_x), float(world_y))
        self.left_down = bool(payload.get("down", False))
        self.left_pressed = bool(payload.get("pressed", False))
        self.left_released = bool(payload.get("released", False))
        self._pressed_keys = _normalize_key_set(payload.get("keys_pressed", payload.get("key_pressed", keys_pressed)))

    def key_pressed(self, key_name: str) -> bool:
        return _normalize_key_name(key_name) in self._pressed_keys


NULL_RUNTIME_INPUT = NullRuntimeInput()


def _float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _normalize_key_set(raw: Any) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, dict):
        return {_normalize_key_name(name) for name, pressed in raw.items() if bool(pressed)}
    if isinstance(raw, str):
        return {_normalize_key_name(raw)}
    try:
        return {_normalize_key_name(name) for name in raw}
    except TypeError:
        return set()


def _normalize_key_name(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text.startswith("KEY_"):
        text = text[4:]
    return text
