"""Impure pyray shell for pure TextInput."""

from __future__ import annotations

from engine.editor.ui_core.controls.text_input import TextInput
from engine.editor.ui_core.tokens import EDITOR_ACCENT, EDITOR_BORDER, EDITOR_PANEL_ALT, EDITOR_TEXT, EDITOR_TEXT_MUTED


def render_text_input(model: TextInput, focused: bool = False) -> None:
    try:
        import pyray
    except Exception:
        return
    if not _window_ready(pyray):
        return
    if not model.visible:
        return
    x, y, w, h = model.global_rect
    border = EDITOR_ACCENT if focused else EDITOR_BORDER
    _draw_rect(pyray, x, y, w, h, EDITOR_PANEL_ALT)
    pyray.draw_rectangle_lines_ex(pyray.Rectangle(x, y, w, h), 1.0, _color(pyray, border))
    text = model.display_text or model.placeholder
    color = EDITOR_TEXT if model.text else EDITOR_TEXT_MUTED
    pyray.draw_text(text, int(x + model.padding_x), int(y + model.padding_y), model.font_size, _color(pyray, color))


def process_text_input(model: TextInput) -> bool:
    try:
        import pyray
    except Exception:
        return False
    if not _window_ready(pyray):
        return False
    changed = False
    while True:
        codepoint = pyray.get_char_pressed()
        if codepoint <= 0:
            break
        changed = model.insert_text(chr(codepoint)) or changed
    if pyray.is_key_pressed(pyray.KeyboardKey.KEY_BACKSPACE):
        changed = model.backspace() or changed
    if pyray.is_key_pressed(pyray.KeyboardKey.KEY_DELETE):
        changed = model.delete_forward() or changed
    if pyray.is_key_pressed(pyray.KeyboardKey.KEY_LEFT):
        model.move_cursor(-1, selecting=_shift_down(pyray))
    if pyray.is_key_pressed(pyray.KeyboardKey.KEY_RIGHT):
        model.move_cursor(1, selecting=_shift_down(pyray))
    if _ctrl_down(pyray) and pyray.is_key_pressed(pyray.KeyboardKey.KEY_A):
        model.select_all()
    if _ctrl_down(pyray) and pyray.is_key_pressed(pyray.KeyboardKey.KEY_C):
        _set_clipboard_text(pyray, model.copy_selection())
    if _ctrl_down(pyray) and pyray.is_key_pressed(pyray.KeyboardKey.KEY_X):
        value = model.cut_selection()
        if value:
            _set_clipboard_text(pyray, value)
            changed = True
    if _ctrl_down(pyray) and pyray.is_key_pressed(pyray.KeyboardKey.KEY_V):
        changed = model.paste_text(_get_clipboard_text(pyray)) or changed
    if _ctrl_down(pyray) and pyray.is_key_pressed(pyray.KeyboardKey.KEY_Z):
        changed = model.undo() or changed
    if _ctrl_down(pyray) and pyray.is_key_pressed(pyray.KeyboardKey.KEY_Y):
        changed = model.redo() or changed
    return changed


def _ctrl_down(pyray) -> bool:
    key = pyray.KeyboardKey
    return bool(pyray.is_key_down(key.KEY_LEFT_CONTROL) or pyray.is_key_down(key.KEY_RIGHT_CONTROL))


def _shift_down(pyray) -> bool:
    key = pyray.KeyboardKey
    return bool(pyray.is_key_down(key.KEY_LEFT_SHIFT) or pyray.is_key_down(key.KEY_RIGHT_SHIFT))


def _get_clipboard_text(pyray) -> str:
    try:
        return str(pyray.get_clipboard_text())
    except Exception:
        return ""


def _set_clipboard_text(pyray, value: str) -> None:
    try:
        pyray.set_clipboard_text(value)
    except Exception:
        return


def _draw_rect(pyray, x: float, y: float, w: float, h: float, color: tuple[int, int, int, int]) -> None:
    pyray.draw_rectangle_rec(pyray.Rectangle(x, y, w, h), _color(pyray, color))


def _color(pyray, color: tuple[int, int, int, int]):
    return pyray.Color(color[0], color[1], color[2], color[3])


def _window_ready(pyray) -> bool:
    return not hasattr(pyray, "is_window_ready") or bool(pyray.is_window_ready())
