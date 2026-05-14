"""Immediate-mode editor widgets built on Raylib primitives."""

from __future__ import annotations

from typing import Any

from engine.editor.ui import input as ui_input
from engine.editor.ui.draw import (
    draw_border,
    draw_focus_outline,
    draw_panel_background,
    draw_rounded_rect,
    draw_separator,
    draw_tab_accent_bar,
    draw_text_clipped,
)
from engine.editor.ui.draw import (
    draw_panel_header as draw_panel_header_background,
)
from engine.editor.ui.geometry import Rect, inset_rect, split_left
from engine.editor.ui.icons import draw_icon
from engine.editor.ui.theme import UNITY_DARK, EditorTheme, resolve_theme
from engine.editor.ui.tokens import (
    CONTROL_PADDING_X,
    CONTROL_PADDING_Y,
    EDITOR_ACCENT,
    EDITOR_DANGER,
    EDITOR_SUCCESS,
    EDITOR_TEXT,
    EDITOR_TEXT_MUTED,
    EDITOR_WARNING,
    FONT_SIZE_SM,
    ICON_SIZE_SM,
    RGBA,
)
from engine.editor.ui.widget_state import WidgetResult, resolve_visual_state


def _rl():
    import pyray as rl

    return rl


def _rectangle(rect: Rect):
    rl = _rl()
    x, y, w, h = rect
    return rl.Rectangle(float(x), float(y), float(w), float(h))


def _result(rect: Rect, *, enabled: bool = True, value: object = None) -> WidgetResult:
    hovered = enabled and ui_input.is_hovered(rect)
    pressed = enabled and ui_input.is_pressed(rect)
    clicked = enabled and ui_input.is_clicked(rect)
    right_clicked = enabled and ui_input.is_right_clicked(rect)
    return WidgetResult(hovered, pressed, clicked, right_clicked, value=value)


def _text_rect(rect: Rect) -> Rect:
    return inset_rect(rect, CONTROL_PADDING_Y)


def _decode_ffi_text(rl: Any, buffer: Any, fallback: str) -> str:
    ffi = getattr(rl, "ffi", None)
    if ffi is None:
        return fallback
    try:
        return ffi.string(buffer).decode("utf-8", errors="replace")
    except (AttributeError, TypeError, ValueError):
        return fallback


def _parse_textbox_result(raw: Any, current_text: str) -> tuple[str, bool] | None:
    if not isinstance(raw, (tuple, list)):
        return None
    next_text = current_text
    changed = False
    found_text = False
    found_changed = False
    for item in raw:
        if isinstance(item, str) and not found_text:
            next_text = item
            found_text = True
        elif isinstance(item, bool) and not found_changed:
            changed = item
            found_changed = True
    if found_text or found_changed:
        return next_text, changed
    return None


def _parse_dropdown_result(raw: Any, current_active: int) -> tuple[int, bool] | None:
    if not isinstance(raw, (tuple, list)):
        return None
    next_active = current_active
    changed = False
    found_active = False
    found_changed = False
    for item in raw:
        if isinstance(item, bool) and not found_changed:
            changed = item
            found_changed = True
        elif isinstance(item, int) and not found_active:
            next_active = item
            found_active = True
    if found_active or found_changed:
        return next_active, changed
    return None


def editor_label(
    rect: Rect,
    text: str,
    *,
    color: RGBA = EDITOR_TEXT,
    font_size: int = FONT_SIZE_SM,
) -> WidgetResult:
    """Draw static editor text and return it as widget value."""

    draw_text_clipped(text, _text_rect(rect), color, font_size)
    return WidgetResult(value=text)


