"""Cache de resolucion de referencias de textura para rutas calientes de render."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pyray as rl
from engine.assets.asset_reference import normalize_asset_path, normalize_asset_reference
from engine.resources.texture_manager import TextureManager


@dataclass(slots=True)
class ResolvedTexture:
    texture: Any
    absolute_path: str
    cache_key: str
    canonical_reference: dict[str, str]


class TextureResolutionCache:
    """Evita resolver catalogo y filesystem para cada sprite en cada frame."""

    def __init__(
        self,
        texture_manager: TextureManager,
        *,
        project_service: Any = None,
        asset_resolver: Any = None,
    ) -> None:
        self._texture_manager = texture_manager
        self._project_service = project_service
        self._asset_resolver = asset_resolver
        self._entries: dict[tuple[str, str, str], ResolvedTexture] = {}

    def clear(self) -> None:
        self._entries.clear()

    def resolve(
        self,
        reference: Any,
        fallback_path: str = "",
        sync_callback: Callable[[dict[str, str]], Any] | None = None,
    ) -> Any:
        normalized = normalize_asset_reference(reference)
        key = (
            str(normalized.get("guid", "") or ""),
            normalize_asset_path(normalized.get("path", "")),
            normalize_asset_path(fallback_path),
        )
        cached = self._entries.get(key)
        if cached is None:
            cached = self._resolve_uncached(normalized, fallback_path)
            self._entries[key] = cached
            canonical_key = (
                str(cached.canonical_reference.get("guid", "") or ""),
                normalize_asset_path(cached.canonical_reference.get("path", "")),
                key[2],
            )
            self._entries.setdefault(canonical_key, cached)
        elif int(getattr(cached.texture, "id", 0)) != 0 and not self._texture_manager.is_loaded(cached.cache_key):
            cached.texture = self._texture_manager.load(cached.absolute_path, cache_key=cached.cache_key)

        if sync_callback is not None and (cached.canonical_reference.get("guid") or cached.canonical_reference.get("path")):
            sync_callback(dict(cached.canonical_reference))
        return cached.texture

    def _resolve_uncached(self, reference: dict[str, str], fallback_path: str) -> ResolvedTexture:
        entry = self._asset_resolver.resolve_entry(reference) if self._asset_resolver is not None else None
        if entry is not None:
            canonical = normalize_asset_reference(
                entry.get("reference")
                or {
                    "guid": entry.get("guid", ""),
                    "path": entry.get("path", ""),
                }
            )
            absolute_path = str(entry.get("absolute_path", "") or "")
            if not absolute_path and self._project_service is not None:
                absolute_path = self._project_service.resolve_path(entry.get("path", "")).as_posix()
            cache_key = str(entry.get("guid") or entry.get("path") or absolute_path)
            texture = self._texture_manager.load(absolute_path, cache_key=cache_key)
            return ResolvedTexture(texture, absolute_path, cache_key, canonical)

        path = normalize_asset_path(fallback_path or reference.get("path", ""))
        absolute_path = self._resolve_fallback_path(path)
        cache_key = absolute_path or path
        texture = self._texture_manager.load(absolute_path, cache_key=cache_key) if absolute_path else rl.Texture()
        return ResolvedTexture(texture, absolute_path, cache_key, reference)

    def _resolve_fallback_path(self, path: str) -> str:
        if not path or self._project_service is None:
            return path
        return self._project_service.resolve_path(path).as_posix()
