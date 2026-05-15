"""Pure dock tree rectangle computation for editor layout."""

from __future__ import annotations

from dataclasses import dataclass

from engine.editor.ui_core.docking import DockArea, DockLayout, DockNode, DockSplit

RectTuple = tuple[float, float, float, float]


@dataclass(frozen=True)
class DockRects:
    areas: dict[str, RectTuple]
    splitters: dict[str, RectTuple]


def _clamp_rect(rect: RectTuple) -> RectTuple:
    x, y, width, height = rect
    return (float(x), float(y), max(0.0, float(width)), max(0.0, float(height)))


def compute_dock_rects(layout: DockLayout, root_rect: RectTuple, splitter_size: float = 4.0) -> DockRects:
    """Compute area rects from a serializable DockLayout tree.

    Horizontal splits divide left/right. Vertical splits divide top/bottom.
    """

    areas: dict[str, RectTuple] = {}
    splitters: dict[str, RectTuple] = {}
    gap = max(0.0, float(splitter_size))

    def visit(node: DockNode, rect: RectTuple) -> None:
        x, y, width, height = _clamp_rect(rect)
        if isinstance(node, DockArea):
            areas[node.id] = (x, y, width, height)
            return

        if not isinstance(node, DockSplit):
            raise TypeError("Unknown dock node")

        if node.direction == "vertical":
            usable = max(0.0, height - gap)
            first_h = usable * node.ratio
            second_h = usable - first_h
            splitters[node.id] = (x, y + first_h, width, gap)
            visit(node.first, (x, y, width, first_h))
            visit(node.second, (x, y + first_h + gap, width, second_h))
            return

        usable = max(0.0, width - gap)
        first_w = usable * node.ratio
        second_w = usable - first_w
        splitters[node.id] = (x + first_w, y, gap, height)
        visit(node.first, (x, y, first_w, height))
        visit(node.second, (x + first_w + gap, y, second_w, height))

    visit(layout.root, root_rect)
    return DockRects(areas=areas, splitters=splitters)


def compute_floating_window_rects(
    layout: DockLayout,
) -> dict[str, RectTuple]:
    """Return rects for all open floating windows.

    Args:
        layout: DockLayout instance

    Returns:
        dict mapping ``window.tab_id`` to ``(x, y, width, height)`` for each
        open floating window.
    """
    result: dict[str, RectTuple] = {}
    for window in layout.floating_windows:
        if getattr(window, "is_open", True):
            result[window.tab_id] = (window.x, window.y, window.width, window.height)
    return result


def compute_auto_hide_collapsed_rect(
    area_rect: RectTuple,
    edge: str,
    strip_thickness: float = 24.0,
) -> RectTuple:
    """Compute the visible collapsed strip rect for an auto-hide area.

    Args:
        area_rect: Full area rect ``(x, y, width, height)``
        edge: ``'left'``, ``'right'``, or ``'bottom'``
        strip_thickness: Width/height of collapsed strip in pixels

    Returns:
        ``(x, y, width, height)`` of the visible strip
    """
    x, y, w, h = area_rect
    if edge == "left":
        return (x, y, strip_thickness, h)
    elif edge == "right":
        return (x + w - strip_thickness, y, strip_thickness, h)
    elif edge == "bottom":
        return (x, y + h - strip_thickness, w, strip_thickness)
    else:
        raise ValueError(f"Unknown edge: {edge}")


__all__ = [
    "DockRects",
    "RectTuple",
    "compute_auto_hide_collapsed_rect",
    "compute_dock_rects",
    "compute_floating_window_rects",
]
