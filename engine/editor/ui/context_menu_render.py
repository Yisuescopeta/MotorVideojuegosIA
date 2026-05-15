"""Impure pyray shell for pure context menus."""

from __future__ import annotations

from engine.editor.ui_core.controls.context_menu import ContextMenuModel
from engine.editor.ui_core.tokens import EDITOR_ACCENT, EDITOR_BORDER, EDITOR_PANEL, EDITOR_TEXT, EDITOR_TEXT_DISABLED


def render_context_menu(model: ContextMenuModel) -> None:
    try:
        import pyray
    except Exception:
        return
    if not _window_ready(pyray):
        return
    if not model.popup.visible:
        return
    x, y, w, h = model.popup.rect
    pyray.draw_rectangle_rec(pyray.Rectangle(x, y, w, h), _color(pyray, EDITOR_PANEL))
    for idx, item in enumerate(model.items):
        row_y = y + idx * model.item_height
        if idx == model.highlighted_index:
            pyray.draw_rectangle_rec(pyray.Rectangle(x, row_y, w, model.item_height), _color(pyray, EDITOR_ACCENT))
        if item.separator:
            pyray.draw_rectangle(int(x + 6), int(row_y + model.item_height / 2), int(w - 12), 1, _color(pyray, EDITOR_BORDER))
            continue
        color = EDITOR_TEXT if item.enabled else EDITOR_TEXT_DISABLED
        prefix = "✓ " if item.checked else ""
        pyray.draw_text(prefix + item.label, int(x + 8), int(row_y + 5), 12, _color(pyray, color))
        if item.shortcut:
            pyray.draw_text(item.shortcut, int(x + w - 60), int(row_y + 5), 12, _color(pyray, color))
        if item.has_submenu:
            pyray.draw_text(">", int(x + w - 14), int(row_y + 5), 12, _color(pyray, color))
    pyray.draw_rectangle_lines_ex(pyray.Rectangle(x, y, w, h), 1.0, _color(pyray, EDITOR_BORDER))
    if model.child_menu is not None:
        render_context_menu(model.child_menu)


def process_context_menu_pointer(model: ContextMenuModel) -> str | None:
    try:
        import pyray
    except Exception:
        return None
    if not _window_ready(pyray):
        return None
    mouse = pyray.get_mouse_position()
    model.highlight_at(mouse.x, mouse.y)
    if pyray.is_mouse_button_pressed(pyray.MouseButton.MOUSE_BUTTON_LEFT):
        return model.activate_at(mouse.x, mouse.y)
    if pyray.is_mouse_button_pressed(pyray.MouseButton.MOUSE_BUTTON_RIGHT):
        model.popup.handle_pointer_down(mouse.x, mouse.y)
    return None


def _color(pyray, color: tuple[int, int, int, int]):
    return pyray.Color(color[0], color[1], color[2], color[3])


def _window_ready(pyray) -> bool:
    return not hasattr(pyray, "is_window_ready") or bool(pyray.is_window_ready())
