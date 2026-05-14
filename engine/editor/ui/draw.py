"""Small pyray drawing wrappers for editor chrome."""

from __future__ import annotations

from engine.editor.ui.colors import to_ray_color, with_alpha
from engine.editor.ui.geometry import Rect, inset_rect, split_top
from engine.editor.ui.theme import UNITY_DARK, EditorTheme, resolve_theme
from engine.editor.ui.tokens import (
    CONTROL_PADDING_Y,
    EDITOR_ACCENT,
    EDITOR_TEXT,
    FONT_SIZE_SM,
    PANEL_PADDING,
    PANEL_RADIUS,
    RGBA,
    TAB_HEIGHT,
)


def _rl():
    import pyray as rl

    return rl


def _rectangle(rect: Rect):
    rl = _rl()
    x, y, w, h = rect
    return rl.Rectangle(float(x), float(y), float(w), float(h))


def draw_rounded_rect(rect: Rect, color: RGBA, radius: float = PANEL_RADIUS) -> None:
    rl = _rl()
    x, y, w, h = rect
    roundness = 0.0 if min(w, h) <= 0 else max(0.0, min(1.0, radius / min(w, h)))
    rl.draw_rectangle_rounded(_rectangle(rect), roundness, 8, to_ray_color(color))


def draw_panel_background(rect: Rect, theme: EditorTheme | None = UNITY_DARK) -> None:
    theme = resolve_theme(theme)
    draw_rounded_rect(rect, theme.panel, PANEL_RADIUS)


def draw_panel_header(rect: Rect, title: str | None = None, theme: EditorTheme | None = UNITY_DARK) -> None:
    theme = resolve_theme(theme)
    rl = _rl()
    header, _ = split_top(rect, TAB_HEIGHT)
    rl.draw_rectangle_rec(_rectangle(header), to_ray_color(theme.panel_header))
    if title:
        x, y, _, _ = header
        rl.draw_text(
            title,
            int(x + PANEL_PADDING),
            int(y + CONTROL_PADDING_Y),
            FONT_SIZE_SM,
            to_ray_color(theme.text),
        )


def draw_border(rect: Rect, color: RGBA | None = None, thickness: int = 1) -> None:
    rl = _rl()
    rl.draw_rectangle_lines_ex(_rectangle(rect), thickness, to_ray_color(color or resolve_theme(None).border))


def draw_separator(rect: Rect, vertical: bool = False, color: RGBA | None = None) -> None:
    rl = _rl()
    x, y, w, h = rect
    line_color = to_ray_color(color or resolve_theme(None).border)
    if vertical:
        rl.draw_line(int(x + w / 2), int(y), int(x + w / 2), int(y + h), line_color)
    else:
        rl.draw_line(int(x), int(y + h / 2), int(x + w), int(y + h / 2), line_color)


def draw_text_clipped(text: str, rect: Rect, color: RGBA = EDITOR_TEXT, font_size: int = 10) -> None:
    rl = _rl()
    x, y, w, h = rect
    rl.begin_scissor_mode(int(x), int(y), int(w), int(h))
    try:
        rl.draw_text(text, int(x), int(y), font_size, to_ray_color(color))
    finally:
        rl.end_scissor_mode()


def draw_focus_outline(rect: Rect, color: RGBA = EDITOR_ACCENT) -> None:
    draw_border(inset_rect(rect, 1), color, 2)


def draw_hover_overlay(rect: Rect, color: RGBA | None = None) -> None:
    draw_rounded_rect(rect, color or with_alpha(EDITOR_TEXT, 18), PANEL_RADIUS)


def draw_selected_overlay(rect: Rect, color: RGBA | None = None) -> None:
    draw_rounded_rect(rect, color or with_alpha(EDITOR_ACCENT, 70), PANEL_RADIUS)
