"""Impure pyray shell for docking chrome in the editor."""

from __future__ import annotations

from engine.editor.ui.colors import to_ray_color
from engine.editor.ui.draw import draw_border, draw_rounded_rect, draw_text_clipped
from engine.editor.ui.geometry import Rect, rect_contains
from engine.editor.ui.widget_state import WidgetResult
from engine.editor.ui_core.tokens import (
    EDITOR_ACCENT,
    EDITOR_BORDER,
    EDITOR_PANEL,
    EDITOR_PANEL_HEADER,
    EDITOR_TEXT,
    FONT_SIZE_SM,
    PANEL_RADIUS,
    RGBA,
)

_SHADOW_COLOR: RGBA = (0, 0, 0, 60)
_SHADOW_OFFSET = 2.0
_TITLE_HEIGHT = 24.0
_BUTTON_SIZE = 16.0
_BUTTON_GAP = 2.0
_RESIZE_MARGIN = 6.0


def _rl():
    import pyray as rl
    return rl


def _draw_title_button(rect: Rect, label: str, color: RGBA) -> WidgetResult:
    rl = _rl()
    x, y, w, h = rect
    mx = float(rl.get_mouse_position().x)
    my = float(rl.get_mouse_position().y)
    inside = rect_contains(rect, mx, my)
    pressed = inside and rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT)
    clicked = inside and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)
    bg: RGBA = EDITOR_ACCENT if pressed else (60, 60, 60, 255) if inside else EDITOR_PANEL_HEADER
    draw_rounded_rect(rect, bg, 2)
    rl.draw_text(label, int(x + 3), int(y + 2), 8, to_ray_color(color))
    return WidgetResult(hovered=inside, pressed=pressed, clicked=clicked, value=label)


def draw_floating_window(
    rect: Rect, title: str, *, is_dragging: bool = False
) -> WidgetResult:
    """Draw a floating dock window with title bar, dock and close buttons.

    Returns WidgetResult with value dict containing ``dock``, ``close``,
    and ``title_drag`` boolean flags.
    """
    rl = _rl()
    x, y, w, h = rect

    # Shadow
    shadow_rect = (x + _SHADOW_OFFSET, y + _SHADOW_OFFSET, w, h)
    draw_rounded_rect(shadow_rect, _SHADOW_COLOR, PANEL_RADIUS + _SHADOW_OFFSET)

    # Panel background
    draw_rounded_rect(rect, EDITOR_PANEL, PANEL_RADIUS)

    # Title bar
    title_rect = (x, y, w, _TITLE_HEIGHT)
    draw_rounded_rect(title_rect, EDITOR_PANEL_HEADER, PANEL_RADIUS)
    rl.draw_rectangle(
        int(x), int(y + _TITLE_HEIGHT - PANEL_RADIUS),
        int(w), int(PANEL_RADIUS),
        to_ray_color(EDITOR_PANEL_HEADER),
    )

    # Title text
    title_text_x = x + 8.0
    title_text_w = w - (_BUTTON_SIZE * 2 + _BUTTON_GAP + 8.0 + 8.0)
    draw_text_clipped(
        title,
        (title_text_x, y + 4, max(0.0, title_text_w), _TITLE_HEIGHT - 8),
        EDITOR_TEXT,
        FONT_SIZE_SM,
    )

    # Close button — rightmost
    close_x = x + w - _BUTTON_SIZE - 4
    close_rect = (
        close_x, y + (_TITLE_HEIGHT - _BUTTON_SIZE) / 2,
        _BUTTON_SIZE, _BUTTON_SIZE,
    )
    close_result = _draw_title_button(close_rect, "X", EDITOR_TEXT)

    # Dock button — left of close
    dock_x = close_x - _BUTTON_SIZE - _BUTTON_GAP
    dock_rect = (
        dock_x, y + (_TITLE_HEIGHT - _BUTTON_SIZE) / 2,
        _BUTTON_SIZE, _BUTTON_SIZE,
    )
    dock_result = _draw_title_button(dock_rect, "D", EDITOR_TEXT)

    # Border
    border_color = EDITOR_ACCENT if is_dragging else EDITOR_BORDER
    draw_border(rect, border_color)

    # Title drag detection
    mx = float(rl.get_mouse_position().x)
    my = float(rl.get_mouse_position().y)
    title_drag = (
        rect_contains(title_rect, mx, my)
        and not rect_contains(dock_rect, mx, my)
        and not rect_contains(close_rect, mx, my)
        and rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT)
    )

    return WidgetResult(
        clicked=close_result.clicked or dock_result.clicked,
        value={
            "dock": dock_result.clicked,
            "close": close_result.clicked,
            "title_drag": title_drag,
        },
    )


def hit_test_floating_window(
    rect: Rect, title: str, mouse: tuple[float, float]
) -> dict[str, bool]:
    """Pure geometry hit-test for a floating window.

    Returns dict with keys ``title_hit``, ``dock_hit``, ``close_hit``,
    ``resize_hit``, and ``body_hit``.
    """
    del title  # preserved for caller convenience
    x, y, w, h = rect
    mx, my = mouse

    if not rect_contains(rect, mx, my):
        return {
            "title_hit": False, "dock_hit": False, "close_hit": False,
            "resize_hit": False, "body_hit": False,
        }

    close_x = x + w - _BUTTON_SIZE - 4
    close_rect = (
        close_x, y + (_TITLE_HEIGHT - _BUTTON_SIZE) / 2,
        _BUTTON_SIZE, _BUTTON_SIZE,
    )
    close_hit = rect_contains(close_rect, mx, my)

    dock_x = close_x - _BUTTON_SIZE - _BUTTON_GAP
    dock_rect = (
        dock_x, y + (_TITLE_HEIGHT - _BUTTON_SIZE) / 2,
        _BUTTON_SIZE, _BUTTON_SIZE,
    )
    dock_hit = rect_contains(dock_rect, mx, my)

    title_rect = (x, y, w, _TITLE_HEIGHT)
    title_hit = rect_contains(title_rect, mx, my) and not dock_hit and not close_hit

    resize_hit = (mx >= x + w - _RESIZE_MARGIN) or (my >= y + h - _RESIZE_MARGIN)
    body_hit = not title_hit and not resize_hit

    return {
        "title_hit": title_hit,
        "dock_hit": dock_hit,
        "close_hit": close_hit,
        "resize_hit": resize_hit,
        "body_hit": body_hit,
    }


