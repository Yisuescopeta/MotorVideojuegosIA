"""Pure retained-mode event types for the control tree."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.editor.ui_core.controls.control import Control


class ControlEventKind(Enum):
    MOUSE_ENTER = auto()
    MOUSE_EXIT = auto()
    MOUSE_DOWN = auto()
    MOUSE_UP = auto()
    CLICK = auto()
    DOUBLE_CLICK = auto()
    DRAG_START = auto()
    DRAG = auto()
    DRAG_END = auto()
    FOCUS_GAIN = auto()
    FOCUS_LOST = auto()
    KEY_DOWN = auto()
    KEY_UP = auto()
    RESIZED = auto()
    SCROLL = auto()


@dataclass
class ControlEvent:
    kind: ControlEventKind
    target: Control | None = None
    local_x: float = 0.0
    local_y: float = 0.0
    global_x: float = 0.0
    global_y: float = 0.0
    button: int = 0
    key: int = 0
    consumed: bool = False


@dataclass
class Size:
    width: float
    height: float

    @property
    def min_axis(self) -> float:
        return min(self.width, self.height)

    def __add__(self, other: Size) -> Size:
        return Size(self.width + other.width, self.height + other.height)

    def __truediv__(self, scalar: float) -> Size:
        return Size(self.width / scalar, self.height / scalar)

    def max(self, other: Size) -> Size:
        return Size(max(self.width, other.width), max(self.height, other.height))


@dataclass
class Anchor:
    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0


@dataclass
class Margin:
    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0

    @property
    def horizontal(self) -> float:
        return self.left + self.right

    @property
    def vertical(self) -> float:
        return self.top + self.bottom
