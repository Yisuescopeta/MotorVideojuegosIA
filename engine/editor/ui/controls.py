"""Impure retained-mode control renderer (pyray-dependent).

Uses pure models from ``engine.editor.ui_core.controls`` and renders them with
pyray drawing primitives. This is the impure shell counterpart.
"""

from __future__ import annotations

from engine.editor.ui_core.controls import (
    Button,
    Container,
    Control,
    ControlEvent,
    ControlEventKind,
    FocusManager,
    Label,
    Panel,
    TextureRect,
)
from engine.editor.ui_core.tokens import (
    EDITOR_ACCENT,
    EDITOR_ACCENT_HOVER,
    EDITOR_BORDER,
    EDITOR_PANEL,
    EDITOR_TEXT,
    EDITOR_TEXT_DISABLED,
    EDITOR_TEXT_MUTED,
)


def _to_ray_color(c: tuple[int, int, int, int]):
    import pyray

    return pyray.Color(c[0], c[1], c[2], c[3])


def render_control(ctrl: Control, focused: Control | None) -> None:
    if not ctrl.visible:
        return

    import pyray

    rx, ry, rw, rh = ctrl.global_rect

    if isinstance(ctrl, Panel):
        pyray.draw_rectangle_rec(
            pyray.Rectangle(rx, ry, rw, rh),
            _to_ray_color(EDITOR_PANEL),
        )

    elif isinstance(ctrl, Button):
        is_focused = ctrl is focused
        is_hovered = _check_hover(ctrl, pyray)
        color = EDITOR_ACCENT_HOVER if is_hovered else EDITOR_ACCENT
        border_color = EDITOR_TEXT if is_focused else EDITOR_BORDER
        pyray.draw_rectangle_rec(
            pyray.Rectangle(rx, ry, rw, rh),
            _to_ray_color(color),
        )
        pyray.draw_rectangle_lines_ex(
            pyray.Rectangle(rx, ry, rw, rh),
            1.0,
            _to_ray_color(border_color),
        )
        if ctrl.text:
            text_offset_y = int(ry + rh / 2 - 6)
            pyray.draw_text(
                ctrl.text,
                int(rx + 8),
                text_offset_y,
                ctrl.font_size,
                _to_ray_color(EDITOR_TEXT),
            )

    elif isinstance(ctrl, Label):
        text_color = EDITOR_TEXT_DISABLED if ctrl.disabled else EDITOR_TEXT_MUTED
        pyray.draw_text(
            ctrl.text,
            int(rx),
            int(ry),
            ctrl.font_size,
            _to_ray_color(text_color),
        )

    elif isinstance(ctrl, TextureRect):
        pyray.draw_rectangle_rec(
            pyray.Rectangle(rx, ry, rw, rh),
            _to_ray_color(EDITOR_BORDER),
        )
        pyray.draw_text(
            "[img]",
            int(rx + 4),
            int(ry + 4),
            10,
            _to_ray_color(EDITOR_TEXT_MUTED),
        )

    elif isinstance(ctrl, Container):
        pyray.draw_rectangle_lines_ex(
            pyray.Rectangle(rx, ry, rw, rh),
            1.0,
            _to_ray_color(EDITOR_BORDER),
        )

    elif isinstance(ctrl, Control):
        if ctrl is focused:
            pyray.draw_rectangle_lines_ex(
                pyray.Rectangle(rx, ry, rw, rh),
                1.0,
                _to_ray_color(EDITOR_ACCENT),
            )

    for child in ctrl.children:
        render_control(child, focused)


def _check_hover(ctrl: Control, pyray) -> bool:
    mouse = pyray.get_mouse_position()
    return ctrl.contains_point(mouse.x, mouse.y)


def process_input(
    root: Control,
    focus: FocusManager,
) -> list[ControlEvent]:
    import pyray

    events: list[ControlEvent] = []
    mouse = pyray.get_mouse_position()
    mx, my = mouse.x, mouse.y

    hovered = focus.pick_at(root, mx, my)
    prev = focus.hovered
    if hovered is not prev:
        if prev is not None:
            prev.dispatch(ControlEvent(ControlEventKind.MOUSE_EXIT, target=prev), focus)
        if hovered is not None:
            hovered.dispatch(ControlEvent(ControlEventKind.MOUSE_ENTER, target=hovered), focus)
        focus.hovered = hovered

    if pyray.is_mouse_button_pressed(pyray.MouseButton.MOUSE_BUTTON_LEFT):
        if hovered is not None:
            hovered.dispatch(
                ControlEvent(ControlEventKind.MOUSE_DOWN, target=hovered, global_x=mx, global_y=my),
                focus,
            )

    if pyray.is_mouse_button_released(pyray.MouseButton.MOUSE_BUTTON_LEFT):
        if hovered is not None:
            hovered.dispatch(
                ControlEvent(ControlEventKind.CLICK, target=hovered, global_x=mx, global_y=my),
                focus,
            )

    if pyray.is_key_pressed(pyray.KeyboardKey.KEY_TAB):
        if pyray.is_key_down(pyray.KeyboardKey.KEY_LEFT_SHIFT) or pyray.is_key_down(pyray.KeyboardKey.KEY_RIGHT_SHIFT):
            focus.focus_prev()
        else:
            focus.focus_next()

    return events


def demo_control_tree() -> Control:
    root = Panel(name="RootPanel", children=[])

    vbox = Container(
        name="MainVBox",
        direction="vertical",
    )

    label = Label(name="TitleLabel", text="Demo: Retained-mode Controls", font_size=16)

    row = Container(
        name="ButtonRow",
        direction="horizontal",
        spacing=8.0,
    )
    btn1 = Button(name="Btn1", text="Click Me", tab_index=1)
    btn2 = Button(name="Btn2", text="Button 2", tab_index=2)
    btn3 = Button(name="Btn3", text="Button 3", tab_index=3)
    btn1.on_click = lambda c, e: print(f"[demo] {c.name} clicked")
    btn2.on_click = lambda c, e: print(f"[demo] {c.name} clicked")
    btn3.on_click = lambda c, e: print(f"[demo] {c.name} clicked")
    row.add_child(btn1)
    row.add_child(btn2)
    row.add_child(btn3)

    footer_label = Label(name="FooterLabel", text="TAB to cycle focus | click buttons to test", font_size=10)

    vbox.add_child(label)
    vbox.add_child(row)
    vbox.add_child(footer_label)
    root.add_child(vbox)

    root.arrange((100.0, 100.0, 400.0, 200.0))
    return root
