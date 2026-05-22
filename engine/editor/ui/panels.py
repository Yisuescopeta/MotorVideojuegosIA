"""Reusable editor panel chrome for immediate-mode UI."""

from __future__ import annotations

from collections.abc import Sequence

from engine.editor.ui import input as ui_input
from engine.editor.ui.colors import to_ray_color
from engine.editor.ui.draw import (
    draw_border,
    draw_panel_background,
    draw_panel_shadow,
    draw_rounded_rect,
    draw_text_clipped,
)
from engine.editor.ui.geometry import Rect, inset_rect, split_top
from engine.editor.ui.theme import UNITY_DARK, EditorTheme, resolve_theme
from engine.editor.ui.tokens import CONTROL_PADDING_X, FONT_SIZE_SM, PANEL_PADDING, TAB_HEIGHT
from engine.editor.ui.widget_state import WidgetResult

PANEL_HEADER_HEIGHT = TAB_HEIGHT
PANEL_ACTION_SIZE = 18
PANEL_ACTION_GAP = 4

_clip_stack: list[Rect] = []


def _rl():
    import pyray as rl

    return rl


def _rectangle(rect: Rect):
    rl = _rl()
    x, y, w, h = rect
    return rl.Rectangle(float(x), float(y), float(w), float(h))


def _result(rect: Rect, *, value: object = None) -> WidgetResult:
    return WidgetResult(
        hovered=ui_input.is_hovered(rect),
        pressed=ui_input.is_pressed(rect),
        clicked=ui_input.is_clicked(rect),
        right_clicked=ui_input.is_right_clicked(rect),
        value=value,
    )


def _action_label(action: object) -> str:
    if isinstance(action, dict):
        return str(action.get("label") or action.get("text") or action.get("id") or "")
    return str(action)


def _draw_header_button(rect: Rect, label: str, theme: EditorTheme) -> WidgetResult:
    result = _result(rect, value=label)
    bg = theme.button_hover if result.hovered else theme.button
    if result.pressed:
        bg = theme.accent
    draw_rounded_rect(rect, bg, theme.button_radius)
    draw_border(rect, theme.border_hover if result.hovered else theme.border)
    draw_text_clipped(label, inset_rect(rect, 4), theme.text, FONT_SIZE_SM)
    return result


def draw_panel_header(
    rect: Rect,
    title: str,
    actions: Sequence[object] | None = None,
    active: bool = False,
    subtitle: str = "",
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Draw fixed panel header with uppercase title, menu button and optional actions."""

    theme = resolve_theme(theme)
    x, y, w, h = rect
    header_h = min(float(PANEL_HEADER_HEIGHT), max(0.0, h))
    header_rect = (x, y, w, header_h)
    _rl().draw_rectangle_rec(_rectangle(header_rect), to_ray_color(theme.panel_header if not active else theme.panel_alt))
    if active:
        _rl().draw_rectangle(int(x), int(y), int(w), 2, to_ray_color(theme.accent))

    right = x + w - PANEL_PADDING
    clicked_action: object | None = None

    menu_rect = (right - PANEL_ACTION_SIZE, y + 3, PANEL_ACTION_SIZE, max(0.0, header_h - 6))
    menu_result = _draw_header_button(menu_rect, "...", theme)
    right = menu_rect[0] - PANEL_ACTION_GAP

    action_results: list[WidgetResult] = []
    for action in reversed(list(actions or [])):
        label = _action_label(action)
        button_w = max(PANEL_ACTION_SIZE, min(72.0, len(label) * 6.0 + CONTROL_PADDING_X))
        action_rect = (right - button_w, y + 3, button_w, max(0.0, header_h - 6))
        action_result = _draw_header_button(action_rect, label, theme)
        action_results.append(action_result)
        if action_result.clicked:
            clicked_action = action
        right = action_rect[0] - PANEL_ACTION_GAP

    text_right = max(x + PANEL_PADDING, right - PANEL_ACTION_GAP)
    title_rect = (x + PANEL_PADDING, y + 4, max(0.0, text_right - x - PANEL_PADDING), 10)
    draw_text_clipped(title.upper(), title_rect, theme.text, FONT_SIZE_SM)
    if subtitle:
        subtitle_rect = (x + PANEL_PADDING, y + 14, max(0.0, text_right - x - PANEL_PADDING), 9)
        draw_text_clipped(subtitle, subtitle_rect, theme.text_muted, FONT_SIZE_SM)

    result = _result(header_rect, value={"title": title, "menu": menu_result.clicked, "action": clicked_action})
    result.clicked = result.clicked or menu_result.clicked or any(item.clicked for item in action_results)
    result.changed = clicked_action is not None or menu_result.clicked
    return result


def draw_editor_panel(
    rect: Rect,
    title: str,
    active: bool = False,
    subtitle: str = "",
    actions: Sequence[object] | None = None,
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Draw full editor panel frame and header."""

    theme = resolve_theme(theme)
    draw_panel_shadow(rect, theme.panel_radius)
    draw_panel_background(rect, theme)
    draw_border(rect, theme.accent if active else theme.border)
    header, _content = split_top(rect, PANEL_HEADER_HEIGHT)
    header_result = draw_panel_header(header, title, actions=actions, active=active, subtitle=subtitle, theme=theme)
    panel_result = _result(rect, value=rect)
    panel_result.clicked = panel_result.clicked or header_result.clicked
    panel_result.changed = header_result.changed
    panel_result.value = header_result.value if header_result.changed else rect
    return panel_result


def draw_editor_panel_frame(
    rect: Rect,
    title: str,
    active: bool = False,
    subtitle: str = "",
    actions: Sequence[object] | None = None,
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Alias for panel frame drawing used by editor layout."""

    return draw_editor_panel(rect, title, active=active, subtitle=subtitle, actions=actions, theme=theme)


def begin_panel_content(rect: Rect) -> None:
    """Begin clipped panel content region."""

    x, y, w, h = rect
    safe_rect = (x, y, max(0.0, w), max(0.0, h))
    _clip_stack.append(safe_rect)
    _rl().begin_scissor_mode(int(safe_rect[0]), int(safe_rect[1]), int(safe_rect[2]), int(safe_rect[3]))


def end_panel_content() -> None:
    """End latest panel content clipping region."""

    if not _clip_stack:
        return

    _clip_stack.pop()
    _rl().end_scissor_mode()
    if _clip_stack:
        safe_rect = _clip_stack[-1]
        _rl().begin_scissor_mode(int(safe_rect[0]), int(safe_rect[1]), int(safe_rect[2]), int(safe_rect[3]))
