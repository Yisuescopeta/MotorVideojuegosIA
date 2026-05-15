"""Pure rectangle, color and math helpers for UI layers.

Importable by both Editor UI and Runtime UI without pyray or engine internals.
"""

from __future__ import annotations

import math

from engine.ui.shared_constants import RGBA

# --- Types ---

Rect = tuple[float, float, float, float]

# --- Rectangle helpers ---


def inset_rect(rect: Rect, inset: float) -> Rect:
    """Shrink rect by inset pixels on all sides."""
    x, y, w, h = rect
    inset = max(0.0, float(inset))
    return (x + inset, y + inset, max(0.0, w - inset * 2), max(0.0, h - inset * 2))


def split_top(rect: Rect, height: float) -> tuple[Rect, Rect]:
    """Split rect into top strip of given height and remaining bottom."""
    x, y, w, h = rect
    height = max(0.0, min(float(height), h))
    return (x, y, w, height), (x, y + height, w, h - height)


def split_bottom(rect: Rect, height: float) -> tuple[Rect, Rect]:
    """Split rect into main top area and bottom strip of given height."""
    x, y, w, h = rect
    height = max(0.0, min(float(height), h))
    return (x, y, w, h - height), (x, y + h - height, w, height)


def split_left(rect: Rect, width: float) -> tuple[Rect, Rect]:
    """Split rect into left column of given width and remaining right."""
    x, y, w, h = rect
    width = max(0.0, min(float(width), w))
    return (x, y, width, h), (x + width, y, w - width, h)


def split_right(rect: Rect, width: float) -> tuple[Rect, Rect]:
    """Split rect into main left area and right column of given width."""
    x, y, w, h = rect
    width = max(0.0, min(float(width), w))
    return (x, y, w - width, h), (x + w - width, y, width, h)


def rect_contains(rect: Rect, px: float, py: float) -> bool:
    """Check if point (px, py) is inside rect."""
    x, y, w, h = rect
    return x <= px <= x + w and y <= py <= y + h


def clamp_rect(rect: Rect, bounds: Rect) -> Rect:
    """Clamp rect to stay within bounds."""
    x, y, w, h = rect
    bx, by, bw, bh = bounds
    w = min(max(0.0, w), max(0.0, bw))
    h = min(max(0.0, h), max(0.0, bh))
    x = max(bx, min(x, bx + bw - w))
    y = max(by, min(y, by + bh - h))
    return (x, y, w, h)


def rect_union(a: Rect, b: Rect) -> Rect:
    """Bounding rectangle that contains both rects."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left = min(ax, bx)
    top = min(ay, by)
    right = max(ax + aw, bx + bw)
    bottom = max(ay + ah, by + bh)
    return (left, top, right - left, bottom - top)


def rect_intersection(a: Rect, b: Rect) -> Rect | None:
    """Intersection of two rects, or None if disjoint."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    if left >= right or top >= bottom:
        return None
    return (left, top, right - left, bottom - top)


def rect_center(rect: Rect) -> tuple[float, float]:
    """Center point of rect."""
    x, y, w, h = rect
    return (x + w / 2.0, y + h / 2.0)


# --- Color helpers ---


def _channel(value: int) -> int:
    return max(0, min(255, int(value)))


def rgba(r: int, g: int, b: int, a: int = 255) -> RGBA:
    """Return a clamped RGBA tuple."""
    return (_channel(r), _channel(g), _channel(b), _channel(a))


def with_alpha(color: RGBA, alpha: int) -> RGBA:
    """Return color with alpha channel replaced."""
    return rgba(color[0], color[1], color[2], alpha)


def lerp_color(a: RGBA, b: RGBA, t: float) -> RGBA:
    """Linearly interpolate between two RGBA colors."""
    t = max(0.0, min(1.0, float(t)))
    return rgba(
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
        round(a[3] + (b[3] - a[3]) * t),
    )


def is_dark_theme(background: RGBA) -> bool:
    """Check if a background color is dark (luminance < 128)."""
    r, g, b, _ = background
    luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
    return luminance < 128


def rgba_to_int(color: RGBA) -> int:
    """Pack RGBA into a 32-bit integer (R<<24 | G<<16 | B<<8 | A)."""
    r, g, b, a = color
    return (_channel(r) << 24) | (_channel(g) << 16) | (_channel(b) << 8) | _channel(a)


def int_to_rgba(value: int) -> RGBA:
    """Unpack a 32-bit integer into an RGBA tuple."""
    value = int(value) & 0xFFFFFFFF
    return ((value >> 24) & 255, (value >> 16) & 255, (value >> 8) & 255, value & 255)


def rgba_to_hex(color: RGBA, include_alpha: bool = True) -> str:
    """Convert RGBA to hex string like #RRGGBB or #RRGGBBAA."""
    r, g, b, a = rgba(*color)
    if include_alpha:
        return f"#{r:02X}{g:02X}{b:02X}{a:02X}"
    return f"#{r:02X}{g:02X}{b:02X}"


def text_width_estimate(text: str, font_size: float, char_width_ratio: float = 0.55) -> float:
    """Estimate pixel width of text given font size.

    Uses average char width ratio. For monospace fonts ratio ~0.6;
    for proportional fonts ratio ~0.5 is a safe estimate.
    """
    if not text:
        return 0.0
    return float(len(text)) * font_size * max(0.1, char_width_ratio)


def line_height_estimate(font_size: float, line_spacing: float = 1.4) -> float:
    """Estimate line height from font size."""
    return font_size * max(1.0, line_spacing)


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi] range."""
    return max(lo, min(hi, float(value)))


def lerp(a: float, b: float, t: float) -> float:
    """Linearly interpolate between a and b."""
    t = max(0.0, min(1.0, float(t)))
    return a + (b - a) * t


def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Euclidean distance between two points."""
    return math.hypot(x2 - x1, y2 - y1)
