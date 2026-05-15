"""Pure focus management with tab-order navigation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.editor.ui_core.controls.control import Control


@dataclass
class FocusManager:
    focused: Control | None = field(default=None, repr=False)
    hovered: Control | None = field(default=None, repr=False)
    grabber: Control | None = field(default=None, repr=False)
    _tab_order: list[Control] = field(default_factory=list, repr=False)

    @property
    def current(self) -> Control | None:
        return self.grabber or self.focused

    def grab(self, control: Control) -> None:
        if self.grabber is not None and self.grabber is not self.focused:
            self.focused = self.grabber
        self.grabber = control

    def ungrab(self) -> None:
        self.grabber = None

    def set_focus(self, control: Control) -> None:
        if self.focused is control:
            return
        self.focused = control

    def clear_focus(self) -> None:
        self.ungrab()
        self.focused = None

    def build_tab_order(self, root: Control) -> None:
        self._tab_order.clear()

        def collect(ctrl: Control) -> None:
            if ctrl.visible and not ctrl.disabled and ctrl.tab_index >= 0:
                self._tab_order.append(ctrl)
            for child in ctrl.children:
                collect(child)

        collect(root)
        self._tab_order.sort(key=lambda c: c.tab_index)

    def focus_next(self) -> Control | None:
        if not self._tab_order:
            return None
        current = self.current
        if current is None or current not in self._tab_order:
            self.set_focus(self._tab_order[0])
            return self._tab_order[0]
        idx = self._tab_order.index(current)
        next_idx = (idx + 1) % len(self._tab_order)
        self.set_focus(self._tab_order[next_idx])
        return self._tab_order[next_idx]

    def focus_prev(self) -> Control | None:
        if not self._tab_order:
            return None
        current = self.current
        if current is None or current not in self._tab_order:
            self.set_focus(self._tab_order[-1])
            return self._tab_order[-1]
        idx = self._tab_order.index(current)
        prev_idx = (idx - 1) % len(self._tab_order)
        self.set_focus(self._tab_order[prev_idx])
        return self._tab_order[prev_idx]

    def pick_at(self, root: Control, gx: float, gy: float) -> Control | None:
        def deepest(ctrl: Control) -> Control | None:
            if not ctrl.visible or not ctrl.contains_point(gx, gy):
                return None
            for child in reversed(ctrl.children):
                found = deepest(child)
                if found is not None:
                    return found
            return ctrl

        return deepest(root)
