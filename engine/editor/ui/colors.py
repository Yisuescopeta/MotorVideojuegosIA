from engine.editor.ui_core.colors import (  # noqa: F401
    int_to_rgba,
    is_dark_theme,
    lerp_color,
    rgba,
    rgba_to_hex,
    rgba_to_int,
    with_alpha,
)
from engine.editor.ui_core.tokens import RGBA


def to_ray_color(color: RGBA) -> object:
    """Convert to pyray.Color, importing pyray only at draw time."""
    import pyray as rl

    r, g, b, a = rgba(*color)
    return rl.Color(r, g, b, a)


__all__ = [
    "RGBA",
    "int_to_rgba",
    "is_dark_theme",
    "lerp_color",
    "rgba",
    "rgba_to_hex",
    "rgba_to_int",
    "to_ray_color",
    "with_alpha",
]
