"""Mouse input helpers for immediate editor widgets."""

from __future__ import annotations

from engine.editor.ui.geometry import Rect, rect_contains


def _rl():
    import pyray as rl

    return rl


def _left_button() -> int:
    return int(getattr(_rl(), "MOUSE_BUTTON_LEFT", 0))


def _right_button() -> int:
    return int(getattr(_rl(), "MOUSE_BUTTON_RIGHT", 1))


def mouse_position() -> tuple[float, float]:
    """Return current mouse position in editor screen coordinates."""

    rl = _rl()
    pos = rl.get_mouse_position()
    return (float(pos.x), float(pos.y))


def is_hovered(rect: Rect) -> bool:
    """Return whether current mouse position is inside ``rect``."""

    x, y = mouse_position()
    return is_hovered_at(rect, x, y)


def is_pressed(rect: Rect) -> bool:
    """Return whether left mouse button is down over ``rect``."""

    return is_pressed_at(rect, *mouse_position(), rl_mouse_down(_left_button()))


def is_clicked(rect: Rect) -> bool:
    """Return true on left mouse pressed event while cursor is over rect."""
    return is_clicked_at(rect, *mouse_position(), rl_mouse_pressed(_left_button()))


def is_right_clicked(rect: Rect) -> bool:
    """Return true on right mouse pressed event while cursor is over rect."""

    return is_right_clicked_at(rect, *mouse_position(), rl_mouse_pressed(_right_button()))


def wheel_delta() -> float:
    """Return mouse wheel movement for current frame."""

    return float(_rl().get_mouse_wheel_move())


def rl_mouse_down(button: int) -> bool:
    """Return raw Raylib mouse-down state for ``button``."""

    return bool(_rl().is_mouse_button_down(button))


def rl_mouse_pressed(button: int) -> bool:
    """Return raw Raylib mouse-pressed event for ``button``."""

    return bool(_rl().is_mouse_button_pressed(button))


def is_hovered_at(rect: Rect, x: float, y: float) -> bool:
    """Return whether point ``x, y`` is inside ``rect``."""

    return rect_contains(rect, x, y)


def is_pressed_at(rect: Rect, x: float, y: float, mouse_down: bool) -> bool:
    """Return pressed state for point ``x, y`` and supplied button state."""

    return bool(mouse_down) and is_hovered_at(rect, x, y)


def is_clicked_at(rect: Rect, x: float, y: float, mouse_clicked: bool) -> bool:
    """Return click state for point ``x, y`` and supplied click event."""

    return bool(mouse_clicked) and is_hovered_at(rect, x, y)


def is_right_clicked_at(rect: Rect, x: float, y: float, mouse_clicked: bool) -> bool:
    """Return right-click state for point ``x, y`` and supplied click event."""

    return bool(mouse_clicked) and is_hovered_at(rect, x, y)