def draw_auto_hide_collapsed_strip(
    area_id: str,
    rect: Rect,
    edge: str,
    tabs: list[str],
    *,
    hovered: bool = False,
    animation: float = 0.0,
) -> WidgetResult:
    """Draw a collapsed auto-hide strip on the given edge.

    ``edge`` must be ``'left'``, ``'right'``, or ``'bottom'``.
    ``animation``: 0.0 = fully collapsed strip visible, 1.0 = fully expanded.

    Returns WidgetResult with value dict containing ``'pinned'`` flag.
    """
    rl = _rl()
    animation = max(0.0, min(1.0, float(animation)))
    x, y, w, h = rect

    fade_alpha = max(20, int(180 * (1.0 - animation)))
    if not hovered:
        fade_alpha = max(20, int(120 * (1.0 - animation)))

    bg: RGBA = (EDITOR_PANEL[0], EDITOR_PANEL[1], EDITOR_PANEL[2], fade_alpha)
    draw_rounded_rect(rect, bg, 0)

    # Pin icon button
    pin_size = 16.0
    if edge in ("left", "right"):
        pin_rect = (x + (w - pin_size) / 2, y + 8, pin_size, pin_size)
    else:
        pin_rect = (x + 8, y + (h - pin_size) / 2, pin_size, pin_size)

    pin_hit = rect_contains(
        pin_rect,
        float(rl.get_mouse_position().x),
        float(rl.get_mouse_position().y),
    )
    pin_clicked = pin_hit and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)
    pin_bg: RGBA = (
        (EDITOR_ACCENT[0], EDITOR_ACCENT[1], EDITOR_ACCENT[2], fade_alpha)
        if pin_hit else (60, 60, 60, fade_alpha)
    )
    draw_rounded_rect(pin_rect, pin_bg, 2)

    pin_text_color: RGBA = (
        EDITOR_TEXT if fade_alpha > 80 else (200, 200, 200, fade_alpha)
    )
    rl.draw_text(
        "P", int(pin_rect[0] + 3), int(pin_rect[1] + 2),
        8, to_ray_color(pin_text_color),
    )

    # Area name abbreviation (first 3 chars)
    abbrev = area_id[:3].upper()
    text_color: RGBA = (EDITOR_TEXT[0], EDITOR_TEXT[1], EDITOR_TEXT[2], fade_alpha)
    if edge in ("left", "right"):
        char_y = y + 32.0
        for ch in abbrev:
            rl.draw_text(ch, int(x + 4), int(char_y), 10, to_ray_color(text_color))
            char_y += 14.0
    else:
        char_x = x + 32.0
        for ch in abbrev:
            rl.draw_text(ch, int(char_x), int(y + 4), 10, to_ray_color(text_color))
            char_x += 14.0

    # Tab count indicator
    if tabs:
        count_text = str(len(tabs))
        if edge in ("left", "right"):
            rl.draw_text(
                count_text, int(x + w - 14), int(y + h - 18),
                9, to_ray_color(text_color),
            )
        else:
            rl.draw_text(
                count_text, int(x + 8), int(y + h - 16),
                9, to_ray_color(text_color),
            )

    return WidgetResult(clicked=pin_clicked, value={"pinned": pin_clicked})


def draw_drag_preview(
    mouse_xy: tuple[float, float],
    tab_label: str,
    drop_zone_rects: list[tuple[str, Rect]],
    *,
    highlight_zone: str | None = None,
) -> None:
    """Draw drag-and-drop preview with tab label and highlighted drop zones.

    ``drop_zone_rects`` is a list of ``(zone_id, rect)`` pairs.
    ``highlight_zone`` is the zone_id currently under the mouse.
    """
    rl = _rl()
    mx, my = mouse_xy

    # Drag preview at mouse position
    preview_w = 120.0
    preview_h = 24.0
    preview_rect = (mx + 12, my + 12, preview_w, preview_h)
    preview_alpha: RGBA = (80, 80, 80, 150)
    draw_rounded_rect(preview_rect, preview_alpha, 3)
    draw_border(preview_rect, EDITOR_ACCENT)
    rl.draw_text(
        tab_label,
        int(preview_rect[0] + 6), int(preview_rect[1] + 5),
        FONT_SIZE_SM, to_ray_color(EDITOR_TEXT),
    )

    # Drop zone highlights
    for zone_id, zone_rect in drop_zone_rects:
        if zone_id == highlight_zone:
            highlight_alpha: RGBA = (
                EDITOR_ACCENT[0], EDITOR_ACCENT[1], EDITOR_ACCENT[2], 60,
            )
            draw_rounded_rect(zone_rect, highlight_alpha, PANEL_RADIUS)
            draw_border(zone_rect, EDITOR_ACCENT, 2)


__all__ = [
    "draw_auto_hide_collapsed_strip",
    "draw_drag_preview",
    "draw_floating_window",
    "hit_test_floating_window",
]
