"""
engine/resources/texture_manager.py - Gestor centralizado de texturas.
"""

from __future__ import annotations

from typing import Dict, Optional

import pyray as rl


class TextureManager:
    """Evita cargar la misma textura multiples veces."""

    def __init__(self) -> None:
        self._cache: Dict[str, rl.Texture] = {}

    def load(self, path: str, cache_key: Optional[str] = None) -> rl.Texture:
        key = str(cache_key or path)
        if key in self._cache:
            return self._cache[key]

        texture = rl.load_texture(path)
        if texture.id == 0:
            print(f"[WARNING] No se pudo cargar textura: {path}")

        self._cache[key] = texture
        return texture

    def unload(self, cache_key: str) -> None:
        if cache_key in self._cache:
            rl.unload_texture(self._cache[cache_key])
            del self._cache[cache_key]

    def unload_all(self) -> None:
        for texture in self._cache.values():
            rl.unload_texture(texture)
        self._cache.clear()

    def is_loaded(self, cache_key: str) -> bool:
        return cache_key in self._cache

    def get_loaded_count(self) -> int:
        return len(self._cache)
