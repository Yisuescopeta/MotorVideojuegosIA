"""Pure widget result and visual state helpers for editor UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


@dataclass
class WidgetResult:
    """Immediate widget outcome."""

    hovered: bool = False
    pressed: bool = False
    clicked: bool = False
    right_clicked: bool = False
    changed: bool = False
    value: object = None

    def consumed(self) -> bool:
        return self.pressed or self.clicked or self.right_clicked or self.changed

    def consume(self) -> bool:
        return self.consumed()


class WidgetVisualState(Enum):
    """Resolved visual state for drawing editor controls."""

    NORMAL = auto()
    HOVER = auto()
    PRESSED = auto()
    ACTIVE = auto()
    DISABLED = auto()
    FOCUSED = auto()
    SELECTED = auto()


def resolve_visual_state(
    enabled: bool = True,
    hovered: bool = False,
    pressed: bool = False,
    active: bool = False,
    focused: bool = False,
    selected: bool = False,
) -> WidgetVisualState:
    if not enabled:
        return WidgetVisualState.DISABLED
    if pressed:
        return WidgetVisualState.PRESSED
    if active:
        return WidgetVisualState.ACTIVE
    if selected:
        return WidgetVisualState.SELECTED
    if focused:
        return WidgetVisualState.FOCUSED
    if hovered:
        return WidgetVisualState.HOVER
    return WidgetVisualState.NORMAL


@dataclass
class WidgetState:
    """Frame-local immediate widget state."""

    enabled: bool = True
    hovered: bool = False
    pressed: bool = False
    active: bool = False
    focused: bool = False
    selected: bool = False

    @property
    def visual(self) -> WidgetVisualState:
        return resolve_visual_state(
            enabled=self.enabled,
            hovered=self.hovered,
            pressed=self.pressed,
            active=self.active,
            focused=self.focused,
            selected=self.selected,
        )

    def update(
        self,
        *,
        enabled: bool | None = None,
        hovered: bool | None = None,
        pressed: bool | None = None,
        active: bool | None = None,
        focused: bool | None = None,
        selected: bool | None = None,
    ) -> WidgetState:
        return WidgetState(
            enabled=self.enabled if enabled is None else enabled,
            hovered=self.hovered if hovered is None else hovered,
            pressed=self.pressed if pressed is None else pressed,
            active=self.active if active is None else active,
            focused=self.focused if focused is None else focused,
            selected=self.selected if selected is None else selected,
        )
