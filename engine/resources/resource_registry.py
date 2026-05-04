"""engine/resources/resource_registry.py — Registro unificado de recursos cargados.

Cachea recursos por path con refcounting para evitar cargas duplicadas.
Adaptado del ResourceLoader de Godot.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResourceEntry:
    """Entrada en el registry: recurso cargado + refcount."""

    resource: Any
    resource_type: str
    ref_count: int = 1
    path: str = ""


class ResourceRegistry:
    """Registry unificado de recursos cargados (adaptado Godot ResourceLoader).

    Cachea recursos por path para evitar cargas duplicadas.
    Soporta: TileSetResource, AnimationResource, SpriteFramesResource,
    Shader2DResource, ThemeResource, StyleBoxResource.
    """

    def __init__(self) -> None:
        self._entries: dict[str, ResourceEntry] = {}
        self._type_loaders: dict[str, callable] = {}
        self._register_default_loaders()

    def _register_default_loaders(self) -> None:
        """Registra loaders para tipos de recurso conocidos."""
        self._type_loaders["tileset"] = self._load_tileset
        self._type_loaders["animation"] = self._load_animation
        self._type_loaders["sprite_frames"] = self._load_sprite_frames
        self._type_loaders["shader2d"] = self._load_shader
        self._type_loaders["theme"] = self._load_theme

    def load(self, path: str, resource_type: str = "auto") -> Any:
        """Carga un recurso por path. Usa caché si ya está cargado.

        Args:
            path: Ruta al archivo de recurso (.json, .tileset, .anim, etc.)
            resource_type: Tipo de recurso o "auto" para detectar por extensión.

        Returns:
            El recurso cargado, o None si falla.
        """
        if not path or not os.path.isfile(path):
            return None

        # Cache hit
        if path in self._entries:
            self._entries[path].ref_count += 1
            return self._entries[path].resource

        # Detectar tipo
        if resource_type == "auto":
            resource_type = self._detect_type(path)

        loader = self._type_loaders.get(resource_type)
        if loader is None:
            return None

        try:
            resource = loader(path)
            self._entries[path] = ResourceEntry(
                resource=resource,
                resource_type=resource_type,
                path=path,
                ref_count=1,
            )
            return resource
        except Exception:
            return None

    def unload(self, path: str) -> bool:
        """Decrementa refcount y descarga si llega a 0."""
        if path not in self._entries:
            return False
        entry = self._entries[path]
        entry.ref_count -= 1
        if entry.ref_count <= 0:
            del self._entries[path]
        return True

    def is_loaded(self, path: str) -> bool:
        return path in self._entries

    def get_loaded(self, path: str) -> Any:
        entry = self._entries.get(path)
        return entry.resource if entry else None

    def clear(self) -> None:
        self._entries.clear()

    def _detect_type(self, path: str) -> str:
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        mapping = {
            "tileset": "tileset",
            "anim": "animation",
            "sframes": "sprite_frames",
            "shader2d": "shader2d",
            "theme": "theme",
            "json": "auto",  # Intentar inferir del contenido
        }
        return mapping.get(ext, "auto")

    # ------------------------------------------------------------------ #
    # Loaders específicos
    # ------------------------------------------------------------------ #

    def _load_tileset(self, path: str) -> Any:
        from engine.resources.tileset_resource import TileSetResource

        with open(path, "r") as f:
            return TileSetResource.from_dict(json.load(f))

    def _load_animation(self, path: str) -> Any:
        from engine.resources.animation_resource import AnimationResource

        with open(path, "r") as f:
            return AnimationResource.from_dict(json.load(f))

    def _load_sprite_frames(self, path: str) -> Any:
        from engine.resources.sprite_frames_resource import SpriteFramesResource

        with open(path, "r") as f:
            return SpriteFramesResource.from_dict(json.load(f))

    def _load_shader(self, path: str) -> Any:
        from engine.resources.shader2d_resource import Shader2DResource

        with open(path, "r") as f:
            return Shader2DResource.from_dict(json.load(f))

    def _load_theme(self, path: str) -> Any:
        from engine.resources.theme_resource import ThemeResource

        with open(path, "r") as f:
            return ThemeResource.from_dict(json.load(f))
