"""Font loading with TTF support and fallback system."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_FONT_CACHE: dict[tuple[str, int], Any] = {}
_PROJECT_ROOT: Path | None = None


def _rl():
    import pyray as rl
    return rl


def _resolve_project_root() -> Path:
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / ".motor").is_dir():
            _PROJECT_ROOT = current
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    fallback = Path.cwd()
    _PROJECT_ROOT = fallback
    return fallback


def _fonts_dir() -> Path:
    return _resolve_project_root() / "assets" / "fonts"


def _font_path(name: str) -> Path | None:
    fonts = _fonts_dir()
    ttf = fonts / f"{name}.ttf"
    if ttf.is_file():
        return ttf
    bare = fonts / name
    if bare.is_file():
        return bare
    return None


def _try_fallbacks() -> Path | None:
    fonts = _fonts_dir()
    for candidate in ("DejaVuSansMono.ttf", "CascadiaMono.ttf"):
        path = fonts / candidate
        if path.is_file():
            return path
    return None


def load_font(name: str, size: int) -> Any:
    key = (name, size)
    cached = _FONT_CACHE.get(key)
    if cached is not None:
        return cached

    rl = _rl()
    path = _font_path(name)

    if path is not None:
        font = rl.load_font_ex(str(path), size, None, 0)
        _FONT_CACHE[key] = font
        return font

    fallback = _try_fallbacks()
    if fallback is not None:
        font = rl.load_font_ex(str(fallback), size, None, 0)
        _FONT_CACHE[key] = font
        return font

    default = rl.get_font_default()
    if default is not None:
        return default

    raise FileNotFoundError(f"Font '{name}' not found and no fallback available")


def get_default_font() -> Any:
    return _rl().get_font_default()


_MONO_CANDIDATES = ("JetBrainsMono", "CascadiaMono", "DejaVuSansMono", "Consolas", "Courier New")


def load_mono_font(size: int) -> Any:
    """Load a monospaced font, falling back through known candidates."""
    key = ("__mono__", size)
    cached = _FONT_CACHE.get(key)
    if cached is not None:
        return cached

    rl = _rl()
    for candidate in _MONO_CANDIDATES:
        path = _font_path(candidate)
        if path is not None:
            font = rl.load_font_ex(str(path), size, None, 0)
            _FONT_CACHE[key] = font
            return font

    return load_font("default", size)


def get_mono_font(size: int = 12) -> Any:
    """Get or load the monospaced font at the given size."""
    return load_mono_font(size)


def unload_font(font: Any) -> None:
    if font is not None:
        _rl().unload_font(font)


def unload_all_fonts() -> None:
    rl = _rl()
    for font in _FONT_CACHE.values():
        rl.unload_font(font)
    _FONT_CACHE.clear()
