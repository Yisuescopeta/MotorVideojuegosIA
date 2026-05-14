"""Pure Container controls with automatic child layout."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.editor.ui_core.controls.control import Control
from engine.editor.ui_core.controls.events import Size


class LayoutDirection:
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


@dataclass
class Container(Control):
    direction: str = LayoutDirection.VERTICAL
    spacing: float = 0.0
    alignment: str = "start"

    def measure(self, available: Size) -> Size:
        margin = self.margin
        total_w = 0.0
        total_h = 0.0
        visible_children = [c for c in self.children if c.visible]
        spacing_total = max(0.0, self.spacing * (len(visible_children) - 1))

        if self.direction == LayoutDirection.HORIZONTAL:
            max_child_h = 0.0
            for child in visible_children:
                child_size = child.measure(available)
                total_w += child_size.width
                max_child_h = max(max_child_h, child_size.height)
            total_w += spacing_total
            total_h = max_child_h
        else:
            max_child_w = 0.0
            for child in visible_children:
                child_size = child.measure(available)
                max_child_w = max(max_child_w, child_size.width)
                total_h += child_size.height
            total_w = max_child_w
            total_h += spacing_total

        if self.custom_min_size is not None:
            total_w = max(total_w, self.custom_min_size.width)
            total_h = max(total_h, self.custom_min_size.height)

        return Size(total_w + margin.horizontal, total_h + margin.vertical)

    def arrange(self, rect: tuple[float, float, float, float]) -> None:
        self._rect = rect
        rx, ry, rw, rh = rect
        margin = self.margin
        content_x = rx + margin.left
        content_y = ry + margin.top
        content_w = max(0.0, rw - margin.horizontal)
        content_h = max(0.0, rh - margin.vertical)

        visible_children = [c for c in self.children if c.visible]
        if not visible_children:
            return

        if self.direction == LayoutDirection.HORIZONTAL:
            self._arrange_horizontal(visible_children, content_x, content_y, content_w, content_h)
        else:
            self._arrange_vertical(visible_children, content_x, content_y, content_w, content_h)

    def _arrange_horizontal(
        self,
        children: list[Control],
        cx: float,
        cy: float,
        cw: float,
        ch: float,
    ) -> None:
        spacing = self.spacing
        expandables = [c for c in children if c.expand_h]
        total_spacing = spacing * (len(children) - 1)

        per_expand = 0.0
        if expandables:
            non_expand_total = 0.0
            for c in children:
                if not c.expand_h:
                    child_size = c.measure(Size(cw, ch))
                    non_expand_total += child_size.width
            leftover = max(0.0, cw - non_expand_total - total_spacing)
            per_expand = leftover / max(1, len(expandables))

        cursor = cx
        for child in children:
            child_size = child.measure(Size(cw, ch))
            child_w = per_expand if (child.expand_h and expandables) else child_size.width
            child_h = ch if child.expand_v else min(child_size.height, ch)
            child_y = cy
            if self.alignment == "center":
                child_y = cy + (ch - child_h) / 2
            elif self.alignment == "end":
                child_y = cy + ch - child_h
            child.arrange((cursor, child_y, child_w, child_h))
            cursor += child_w + spacing

    def _arrange_vertical(
        self,
        children: list[Control],
        cx: float,
        cy: float,
        cw: float,
        ch: float,
    ) -> None:
        spacing = self.spacing
        expandables = [c for c in children if c.expand_v]
        total_spacing = spacing * (len(children) - 1)

        per_expand = 0.0
        if expandables:
            non_expand_total = 0.0
            for c in children:
                if not c.expand_v:
                    child_size = c.measure(Size(cw, ch))
                    non_expand_total += child_size.height
            leftover = max(0.0, ch - non_expand_total - total_spacing)
            per_expand = leftover / max(1, len(expandables))

        cursor = cy
        for child in children:
            child_size = child.measure(Size(cw, ch))
            child_w = cw if child.expand_h else min(child_size.width, cw)
            child_h = per_expand if (child.expand_v and expandables) else child_size.height
            child_x = cx
            if self.alignment == "center":
                child_x = cx + (cw - child_w) / 2
            elif self.alignment == "end":
                child_x = cx + cw - child_w
            child.arrange((child_x, cursor, child_w, child_h))
            cursor += child_h + spacing


@dataclass
class VBoxContainer(Container):
    direction: str = field(default=LayoutDirection.VERTICAL, init=False)


@dataclass
class HBoxContainer(Container):
    direction: str = field(default=LayoutDirection.HORIZONTAL, init=False)


@dataclass
class ScrollContainer(Control):
    scroll_x: float = 0.0
    scroll_y: float = 0.0
    follow_focus: bool = False
    horizontal_scroll_mode: str = "auto"
    vertical_scroll_mode: str = "auto"

    def measure(self, available: Size) -> Size:
        margin = self.margin
        if self.custom_min_size is not None:
            return Size(
                self.custom_min_size.width + margin.horizontal,
                self.custom_min_size.height + margin.vertical,
            )
        return Size(100.0 + margin.horizontal, 100.0 + margin.vertical)

    def arrange(self, rect: tuple[float, float, float, float]) -> None:
        self._rect = rect
        rx, ry, rw, rh = rect
        margin = self.margin
        content_x = rx + margin.left - self.scroll_x
        content_y = ry + margin.top - self.scroll_y
        inner_w = max(0.0, rw - margin.horizontal)
        inner_h = max(0.0, rh - margin.vertical)
        for child in self.children:
            if not child.visible:
                continue
            child_size = child.measure(Size(inner_w, inner_h))
            child_w = child_size.width
            child_h = child_size.height
            child.arrange((content_x, content_y, child_w, child_h))
