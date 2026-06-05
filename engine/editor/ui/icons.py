"""Editor icon facade with Godot hierarchy, Lucide, and primitive fallback."""

from __future__ import annotations

from engine.editor.ui.colors import to_ray_color
from engine.editor.ui.geometry import Rect
from engine.editor.ui.icon_provider import (
    draw_icon_from_pack as _draw_icon_from_pack,
    draw_icon as _draw_lucide_icon,
    icon_exists_in_pack as _icon_exists_in_pack,
)
from engine.editor.ui.icon_provider import (
    icon_exists as _lucide_icon_exists,
)
from engine.editor.ui.theme import UNITY_DARK, EditorTheme
from engine.editor.ui.tokens import (
    EDITOR_TEXT,
    RGBA,
)
from engine.editor.ui_core.icon_names import (
    ICON_AUDIO,
    ICON_ANIMATION,
    ICON_ARROW_DOWN,
    ICON_ARROW_UP,
    ICON_CAMERA,
    ICON_CANVAS,
    ICON_CHECK,
    ICON_CHEVRON_LEFT,
    ICON_CHEVRON_RIGHT,
    ICON_CLOSE,
    ICON_COLLIDER,
    ICON_COMPONENT,
    ICON_CONSOLE,
    ICON_COPY,
    ICON_ENTITY,
    ICON_EXPORT,
    ICON_FOLDER,
    ICON_GEAR,
    ICON_LIGHT,
    ICON_MATERIAL,
    ICON_MENU,
    ICON_MINUS,
    ICON_NODE2D,
    ICON_OPEN,
    ICON_PAUSE,
    ICON_PARTICLES,
    ICON_PLAY,
    ICON_PLUS,
    ICON_PREFAB,
    ICON_PROJECT,
    ICON_RIGIDBODY,
    ICON_SAVE,
    ICON_SCENE,
    ICON_SCRIPT,
    ICON_SEARCH,
    ICON_SPRITE,
    ICON_STOP,
    ICON_TERMINAL,
    ICON_TILEMAP,
    ICON_TRASH,
    ICON_UI_BUTTON,
    ICON_UNKNOWN,
    PUBLIC_ICON_NAMES,
)

_GODOT_HIERARCHY_COLOR = (255, 255, 255, 255)

PRIMITIVE_ICONS = {
    ICON_PLAY,
    ICON_PAUSE,
    ICON_STOP,
    ICON_CLOSE,
    ICON_PLUS,
    ICON_MINUS,
    ICON_CHECK,
    ICON_ARROW_DOWN,
    ICON_CHEVRON_LEFT,
    ICON_CHEVRON_RIGHT,
    ICON_SEARCH,
    ICON_GEAR,
    ICON_MENU,
    ICON_FOLDER,
    ICON_TRASH,
}

KNOWN_ICONS = set(PUBLIC_ICON_NAMES)
HIERARCHY_ICONS = {
    ICON_ENTITY,
    ICON_NODE2D,
    ICON_SPRITE,
    ICON_CAMERA,
    ICON_TILEMAP,
    ICON_COLLIDER,
    ICON_RIGIDBODY,
    ICON_AUDIO,
    ICON_ANIMATION,
    ICON_CANVAS,
    ICON_UI_BUTTON,
    ICON_LIGHT,
    ICON_PARTICLES,
}


def _rl():
    import pyray as rl

    return rl


def _vec2(x: int, y: int):
    return _rl().Vector2(float(x), float(y))


def icon_exists(name: str) -> bool:
    """Return whether ``name`` resolves to a supported editor icon."""

    return (
        name in KNOWN_ICONS
        or name in PRIMITIVE_ICONS
        or _icon_exists_in_pack("godot_hierarchy", name)
        or _lucide_icon_exists(name)
    )


def draw_icon(
    icon_name: str,
    rect: Rect,
    color: RGBA = EDITOR_TEXT,
    theme: EditorTheme = UNITY_DARK,
    *,
    size: int | None = None,
) -> None:
    """Draw an editor icon centered inside ``rect``.

    Hierarchy-specific Godot rendering is attempted first for semantic node
    icons. Lucide remains the primary general editor icon pack and primitive
    drawing remains the final fallback.
    """

    if icon_name in HIERARCHY_ICONS and _draw_icon_from_pack(
        "godot_hierarchy",
        icon_name,
        rect,
        _GODOT_HIERARCHY_COLOR,
        theme,
        size=size,
    ):
        return
    if _draw_lucide_icon(icon_name, rect, color, theme, size=size):
        return
    _draw_primitive_icon(icon_name, rect, color, theme, size=size)


