"""Impure pyray shell for pure popups."""

from __future__ import annotations

from engine.editor.ui_core.controls.popup import PopupModel
from engine.editor.ui_core.tokens import EDITOR_BORDER, EDITOR_PANEL


def render_popup_frame(model: PopupModel) -> None:
    try:
        import pyray
    except Exception:
        return
    if not _window_ready(pyray):
        return
    if not model.visible:
        return
    x, y, w, h = model.rect
    rect = pyray.Rectangle(x, y, w, h)
    pyray.draw_rectangle_rec(rect, _color(pyray, EDITOR_PANEL))
    pyray.draw_rectangle_lines_ex(rect, 1.0, _color(pyray, EDITOR_BORDER))


def _color(pyray, color: tuple[int, int, int, int]):
    return pyray.Color(color[0], color[1], color[2], color[3])


def _window_ready(pyray) -> bool:
    return not hasattr(pyray, "is_window_ready") or bool(pyray.is_window_ready())
