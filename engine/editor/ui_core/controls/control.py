"""Pure retained-mode Control base and basic controls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from engine.editor.ui_core.controls.events import (
    Anchor,
    ControlEvent,
    ControlEventKind,
    Margin,
    Size,
)

if TYPE_CHECKING:
    from engine.editor.ui_core.controls.focus import FocusManager


@dataclass
class Control:
    name: str = ""
    parent: Control | None = None
    children: list[Control] = field(default_factory=list)
    visible: bool = True
    disabled: bool = False
    expand_h: bool = False
    expand_v: bool = False
    anchor: Anchor = field(default_factory=Anchor)
    margin: Margin = field(default_factory=Margin)
    custom_min_size: Size | None = None
    mouse_default_cursor_shape: int = 0
    tab_index: int = -1

    _rect: tuple[float, float, float, float] = field(default=(0.0, 0.0, 0.0, 0.0), repr=False)
    _focused: bool = field(default=False, repr=False)
    _last_event: ControlEvent | None = field(default=None, repr=False)
    _theme_type_variation: str = ""
    _dirty: bool = field(default=True, repr=False)

    on_click: Callable[[Control, ControlEvent], None] | None = field(default=None, repr=False)
    on_focus: Callable[[Control, ControlEvent], None] | None = field(default=None, repr=False)
    on_mouse_enter: Callable[[Control, ControlEvent], None] | None = field(default=None, repr=False)
    on_mouse_exit: Callable[[Control, ControlEvent], None] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        for child in self.children:
            child.parent = self

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return self._rect

    @property
    def x(self) -> float:
        return self._rect[0]

    @property
    def y(self) -> float:
        return self._rect[1]

    @property
    def width(self) -> float:
        return self._rect[2]

    @property
    def height(self) -> float:
        return self._rect[3]

    @property
    def global_rect(self) -> tuple[float, float, float, float]:
        x, y, w, h = self._rect
        node = self.parent
        while node is not None:
            x += node._rect[0]
            y += node._rect[1]
            node = node.parent
        return (x, y, w, h)

    @property
    def focused(self) -> bool:
        return self._focused

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self) -> None:
        self._dirty = True

    def mark_clean(self) -> None:
        self._dirty = False

    def measure(self, available: Size) -> Size:
        margin = self.margin
        if self.custom_min_size is not None:
            return Size(
                self.custom_min_size.width + margin.horizontal,
                self.custom_min_size.height + margin.vertical,
            )
        return Size(margin.horizontal, margin.vertical)

    def arrange(self, rect: tuple[float, float, float, float]) -> None:
        self._rect = rect
        self._dirty = False

    def add_child(self, child: Control) -> None:
        child.parent = self
        self.children.append(child)
        self._dirty = True

    def remove_child(self, child: Control) -> None:
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            self._dirty = True

    def find_child(self, name: str) -> Control | None:
        for child in self.children:
            if child.name == name:
                return child
        for child in self.children:
            result = child.find_child(name)
            if result is not None:
                return result
        return None

    def contains_point(self, gx: float, gy: float) -> bool:
        rx, ry, rw, rh = self.global_rect
        return rx <= gx <= rx + rw and ry <= gy <= ry + rh

    def to_local(self, gx: float, gy: float) -> tuple[float, float]:
        rx, ry, _, _ = self.global_rect
        return (gx - rx, gy - ry)

    def dispatch(self, event: ControlEvent, focus: FocusManager | None = None) -> bool:
        if not self.visible or self.disabled:
            return False

        if event.kind == ControlEventKind.MOUSE_DOWN and focus is not None:
            if self.tab_index >= 0 and self is not focus.current:
                focus.grab(self)

        if event.kind == ControlEventKind.CLICK and self.on_click is not None:
            self.on_click(self, event)
            return True

        if event.kind == ControlEventKind.FOCUS_GAIN:
            self._focused = True
            if self.on_focus is not None:
                self.on_focus(self, event)
            return True

        if event.kind == ControlEventKind.FOCUS_LOST:
            self._focused = False
            return True

        if event.kind == ControlEventKind.MOUSE_ENTER and self.on_mouse_enter is not None:
            self.on_mouse_enter(self, event)
            return True

        if event.kind == ControlEventKind.MOUSE_EXIT and self.on_mouse_exit is not None:
            self.on_mouse_exit(self, event)
            return True

        return False


@dataclass
class Label(Control):
    text: str = ""
    clip_text: bool = False
    font_size: int = 12

    def measure(self, available: Size) -> Size:
        char_w = self.font_size * 0.55
        text_w = len(self.text) * char_w
        text_h = self.font_size * 1.2
        margin = self.margin
        if self.custom_min_size is not None:
            return Size(
                max(text_w, self.custom_min_size.width) + margin.horizontal,
                max(text_h, self.custom_min_size.height) + margin.vertical,
            )
        return Size(text_w + margin.horizontal, text_h + margin.vertical)

    def set_text(self, text: str) -> None:
        self.text = text
        self._dirty = True


@dataclass
class Button(Control):
    text: str = ""
    font_size: int = 12

    def measure(self, available: Size) -> Size:
        char_w = self.font_size * 0.55
        text_w = len(self.text) * char_w + 16.0
        text_h = max(self.font_size * 1.2 + 8.0, 24.0)
        margin = self.margin
        if self.custom_min_size is not None:
            return Size(
                max(text_w, self.custom_min_size.width) + margin.horizontal,
                max(text_h, self.custom_min_size.height) + margin.vertical,
            )
        return Size(text_w + margin.horizontal, text_h + margin.vertical)

    def set_text(self, text: str) -> None:
        self.text = text
        self._dirty = True

    def arrange(self, rect: tuple[float, float, float, float]) -> None:
        self._rect = rect
        self._dirty = False



@dataclass
class Panel(Control):
    scroll_x: float = 0.0
    scroll_y: float = 0.0
    clip_contents: bool = True

    def measure(self, available: Size) -> Size:
        margin = self.margin
        max_w = margin.horizontal
        max_h = margin.vertical
        for child in self.children:
            if not child.visible:
                continue
            child_size = child.measure(available)
            max_w = max(max_w, child_size.width)
            max_h = max(max_h, child_size.height)
        if self.custom_min_size is not None:
            max_w = max(max_w, self.custom_min_size.width)
            max_h = max(max_h, self.custom_min_size.height)
        return Size(max_w + margin.horizontal, max_h + margin.vertical)

    def arrange(self, rect: tuple[float, float, float, float]) -> None:
        self._rect = rect
        rx, ry, rw, rh = rect
        margin = self.margin
        child_x = rx + margin.left
        child_y = ry + margin.top
        child_w = max(0.0, rw - margin.horizontal)
        child_h = max(0.0, rh - margin.vertical)
        for child in self.children:
            if not child.visible:
                continue
            child.arrange((child_x, child_y, child_w, child_h))
        self._dirty = False


@dataclass
class TextureRect(Control):
    expand_mode: str = "keep"
    stretch_mode: str = "scale"
    texture_path: str = ""
    modulate: tuple[int, int, int, int] = (255, 255, 255, 255)

    def measure(self, available: Size) -> Size:
        margin = self.margin
        if self.custom_min_size is not None:
            return Size(
                max(32.0, self.custom_min_size.width) + margin.horizontal,
                max(32.0, self.custom_min_size.height) + margin.vertical,
            )
        return Size(32.0 + margin.horizontal, 32.0 + margin.vertical)