def _draw_primitive_icon(
    icon_name: str,
    rect: Rect,
    color: RGBA = EDITOR_TEXT,
    theme: EditorTheme = UNITY_DARK,
    *,
    size: int | None = None,
) -> None:
    if icon_name not in PRIMITIVE_ICONS:
        return
    del theme
    rl = _rl()
    c = to_ray_color(color)
    x, y, w, h = rect
    cx = int(x + w / 2)
    cy = int(y + h / 2)

    if size is not None:
        half = size // 2
        left = cx - half
        right = cx + half
        top = cy - half
        bottom = cy + half
        icon_w = icon_h = size
    else:
        left = int(x + w * 0.25)
        right = int(x + w * 0.75)
        top = int(y + h * 0.25)
        bottom = int(y + h * 0.75)
        icon_w = int(w)
        icon_h = int(h)

    if icon_name == ICON_PLAY:
        rl.draw_triangle(_vec2(left, top), _vec2(left, bottom), _vec2(right, cy), c)
    elif icon_name == ICON_PAUSE:
        bar_w = max(1, int(icon_w * 0.18))
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
    elif icon_name == ICON_CHEVRON_LEFT:
        rl.draw_line(right, top, left, cy, c)
        rl.draw_line(left, cy, right, bottom, c)
    elif icon_name == ICON_CHEVRON_RIGHT:
        rl.draw_line(left, top, right, cy, c)
        rl.draw_line(right, cy, left, bottom, c)
    elif icon_name == ICON_SEARCH:
        radius = max(2, int(min(icon_w, icon_h) * 0.2))
        rl.draw_circle_lines(cx - 2, cy - 2, radius, c)
        rl.draw_line(cx + radius - 2, cy + radius - 2, right, bottom, c)
    elif icon_name == ICON_GEAR:
        radius = max(3, int(min(icon_w, icon_h) * 0.25))
        rl.draw_circle_lines(cx, cy, radius, c)
        rl.draw_circle_lines(cx, cy, max(1, radius // 2), c)
        rl.draw_line(cx, top, cx, top + 3, c)
        rl.draw_line(cx, bottom - 3, cx, bottom, c)
        rl.draw_line(left, cy, left + 3, cy, c)
        rl.draw_line(right - 3, cy, right, cy, c)
    elif icon_name == ICON_MENU:
        dot_radius = max(1, int(min(icon_w, icon_h) * 0.07))
        for dot_x in (left, cx, right):
            rl.draw_circle(dot_x, cy, dot_radius, c)
    elif icon_name == ICON_FOLDER:
        tab_w = max(2, int(icon_w * 0.35))
        tab_h = max(2, int(icon_h * 0.18))
        rl.draw_rectangle(left, top, tab_w, tab_h, c)
        rl.draw_rectangle_lines(left, top, right - left, bottom - top, c)
        rl.draw_line(left, top + tab_h, left + tab_w, top + tab_h, c)
        rl.draw_line(left + tab_w, top + tab_h, left + tab_w, top, c)
    elif icon_name == ICON_TRASH:
        lid_y = top + max(1, int(icon_h * 0.2))
        body_top = top + max(2, int(icon_h * 0.32))
        rl.draw_line(left, lid_y, right, lid_y, c)
        rl.draw_rectangle_lines(left + 2, body_top, max(1, right - left - 4), max(1, bottom - body_top), c)
        rl.draw_line(cx - 3, top, cx + 3, top, c)
        rl.draw_line(cx, top, cx, lid_y, c)


__all__ = [
    "ICON_AUDIO",
    "ICON_ANIMATION",
    "ICON_ARROW_DOWN",
    "ICON_ARROW_UP",
    "ICON_CAMERA",
    "ICON_CANVAS",
    "ICON_CHECK",
    "ICON_CHEVRON_LEFT",
    "ICON_CHEVRON_RIGHT",
    "ICON_CLOSE",
    "ICON_COLLIDER",
    "ICON_COMPONENT",
    "ICON_CONSOLE",
    "ICON_COPY",
    "ICON_ENTITY",
    "ICON_EXPORT",
    "ICON_FOLDER",
    "ICON_GEAR",
    "ICON_LIGHT",
    "ICON_MATERIAL",
    "ICON_MENU",
    "ICON_MINUS",
    "ICON_NODE2D",
    "ICON_OPEN",
    "ICON_PAUSE",
    "ICON_PARTICLES",
    "ICON_PLAY",
    "ICON_PLUS",
    "ICON_PREFAB",
    "ICON_PROJECT",
    "ICON_RIGIDBODY",
    "ICON_SAVE",
    "ICON_SCENE",
    "ICON_SCRIPT",
    "ICON_SEARCH",
    "ICON_SPRITE",
    "ICON_STOP",
    "ICON_TERMINAL",
    "ICON_TILEMAP",
    "ICON_TRASH",
    "ICON_UI_BUTTON",
    "ICON_UNKNOWN",
    "HIERARCHY_ICONS",
    "KNOWN_ICONS",
    "PRIMITIVE_ICONS",
    "draw_icon",
    "icon_exists",
]
