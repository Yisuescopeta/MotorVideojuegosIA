"""Impure pyray shell for pure dropdowns and comboboxes."""

from __future__ import annotations

from engine.editor.ui_core.controls.dropdown import DropdownModel
from engine.editor.ui_core.tokens import (
    EDITOR_ACCENT,
    EDITOR_BORDER,
    EDITOR_PANEL,
    EDITOR_PANEL_ALT,
    EDITOR_TEXT,
    EDITOR_TEXT_DISABLED,
)


def render_dropdown(model: DropdownModel, rect: tuple[float, float, float, float]) -> None:
    try:
        import pyray
    except Exception:
        return
    if not _window_ready(pyray):
        return
    x, y, w, h = rect
    pyray.draw_rectangle_rec(pyray.Rectangle(x, y, w, h), _color(pyray, EDITOR_PANEL_ALT))
    pyray.draw_rectangle_lines_ex(pyray.Rectangle(x, y, w, h), 1.0, _color(pyray, EDITOR_BORDER))
    pyray.draw_text(model.display_label, int(x + 6), int(y + 5), 12, _color(pyray, EDITOR_TEXT))
    if not model.popup.visible:
        return
    px, py, pw, ph = model.popup.rect
    pyray.draw_rectangle_rec(pyray.Rectangle(px, py, pw, ph), _color(pyray, EDITOR_PANEL))
    for idx, option in enumerate(model.visible_options):
        row_y = py + idx * model.item_height
        if option.id == model.selected_id:
            pyray.draw_rectangle_rec(pyray.Rectangle(px, row_y, pw, model.item_height), _color(pyray, EDITOR_ACCENT))
        color = EDITOR_TEXT if option.enabled else EDITOR_TEXT_DISABLED
        pyray.draw_text(option.label, int(px + 6), int(row_y + 5), 12, _color(pyray, color))
    _draw_scroll_thumb(pyray, model, px, py, pw, ph)
    pyray.draw_rectangle_lines_ex(pyray.Rectangle(px, py, pw, ph), 1.0, _color(pyray, EDITOR_BORDER))


def process_dropdown_pointer(model: DropdownModel) -> str | None:
    try:
        import pyray
    except Exception:
        return None
    if not _window_ready(pyray):
        return None
    if not model.popup.visible:
        return None
    mouse = pyray.get_mouse_position()
    if pyray.is_mouse_button_pressed(pyray.MouseButton.MOUSE_BUTTON_LEFT):
        return model.select_at(mouse.x, mouse.y)
    wheel = pyray.get_mouse_wheel_move() if hasattr(pyray, "get_mouse_wheel_move") else 0
    if wheel:
        model.scroll_by(-int(wheel))
    return None


def _draw_scroll_thumb(pyray, model: DropdownModel, x: float, y: float, w: float, h: float) -> None:
    total = len(model.filtered_options)
    visible = model.visible_item_count(total)
    if total <= visible or visible <= 0 or h <= 0:
        return
    track_w = 6.0
    thumb_h = max(12.0, h * (visible / total))
    max_offset = max(1, total - visible)
    thumb_y = y + (h - thumb_h) * (model.scroll_offset / max_offset)
    pyray.draw_rectangle_rec(pyray.Rectangle(x + w - track_w - 2, thumb_y, track_w, thumb_h), _color(pyray, EDITOR_BORDER))


def _color(pyray, color: tuple[int, int, int, int]):
    return pyray.Color(color[0], color[1], color[2], color[3])


def _window_ready(pyray) -> bool:
    return not hasattr(pyray, "is_window_ready") or bool(pyray.is_window_ready())
