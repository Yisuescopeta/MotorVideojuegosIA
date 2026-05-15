"""Impure pyray shell for pure popups."""
from __future__ import annotations

from engine.editor.ui_core.controls.popup import PopupModel
from engine.editor.ui_core.tokens import (
    EDITOR_ACCENT,
    EDITOR_BORDER,
    EDITOR_PANEL,
    EDITOR_PANEL_HEADER,
    EDITOR_TEXT,
    EDITOR_TEXT_MUTED,
    FONT_SIZE_SM,
    PANEL_PADDING,
)


def render_popup_frame(model: PopupModel) -> None:
    """Draw simple popup frame (border + background)."""
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


def render_popup_dialog(model: PopupModel) -> None:
    """Draw a full dialog popup with title, message, and buttons."""
    try:
        import pyray
    except Exception:
        return
    if not _window_ready(pyray):
        return
    if not model.visible:
        return
    x, y, w, h = model.rect
    rl = pyray

    # Background
    rl.draw_rectangle_rec(rl.Rectangle(x, y, w, h), _color(rl, EDITOR_PANEL))
    rl.draw_rectangle_lines_ex(rl.Rectangle(x, y, w, h), 1.0, _color(rl, EDITOR_BORDER))

    # Title bar
    title_h = 24.0
    rl.draw_rectangle_rec(rl.Rectangle(x, y, w, title_h), _color(rl, EDITOR_PANEL_HEADER))
    title = getattr(model, "title", "") or ""
    if title:
        rl.draw_text(title, int(x + PANEL_PADDING), int(y + 4), FONT_SIZE_SM, _color(rl, EDITOR_TEXT))

    # Message body
    msg = getattr(model, "message", "") or ""
    body_y = y + title_h + 8
    if msg:
        lines = _wrap_text(rl, msg, int(w - PANEL_PADDING * 2), FONT_SIZE_SM)
        line_y = body_y
        for line in lines[:6]:  # max 6 lines
            rl.draw_text(line, int(x + PANEL_PADDING), int(line_y), FONT_SIZE_SM, _color(rl, EDITOR_TEXT_MUTED))
            line_y += 16

    # Buttons
    buttons = getattr(model, "buttons", []) or []
    if buttons:
        btn_w = 70.0
        btn_h = 22.0
        total_btn_w = len(buttons) * btn_w + (len(buttons) - 1) * 8
        btn_start_x = x + (w - total_btn_w) / 2
        btn_y = y + h - btn_h - 10
        for i, btn in enumerate(buttons):
            bx = btn_start_x + i * (btn_w + 8)
            label = btn.get("label", str(btn)) if isinstance(btn, dict) else str(btn)
            is_primary = isinstance(btn, dict) and btn.get("primary", False)
            color = EDITOR_ACCENT if is_primary else EDITOR_PANEL_HEADER
            rl.draw_rectangle_rec(rl.Rectangle(bx, btn_y, btn_w, btn_h), _color(rl, color))
            rl.draw_rectangle_lines_ex(rl.Rectangle(bx, btn_y, btn_w, btn_h), 1.0, _color(rl, EDITOR_BORDER))
            text_w = rl.measure_text(label, FONT_SIZE_SM)
            rl.draw_text(label, int(bx + (btn_w - text_w) / 2), int(btn_y + 4), FONT_SIZE_SM, _color(rl, EDITOR_TEXT))


def process_popup_dialog(model: PopupModel) -> str | None:
    """Process input for dialog popup. Returns button label/action or None."""
    try:
        import pyray
    except Exception:
        return None
    if not _window_ready(pyray):
        return None
    if not model.visible:
        return None
    rl = pyray
    x, y, w, h = model.rect

    if not rl.is_mouse_button_pressed(rl.MouseButton.MOUSE_BUTTON_LEFT):
        return None

    mx, my = rl.get_mouse_position().x, rl.get_mouse_position().y

    buttons = getattr(model, "buttons", []) or []
    if buttons:
        btn_w = 70.0
        btn_h = 22.0
        total_btn_w = len(buttons) * btn_w + (len(buttons) - 1) * 8
        btn_start_x = x + (w - total_btn_w) / 2
        btn_y = y + h - btn_h - 10
        for i, btn in enumerate(buttons):
            bx = btn_start_x + i * (btn_w + 8)
            if bx <= mx <= bx + btn_w and btn_y <= my <= btn_y + btn_h:
                if isinstance(btn, dict):
                    return btn.get("action", btn.get("label", ""))
                return str(btn)

    return None


def _wrap_text(rl, text: str, max_width: int, font_size: int) -> list[str]:
    """Simple word wrap."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if rl.measure_text(test, font_size) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines if lines else [text]


def _color(pyray, color: tuple[int, int, int, int]):
    return pyray.Color(color[0], color[1], color[2], color[3])


def _window_ready(pyray) -> bool:
    return not hasattr(pyray, "is_window_ready") or bool(pyray.is_window_ready())
