"""
engine/rendering/viewport_renderer.py - Manages SubViewport render textures using raylib.
"""
from __future__ import annotations

from typing import Any, Optional

import pyray as rl


class ViewportRenderer:
    """Manages SubViewport render textures via raylib RenderTexture2D."""

    def __init__(self) -> None:
        self._viewports: dict[str, Any] = {}
        self._dirty: set[str] = set()

    def get_or_create_texture(self, name: str, width: int, height: int) -> Any:
        safe_w = max(1, int(width))
        safe_h = max(1, int(height))
        current = self._viewports.get(name)
        backend_ready = bool(hasattr(rl, "is_window_ready") and rl.is_window_ready())
        if not backend_ready:
            if current is not None:
                return current
            placeholder = _TexturePlaceholder(name, safe_w, safe_h)
            self._viewports[name] = placeholder
            return placeholder
        if current is not None and not isinstance(current, _TexturePlaceholder):
            if hasattr(current, "texture"):
                tex = current.texture
                if tex.width == safe_w and tex.height == safe_h:
                    return current
            rl.unload_render_texture(current)
        handle = rl.load_render_texture(safe_w, safe_h)
        self._viewports[name] = handle
        return handle

    def begin_render(self, name: str, transparent_bg: bool = True) -> None:
        tex = self._viewports.get(name)
        if tex is None or isinstance(tex, _TexturePlaceholder):
            return
        rl.begin_texture_mode(tex)
        clear_color = rl.BLANK if transparent_bg else rl.BLACK
        rl.clear_background(clear_color)

    def end_render(self, name: str) -> None:
        tex = self._viewports.get(name)
        if tex is None or isinstance(tex, _TexturePlaceholder):
            return
        rl.end_texture_mode()

    def get_texture(self, name: str) -> Any:
        tex = self._viewports.get(name)
        if tex is None:
            return None
        if isinstance(tex, _TexturePlaceholder):
            return None
        return tex.texture if hasattr(tex, "texture") else None

    def get_render_texture(self, name: str) -> Any:
        tex = self._viewports.get(name)
        if isinstance(tex, _TexturePlaceholder):
            return None
        return tex

    def get_dimensions(self, name: str) -> Optional[tuple[int, int]]:
        tex = self._viewports.get(name)
        if tex is None:
            return None
        if isinstance(tex, _TexturePlaceholder):
            return (tex._width, tex._height)
        if hasattr(tex, "texture") and hasattr(tex.texture, "width"):
            return (tex.texture.width, tex.texture.height)
        return None

    def mark_dirty(self, name: str) -> None:
        self._dirty.add(name)

    def is_dirty(self, name: str) -> bool:
        return name in self._dirty

    def clear_dirty(self, name: str) -> None:
        self._dirty.discard(name)

    def cleanup(self) -> None:
        for name, tex in list(self._viewports.items()):
            if not isinstance(tex, _TexturePlaceholder):
                try:
                    rl.unload_render_texture(tex)
                except Exception:
                    pass
        self._viewports.clear()
        self._dirty.clear()

    def remove(self, name: str) -> None:
        tex = self._viewports.pop(name, None)
        if tex is not None and not isinstance(tex, _TexturePlaceholder):
            rl.unload_render_texture(tex)
        self._dirty.discard(name)


class _TexturePlaceholder:
    """Fallback when no graphics backend available."""

    def __init__(self, name: str, width: int, height: int) -> None:
        self._name = name
        self._width = width
        self._height = height
