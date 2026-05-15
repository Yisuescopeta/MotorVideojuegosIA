"""Impure pyray shell for pure file picker."""
from __future__ import annotations

from engine.editor.ui_core.controls.file_picker import FilePickerModel
from engine.editor.ui_core.tokens import (
    EDITOR_ACCENT,
    EDITOR_BG,
    EDITOR_BORDER,
    EDITOR_PANEL,
    EDITOR_PANEL_ALT,
    EDITOR_PANEL_HEADER,
    EDITOR_TEXT,
    EDITOR_TEXT_MUTED,
    FONT_SIZE_SM,
    PANEL_PADDING,
)

_ENTRY_HEIGHT = 22
_SCROLL_BAR_WIDTH = 8.0
_BTN_WIDTH = 70.0
_BTN_HEIGHT = 24.0
_INPUT_HEIGHT = 28.0
_BREADCRUMB_HEIGHT = 22.0
_TITLE_BAR_HEIGHT = 26.0


def _rl():
    import pyray as rl
    return rl


def _color(c: tuple[int, int, int, int]):
    rl = _rl()
    return rl.Color(c[0], c[1], c[2], c[3])


def _ready() -> bool:
    try:
        rl = _rl()
        return not hasattr(rl, "is_window_ready") or bool(rl.is_window_ready())
    except Exception:
        return False


def render_file_picker(model: FilePickerModel, x: float, y: float, w: float, h: float) -> None:
    if not _ready():
        return
    rl = _rl()
    rl.draw_rectangle_rec(rl.Rectangle(x, y, w, h), _color(EDITOR_BG))
    rl.draw_rectangle_lines_ex(rl.Rectangle(x, y, w, h), 1.0, _color(EDITOR_BORDER))
    cy = y
    title_h = min(_TITLE_BAR_HEIGHT, h * 0.08)
    rl.draw_rectangle_rec(rl.Rectangle(x, cy, w, title_h), _color(EDITOR_PANEL_HEADER))
    rl.draw_text(model.title, int(x + PANEL_PADDING), int(cy + 4), FONT_SIZE_SM, _color(EDITOR_TEXT))
    cy += title_h
    bread_h = _BREADCRUMB_HEIGHT
    rl.draw_rectangle_rec(rl.Rectangle(x, cy, w, bread_h), _color(EDITOR_PANEL))
    rl.draw_text(model.current_path, int(x + PANEL_PADDING), int(cy + 3), FONT_SIZE_SM, _color(EDITOR_TEXT_MUTED))
    cy += bread_h
    input_h = _INPUT_HEIGHT if model.mode == "save" else 0
    btn_h = _BTN_HEIGHT + PANEL_PADDING * 2
    entries_h = max(0, h - (cy - y) - input_h - btn_h)
    rl.draw_rectangle_rec(rl.Rectangle(x, cy, w, entries_h), _color(EDITOR_PANEL_ALT))
    filtered = model.filtered_entries()
    vis = max(1, int(entries_h / _ENTRY_HEIGHT))
    off = max(0.0, min(model._scroll_offset, float(max(0, len(filtered) - vis))))
    rl.begin_scissor_mode(int(x), int(cy), int(w), int(entries_h))
    start = max(0, int(off))
    end = min(len(filtered), start + vis)
    for i, entry in enumerate(filtered[start:end]):
        ry = cy + i * _ENTRY_HEIGHT
        prefix = "[D] " if entry.is_dir else "    "
        col = EDITOR_ACCENT if entry.path == model.selected_path else EDITOR_TEXT
        rl.draw_text(prefix + entry.name, int(x + PANEL_PADDING), int(ry + 4), FONT_SIZE_SM, _color(col))
        if not entry.is_dir and entry.size > 0:
            sz = _fmt(entry.size)
            rl.draw_text(sz, int(x + w - 60), int(ry + 4), FONT_SIZE_SM, _color(EDITOR_TEXT_MUTED))
    rl.end_scissor_mode()
    if len(filtered) > vis:
        _scrollbar(x, cy, w, entries_h, off, len(filtered), vis)
    cy += entries_h
    if model.mode == "save":
        rl.draw_rectangle_rec(rl.Rectangle(x + PANEL_PADDING, cy + 2, w - PANEL_PADDING * 2, _INPUT_HEIGHT - 4), _color(EDITOR_PANEL))
        rl.draw_rectangle_lines_ex(rl.Rectangle(x + PANEL_PADDING, cy + 2, w - PANEL_PADDING * 2, _INPUT_HEIGHT - 4), 1.0, _color(EDITOR_BORDER))
        txt = model.filename_input or "filename..."
        rl.draw_text(txt, int(x + PANEL_PADDING + 4), int(cy + 6), FONT_SIZE_SM, _color(EDITOR_TEXT))
        cy += input_h
    by = cy + PANEL_PADDING
    ok_x = x + w - _BTN_WIDTH - PANEL_PADDING
    cancel_x = ok_x - _BTN_WIDTH - PANEL_PADDING
    rl.draw_rectangle_rec(rl.Rectangle(ok_x, by, _BTN_WIDTH, _BTN_HEIGHT), _color(EDITOR_ACCENT))
    rl.draw_text("OK", int(ok_x + 24), int(by + 4), FONT_SIZE_SM, _color(EDITOR_TEXT))
    rl.draw_rectangle_rec(rl.Rectangle(cancel_x, by, _BTN_WIDTH, _BTN_HEIGHT), _color(EDITOR_PANEL))
    rl.draw_text("Cancel", int(cancel_x + 10), int(by + 4), FONT_SIZE_SM, _color(EDITOR_TEXT))