def editor_button(
    rect: Rect,
    text: str,
    *,
    enabled: bool = True,
    active: bool = False,
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Draw a clickable editor button and report pointer interaction."""

    theme = resolve_theme(theme)
    result = _result(rect, enabled=enabled, value=text)
    state = resolve_visual_state(enabled, result.hovered, result.pressed, active)
    color = theme.button
    if state.name in {"HOVER", "FOCUSED"}:
        color = theme.button_hover
    elif state.name in {"PRESSED", "ACTIVE", "SELECTED"}:
        color = theme.accent
    elif state.name == "DISABLED":
        color = theme.raygui_dark
    draw_rounded_rect(rect, color)
    draw_border(rect, theme.border_hover if result.hovered else theme.border)
    text_color = theme.text if enabled else theme.text_disabled
    draw_text_clipped(text, _text_rect(rect), text_color, FONT_SIZE_SM)
    return result


def editor_icon_button(
    rect: Rect,
    icon_name: str,
    *,
    enabled: bool = True,
    active: bool = False,
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Draw a button with centered primitive icon."""

    theme = resolve_theme(theme)
    result = editor_button(rect, "", enabled=enabled, active=active, theme=theme)
    draw_icon(icon_name, inset_rect(rect, 3), theme.text if enabled else theme.text_disabled, theme)
    result.value = icon_name
    return result


def editor_toggle_button(
    rect: Rect,
    text: str,
    value: bool,
    *,
    enabled: bool = True,
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Draw a toggle button and return next boolean value on click."""

    theme = resolve_theme(theme)
    result = editor_button(rect, text, enabled=enabled, active=value, theme=theme)
    if result.clicked:
        result.changed = True
        result.value = not value
    else:
        result.value = value
    return result


def editor_tab(
    rect: Rect,
    text: str,
    selected: bool = False,
    *,
    active: bool | None = None,
    icon: str = "",
    closeable: bool = False,
    enabled: bool = True,
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Draw one tab and report click state for selection changes."""

    theme = resolve_theme(theme)
    if active is not None:
        selected = active
    result = editor_button(rect, text, enabled=enabled, active=selected, theme=theme)
    if selected:
        draw_tab_accent_bar(rect, theme.accent)
    if icon:
        x, y, _w, h = rect
        draw_icon(icon, (x + CONTROL_PADDING_X, y + (h - ICON_SIZE_SM) / 2, ICON_SIZE_SM, ICON_SIZE_SM), theme.text, theme)
    if closeable:
        x, y, w, h = rect
        draw_icon("close", (x + w - ICON_SIZE_SM - CONTROL_PADDING_X, y + (h - ICON_SIZE_SM) / 2, ICON_SIZE_SM, ICON_SIZE_SM), theme.text, theme)
    return result


def editor_tab_bar(
    rect: Rect,
    tabs: list[str] | list[dict[str, Any]],
    selected_index: int = 0,
    *,
    active_index: int | None = None,
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Draw equal-width tabs and return selected tab index."""

    theme = resolve_theme(theme)
    if active_index is not None:
        selected_index = active_index
    if not tabs:
        return WidgetResult(value=selected_index)
    x, y, w, h = rect
    tab_w = w / len(tabs)
    result = WidgetResult(value=selected_index)
    for index, tab in enumerate(tabs):
        title = tab.get("text", "") if isinstance(tab, dict) else tab
        icon = str(tab.get("icon", "")) if isinstance(tab, dict) else ""
        closeable = bool(tab.get("closeable", False)) if isinstance(tab, dict) else False
        tab_rect = (x + tab_w * index, y, tab_w, h)
        tab_result = editor_tab(tab_rect, str(title), index == selected_index, icon=icon, closeable=closeable, theme=theme)
        if tab_result.clicked:
            result.clicked = True
            result.changed = index != selected_index
            result.value = index
    return result


def editor_panel(
    rect: Rect,
    title: str | None = None,
    *,
    collapsible: bool = False,
    collapsed: bool = False,
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Draw editor panel background and optional interactive header."""

    theme = resolve_theme(theme)
    draw_panel_background(rect, theme)
    draw_border(rect, theme.border)
    if title is None:
        return _result(rect, value=rect)
    x, y, w, _h = rect
    header_result = editor_panel_header((x, y, w, 24), title, collapsible=collapsible, collapsed=collapsed, theme=theme)
    result = _result(rect, value=rect)
    if header_result.changed:
        result.clicked = header_result.clicked
        result.changed = True
        result.value = header_result.value
    return result


def editor_panel_header(
    rect: Rect,
    title: str,
    *,
    collapsible: bool = False,
    collapsed: bool = False,
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Draw panel header and report collapse toggle changes when enabled."""

    theme = resolve_theme(theme)
    draw_panel_header_background(rect, title, theme)
    result = _result(rect, value=title)
    if collapsible and result.clicked:
        result.changed = True
        result.value = {"collapsed": not collapsed}
    return result


def editor_separator(
    rect: Rect,
    *,
    vertical: bool = False,
    color: RGBA | None = None,
) -> WidgetResult:
    """Draw horizontal or vertical editor separator."""

    draw_separator(rect, vertical, color)
    return WidgetResult(value=rect)


def editor_badge(
    rect: Rect,
    text: str,
    *,
    color: RGBA = EDITOR_ACCENT,
) -> WidgetResult:
    """Draw small rounded label badge."""

    draw_rounded_rect(rect, color)
    draw_text_clipped(text, _text_rect(rect), EDITOR_TEXT, FONT_SIZE_SM)
    return WidgetResult(value=text)


def editor_status_pill(
    rect: Rect,
    text: str,
    *,
    kind: str = "info",
    ok: bool | None = None,
) -> WidgetResult:
    """Draw status badge using semantic ``kind`` or legacy ``ok`` flag."""

    if ok is not None:
        kind = "success" if ok else "error"
    colors = {
        "info": EDITOR_ACCENT,
        "accent": EDITOR_ACCENT,
        "success": EDITOR_SUCCESS,
        "warning": EDITOR_WARNING,
        "error": EDITOR_DANGER,
        "danger": EDITOR_DANGER,
    }
    return editor_badge(rect, text, color=colors.get(kind, EDITOR_ACCENT))


def editor_checkbox(
    rect: Rect,
    label: str,
    value: bool,
    *,
    enabled: bool = True,
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Draw checkbox with label and return next boolean value on click."""

    theme = resolve_theme(theme)
    box, text_rect = split_left(rect, ICON_SIZE_SM + CONTROL_PADDING_X)
    result = _result(rect, enabled=enabled, value=value)
    draw_border(inset_rect(box, 3), theme.border_hover if result.hovered else theme.border)
    if value:
        draw_icon("check", inset_rect(box, 3), theme.accent, theme)
    editor_label(text_rect, label, color=theme.text if enabled else theme.text_disabled)
    if result.clicked:
        result.changed = True
        result.value = not value
    return result


def editor_slider_float(
    rect: Rect,
    value: float,
    min_val: float,
    max_val: float,
    *,
    step: float = 0.0,
    enabled: bool = True,
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Draw float slider and return adjusted value while pressed."""

    theme = resolve_theme(theme)
    result = _result(rect, enabled=enabled, value=value)
    x, y, w, h = rect
    span = max(0.000001, max_val - min_val)
    t = max(0.0, min(1.0, (value - min_val) / span))
    draw_rounded_rect((x, y + h / 2 - 2, w, 4), theme.raygui_dark)
    draw_rounded_rect((x, y + h / 2 - 2, w * t, 4), theme.accent)
    draw_rounded_rect((x + w * t - 4, y + 2, 8, h - 4), theme.button_hover)
    if result.pressed:
        mx, _ = ui_input.mouse_position()
        new_value = min_val + max(0.0, min(1.0, (mx - x) / max(1.0, w))) * span
        if step > 0.0:
            new_value = min_val + round((new_value - min_val) / step) * step
            new_value = max(min_val, min(max_val, new_value))
        result.changed = abs(new_value - value) > 0.000001
        result.value = new_value
    return result


def editor_text_field_simple(
    rect: Rect,
    text: str,
    *,
    placeholder: str = "",
    max_chars: int = 256,
    focused: bool = False,
    enabled: bool = True,
    theme: EditorTheme | None = UNITY_DARK,
) -> WidgetResult:
    """Draw simple non-editing text field shell for editor forms."""

    theme = resolve_theme(theme)
    value = text[:max_chars]
    result = _result(rect, enabled=enabled, value=value)
    draw_rounded_rect(rect, theme.raygui_dark)
    draw_border(rect, theme.accent if focused else theme.border)
    display_text = value if value else placeholder
    text_color = theme.text if value and enabled else EDITOR_TEXT_MUTED
    if not enabled:
        text_color = theme.text_disabled
    draw_text_clipped(display_text, _text_rect(rect), text_color)
    if focused:
        draw_focus_outline(rect, theme.accent)
    return result


def raygui_textbox_bridge(
    rect: Rect,
    text: str,
    *,
    max_chars: int | None = None,
    edit_mode: bool = False,
    max_length: int = 256,
) -> WidgetResult:
    """Bridge Raygui text box output into ``WidgetResult``."""

    if max_chars is not None:
        max_length = max_chars
    rl = _rl()
    value = text[:max_length]
    rect_obj = _rectangle(rect)
    raw = None
    ffi = getattr(rl, "ffi", None)
    if ffi is not None:
        try:
            encoded = value.encode("utf-8")[: max(0, max_length - 1)]
            buffer = ffi.new("char[]", max_length + 1)
            for index, byte in enumerate(encoded):
                buffer[index] = byte
            raw = rl.gui_text_box(rect_obj, buffer, max_length, edit_mode)
            value = _decode_ffi_text(rl, buffer, value)[:max_length]
        except (AttributeError, TypeError, ValueError):
            raw = rl.gui_text_box(rect_obj, value, max_length, edit_mode)
    else:
        raw = rl.gui_text_box(rect_obj, value, max_length, edit_mode)
    parsed = _parse_textbox_result(raw, value)
    if parsed is not None:
        value, changed = parsed
        value = value[:max_length]
    else:
        changed = bool(raw)
    return WidgetResult(changed=changed, value=value)


def raygui_dropdown_bridge(
    rect: Rect,
    options: list[str],
    active: int = 0,
    *,
    active_index: int | None = None,
    edit_mode: bool = False,
) -> WidgetResult:
    """Bridge Raygui dropdown output into ``WidgetResult``."""

    rl = _rl()
    text = ";".join(options)
    if active_index is not None:
        active = active_index
    next_active = int(active)
    rect_obj = _rectangle(rect)
    raw = None
    ffi = getattr(rl, "ffi", None)
    if ffi is not None:
        try:
            active_ptr = ffi.new("int *", next_active)
            raw = rl.gui_dropdown_box(rect_obj, text, active_ptr, edit_mode)
            next_active = int(active_ptr[0])
        except (AttributeError, TypeError, ValueError):
            raw = rl.gui_dropdown_box(rect_obj, text, next_active, edit_mode)
    else:
        raw = rl.gui_dropdown_box(rect_obj, text, next_active, edit_mode)
    parsed = _parse_dropdown_result(raw, next_active)
    if parsed is not None:
        next_active, changed = parsed
    else:
        changed = bool(raw)
    return WidgetResult(changed=changed, value=next_active)
