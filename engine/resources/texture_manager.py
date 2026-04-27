"""
engine/resources/texture_manager.py - Gestor centralizado de texturas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pyray as rl


@dataclass
class _TextureCacheEntry:
    texture: rl.Texture
    path: str
    refcount: int
    approx_memory: int


class TextureManager:
    """Evita cargar la misma textura multiples veces."""

    def __init__(self) -> None:
        self._cache: Dict[str, _TextureCacheEntry] = {}
        self._failed_count: int = 0

    def load(self, path: str, cache_key: Optional[str] = None) -> rl.Texture:
        """Carga una textura sin tomar ownership por refcount."""

        key = str(cache_key or path)
        if key in self._cache:
            return self._cache[key].texture

        return self._load_uncounted(path, key)

    def acquire(self, path: str, cache_key: Optional[str] = None) -> rl.Texture:
        """Carga o reutiliza una textura e incrementa su refcount."""

        key = str(cache_key or path)
        if key in self._cache:
            entry = self._cache[key]
            entry.refcount += 1
            return entry.texture

        texture = self._load_uncounted(path, key)
        if self._is_valid_texture(texture):
            self._cache[key].refcount = 1
        return texture

    def release(self, cache_key: str) -> None:
        """Libera una referencia tomada con acquire."""

        entry = self._cache.get(cache_key)
        if entry is None:
            return

        entry.refcount = max(0, entry.refcount - 1)
        if entry.refcount == 0:
            rl.unload_texture(entry.texture)
            del self._cache[cache_key]

    def _load_uncounted(self, path: str, key: str) -> rl.Texture:
        texture = rl.load_texture(path)
        if not self._is_valid_texture(texture):
            self._failed_count += 1
            print(f"[WARNING] No se pudo cargar textura: {path}")
            return texture

        self._cache[key] = _TextureCacheEntry(
            texture=texture,
            path=path,
            refcount=0,
            approx_memory=self._estimate_memory(texture),
        )
        return texture

    def _is_valid_texture(self, texture: rl.Texture) -> bool:
        return int(getattr(texture, "id", 0)) != 0

    def _estimate_memory(self, texture: rl.Texture) -> int:
        width = max(0, int(getattr(texture, "width", 0)))
        height = max(0, int(getattr(texture, "height", 0)))
        return width * height * 4

    def unload(self, cache_key: str) -> None:
        if cache_key in self._cache:
            rl.unload_texture(self._cache[cache_key].texture)
            del self._cache[cache_key]

    def unload_all(self) -> None:
        for entry in self._cache.values():
            rl.unload_texture(entry.texture)
        self._cache.clear()

    def is_loaded(self, cache_key: str) -> bool:
        return cache_key in self._cache

    def get_loaded_count(self) -> int:
        return len(self._cache)

    def get_failed_count(self) -> int:
        return self._failed_count

    def get_approx_memory(self) -> int:
        return sum(entry.approx_memory for entry in self._cache.values())

    def get_refcount(self, cache_key: str) -> int:
        entry = self._cache.get(cache_key)
        return 0 if entry is None else entry.refcount

    def get_metrics(self) -> dict[str, int]:
        return {
            "loaded_count": self.get_loaded_count(),
            "failed_count": self.get_failed_count(),
            "approx_memory": self.get_approx_memory(),
        }
