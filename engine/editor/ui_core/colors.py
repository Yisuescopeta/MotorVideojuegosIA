"""Pure color helpers for editor UI."""

from __future__ import annotations

from engine.editor.ui_core.tokens import RGBA


def _channel(value: int) -> int:
    return max(0, min(255, int(value)))


def rgba(r: int, g: int, b: int, a: int = 255) -> RGBA:
    """Return a clamped RGBA tuple."""
    return (_channel(r), _channel(g), _channel(b), _channel(a))


def with_alpha(color: RGBA, alpha: int) -> RGBA:
    return rgba(color[0], color[1], color[2], alpha)


def lerp_color(a: RGBA, b: RGBA, t: float) -> RGBA:
    t = max(0.0, min(1.0, float(t)))
    return rgba(
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
        round(a[3] + (b[3] - a[3]) * t),
    )


def is_dark_theme(background: RGBA) -> bool:
    r, g, b, _ = background
    luminance = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
    return luminance < 128


def rgba_to_int(color: RGBA) -> int:
    r, g, b, a = color
    return (_channel(r) << 24) | (_channel(g) << 16) | (_channel(b) << 8) | _channel(a)


def int_to_rgba(value: int) -> RGBA:
    value = int(value) & 0xFFFFFFFF
    return ((value >> 24) & 255, (value >> 16) & 255, (value >> 8) & 255, value & 255)


def rgba_to_hex(color: RGBA, include_alpha: bool = True) -> str:
    r, g, b, a = rgba(*color)
    if include_alpha:
        return f"#{r:02X}{g:02X}{b:02X}{a:02X}"
    return f"#{r:02X}{g:02X}{b:02X}"