def process_file_picker(model: FilePickerModel, x: float, y: float, w: float, h: float) -> str | None:
    if not _ready():
        return None
    rl = _rl()
    mx, my = rl.get_mouse_position().x, rl.get_mouse_position().y
    title_h = min(_TITLE_BAR_HEIGHT, h * 0.08)
    bread_h = _BREADCRUMB_HEIGHT
    input_h = _INPUT_HEIGHT if model.mode == "save" else 0
    btn_h = _BTN_HEIGHT + PANEL_PADDING * 2
    entries_y = y + title_h + bread_h
    entries_h = max(0, h - title_h - bread_h - input_h - btn_h)
    if not (x <= mx <= x + w and y <= my <= y + h):
        return None
    click = rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT)
    if click and entries_y <= my <= entries_y + entries_h:
        filtered = model.filtered_entries()
        vis = max(1, int(entries_h / _ENTRY_HEIGHT))
        off = max(0.0, min(model._scroll_offset, float(max(0, len(filtered) - vis))))
        idx = int((my - entries_y) / _ENTRY_HEIGHT) + int(off)
        if 0 <= idx < len(filtered):
            entry = filtered[idx]
            if entry.is_dir:
                model.navigate_to(entry.path)
                model.selected_path = None
            else:
                model.select(entry.path)
        return None
    wh = rl.get_mouse_wheel_move() if hasattr(rl, "get_mouse_wheel_move") else 0.0
    if wh and entries_y <= my <= entries_y + entries_h:
        filtered = model.filtered_entries()
        vis = max(1, int(entries_h / _ENTRY_HEIGHT))
        model._scroll_offset = max(0.0, min(model._scroll_offset - wh, float(max(0, len(filtered) - vis))))
    by = y + h - _BTN_HEIGHT - PANEL_PADDING
    ok_x = x + w - _BTN_WIDTH - PANEL_PADDING
    cancel_x = ok_x - _BTN_WIDTH - PANEL_PADDING
    if click:
        if ok_x <= mx <= ok_x + _BTN_WIDTH and by <= my <= by + _BTN_HEIGHT:
            if model.mode == "save" and model.filename_input:
                return model.filename_input
            if model.selected_path:
                return model.selected_path
        if cancel_x <= mx <= cancel_x + _BTN_WIDTH and by <= my <= by + _BTN_HEIGHT:
            return "__CANCEL__"
    return None


def _scrollbar(x: float, y: float, w: float, h: float, off: float, total: int, vis: int) -> None:
    if total <= vis or vis <= 0 or h <= 0:
        return
    rl = _rl()
    tw = _SCROLL_BAR_WIDTH
    th = max(12.0, h * (vis / total))
    mx = max(1.0, float(total - vis))
    ty = y + (h - th) * (off / mx)
    rl.draw_rectangle_rec(rl.Rectangle(x + w - tw - 2, ty, tw, th), _color(EDITOR_BORDER))


def _fmt(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"
