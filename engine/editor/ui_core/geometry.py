"""Pure rectangle helpers for editor UI layout."""

from __future__ import annotations

Rect = tuple[float, float, float, float]


def inset_rect(rect: Rect, inset: float) -> Rect:
    x, y, w, h = rect
    inset = max(0.0, float(inset))
    return (x + inset, y + inset, max(0.0, w - inset * 2), max(0.0, h - inset * 2))


def split_top(rect: Rect, height: float) -> tuple[Rect, Rect]:
    x, y, w, h = rect
    height = max(0.0, min(float(height), h))
    return (x, y, w, height), (x, y + height, w, h - height)


def split_bottom(rect: Rect, height: float) -> tuple[Rect, Rect]:
    x, y, w, h = rect
    height = max(0.0, min(float(height), h))
    return (x, y, w, h - height), (x, y + h - height, w, height)


def split_left(rect: Rect, width: float) -> tuple[Rect, Rect]:
    x, y, w, h = rect
    width = max(0.0, min(float(width), w))
    return (x, y, width, h), (x + width, y, w - width, h)


def split_right(rect: Rect, width: float) -> tuple[Rect, Rect]:
    x, y, w, h = rect
    width = max(0.0, min(float(width), w))
    return (x, y, w - width, h), (x + w - width, y, width, h)


def rect_contains(rect: Rect, px: float, py: float) -> bool:
    x, y, w, h = rect
    return x <= px <= x + w and y <= py <= y + h


def clamp_rect(rect: Rect, bounds: Rect) -> Rect:
    x, y, w, h = rect
    bx, by, bw, bh = bounds
    w = min(max(0.0, w), max(0.0, bw))
    h = min(max(0.0, h), max(0.0, bh))
    x = max(bx, min(x, bx + bw - w))
    y = max(by, min(y, by + bh - h))
    return (x, y, w, h)
