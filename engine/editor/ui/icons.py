"""Primitive icon drawing for editor widgets."""

from __future__ import annotations

from engine.editor.ui.colors import to_ray_color
from engine.editor.ui.geometry import Rect
from engine.editor.ui.theme import UNITY_DARK, EditorTheme
from engine.editor.ui.tokens import EDITOR_TEXT, RGBA

ICON_PLAY = "play"
ICON_PAUSE = "pause"
ICON_STOP = "stop"
ICON_CLOSE = "close"
ICON_PLUS = "plus"
ICON_MINUS = "minus"
ICON_CHECK = "check"
ICON_ARROW_DOWN = "arrow_down"
ICON_CHEVRON_RIGHT = "chevron_right"
ICON_SEARCH = "search"
ICON_GEAR = "gear"

KNOWN_ICONS = {
    ICON_PLAY,
    ICON_PAUSE,
    ICON_STOP,
    ICON_CLOSE,
    ICON_PLUS,
    ICON_MINUS,
    ICON_CHECK,
    ICON_ARROW_DOWN,
    ICON_CHEVRON_RIGHT,
    ICON_SEARCH,
    ICON_GEAR,
}


def _rl():
    import pyray as rl

    return rl


def _vec2(x: int, y: int):
    return _rl().Vector2(float(x), float(y))


def icon_exists(name: str) -> bool:
    """Return whether ``name`` is a known primitive editor icon."""

    return name in KNOWN_ICONS


def draw_icon(
    icon_name: str,
    rect: Rect,
    color: RGBA = EDITOR_TEXT,
    theme: EditorTheme = UNITY_DARK,
) -> None:
    """Draw a known primitive icon centered inside ``rect``.

    Unknown icon names are ignored.
    """

    if not icon_exists(icon_name):
        return
    del theme
    rl = _rl()
    c = to_ray_color(color)
    x, y, w, h = rect
    cx = int(x + w / 2)
    cy = int(y + h / 2)
    left = int(x + w * 0.25)
    right = int(x + w * 0.75)
    top = int(y + h * 0.25)
    bottom = int(y + h * 0.75)

    if icon_name == ICON_PLAY:
        rl.draw_triangle(_vec2(left, top), _vec2(left, bottom), _vec2(right, cy), c)
    elif icon_name == ICON_PAUSE:
        bar_w = max(1, int(w * 0.18))
        rl.draw_rectangle(left, top, bar_w, bottom - top, c)
        rl.draw_rectangle(right - bar_w, top, bar_w, bottom - top, c)
    elif icon_name == ICON_STOP:
        rl.draw_rectangle(left, top, right - left, bottom - top, c)
    elif icon_name == ICON_CLOSE:
        rl.draw_line(left, top, right, bottom, c)
        rl.draw_line(right, top, left, bottom, c)
    elif icon_name == ICON_PLUS:
        rl.draw_line(left, cy, right, cy, c)
        rl.draw_line(cx, top, cx, bottom, c)
    elif icon_name == ICON_MINUS:
        rl.draw_line(left, cy, right, cy, c)
    elif icon_name == ICON_CHECK:
        rl.draw_line(left, cy, cx, bottom, c)
        rl.draw_line(cx, bottom, right, top, c)
    elif icon_name == ICON_ARROW_DOWN:
        rl.draw_triangle(_vec2(left, top), _vec2(right, top), _vec2(cx, bottom), c)
    elif icon_name == ICON_CHEVRON_RIGHT:
        rl.draw_line(left, top, right, cy, c)
        rl.draw_line(right, cy, left, bottom, c)
    elif icon_name == ICON_SEARCH:
        radius = max(2, int(min(w, h) * 0.2))
        rl.draw_circle_lines(cx - 2, cy - 2, radius, c)
        rl.draw_line(cx + radius - 2, cy + radius - 2, right, bottom, c)
    elif icon_name == ICON_GEAR:
        radius = max(3, int(min(w, h) * 0.25))
        rl.draw_circle_lines(cx, cy, radius, c)
        rl.draw_circle_lines(cx, cy, max(1, radius // 2), c)
        rl.draw_line(cx, top, cx, top + 3, c)
        rl.draw_line(cx, bottom - 3, cx, bottom, c)
        rl.draw_line(left, cy, left + 3, cy, c)
        rl.draw_line(right - 3, cy, right, cy, c)
