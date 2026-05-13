"""Pure widget result and visual state helpers for editor UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


@dataclass
class WidgetResult:
    """Immediate widget outcome.

    Flags describe pointer interaction for current frame. ``changed`` marks a
    value transition. ``value`` is intentionally ``Any`` because each widget
    narrows it by contract, e.g. text widgets return ``str`` and toggles return
    ``bool``.
    """

    hovered: bool = False
    pressed: bool = False
    clicked: bool = False
    right_clicked: bool = False
    changed: bool = False
    value: Any = None

    def consumed(self) -> bool:
        return self.pressed or self.clicked or self.right_clicked or self.changed

    def consume(self) -> bool:
        return self.consumed()


class WidgetVisualState(Enum):
    """Resolved visual state for drawing editor controls.

    Use with ``resolve_visual_state`` priority: disabled, pressed, active,
    selected, focused, hovered, then normal.
    """

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
    """Frame-local immediate widget state.

    This is transient editor UI state, not serializable authoring/runtime data.
    Widgets compute and consume it during one immediate-mode frame.
    """

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
