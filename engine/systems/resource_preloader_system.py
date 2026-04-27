"""
engine/systems/resource_preloader_system.py - Sistema de precarga de assets.

Precarga texturas y resuelve rutas de audio al entrar en PLAY para evitar
stalls durante el gameplay.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from engine.assets.asset_reference import normalize_asset_reference, reference_has_identity
from engine.assets.asset_service import AssetService
from engine.components.animator import Animator
from engine.components.audiosource import AudioSource
from engine.components.resource_preloader import ResourcePreloader
from engine.components.sprite import Sprite
from engine.components.tilemap import Tilemap
from engine.ecs.world import World
from engine.resources.texture_manager import TextureManager


class ResourcePreloaderSystem:
    """Sistema que precarga assets antes de que comience el gameplay."""

    def __init__(self) -> None:
        self._asset_service: Optional[AssetService] = None
        self._texture_manager: Optional[TextureManager] = None
        self._budgeted_world_id: int | None = None
        self._budgeted_cache_key: tuple[Any, ...] | None = None
        self._budgeted_plan: list[dict[str, str]] = []
        self._budgeted_cursor: int = 0
        self._budgeted_include_textures: bool = True

    def set_project_service(self, project_service: Any) -> None:
        self._asset_service = AssetService(project_service) if project_service is not None else None
        # El TextureManager se provee externamente para reutilizar el mismo cache

    def set_texture_manager(self, texture_manager: TextureManager) -> None:
        self._texture_manager = texture_manager

    def preload(self, world: World) -> Tuple[int, int]:
        """Precarga assets para el world dado.

        Returns:
            (texturas_precargadas, rutas_resueltas)
        """
        if self._asset_service is None:
            return 0, 0

        plan, include_textures = self._build_preload_context(world)
        return self._load_references(plan, include_textures)

    def build_preload_plan(self, world: World) -> list[dict[str, str]]:
        """Construye la lista unica de referencias a precargar sin cargarlas."""
        if self._asset_service is None:
            return []
        plan, _include_textures = self._build_preload_context(world)
        return [dict(ref) for ref in plan]

    def preload_budgeted(self, world: World, max_items: int) -> Tuple[int, int]:
        """Precarga una porcion del plan para evitar stalls largos."""
        if self._asset_service is None or max_items <= 0:
            return 0, 0

        cache_key = self._build_budgeted_cache_key(world)
        if self._budgeted_world_id != id(world) or self._budgeted_cache_key != cache_key:
            plan, include_textures = self._build_preload_context(world)
            self._budgeted_world_id = id(world)
            self._budgeted_cache_key = cache_key
            self._budgeted_plan = plan
            self._budgeted_cursor = 0
            self._budgeted_include_textures = include_textures

        start = self._budgeted_cursor
        end = min(len(self._budgeted_plan), start + int(max_items))
        chunk = self._budgeted_plan[start:end]
        self._budgeted_cursor = end
        return self._load_references(chunk, self._budgeted_include_textures)

    def _build_preload_context(self, world: World) -> tuple[list[dict[str, str]], bool]:
        preloader_configs = self._gather_configs(world)
        include_textures = any(cfg.include_textures for cfg in preloader_configs) if preloader_configs else True
        include_audio = any(cfg.include_audio for cfg in preloader_configs) if preloader_configs else True

        plan: list[dict[str, str]] = []
        seen: set[str] = set()

        # Assets manuales desde los preloaders
        for cfg in preloader_configs:
            for ref in cfg.assets:
                self._add_reference(plan, seen, ref)

        if not preloader_configs or any(cfg.auto_scan for cfg in preloader_configs):
            for ref in self._scan_world(world, include_textures, include_audio):
                self._add_reference(plan, seen, ref)

        return plan, include_textures

    def _load_references(
        self,
        references: list[dict[str, str]],
        include_textures: bool,
    ) -> Tuple[int, int]:
        texture_count = 0
        resolved_count = 0
        resolver = self._asset_service.get_asset_resolver() if self._asset_service is not None else None

        for ref in references:
            entry = resolver.resolve_entry(ref) if resolver is not None else None
            if entry is not None:
                resolved_count += 1
                if include_textures and self._texture_manager is not None:
                    self._texture_manager.load(
                        entry["absolute_path"],
                        cache_key=entry.get("guid") or entry.get("path"),
                    )
                    texture_count += 1
            else:
                # Fallback por path directo si no hay catalogo
                path = ref.get("path", "")
                if path and include_textures and self._texture_manager is not None:
                    self._texture_manager.load(path, cache_key=path)
                    texture_count += 1

        return texture_count, resolved_count

    def _build_budgeted_cache_key(self, world: World) -> tuple[Any, ...]:
        configs = self._gather_configs(world)
        config_signature = tuple(
            (
                cfg.enabled,
                cfg.auto_scan,
                cfg.include_textures,
                cfg.include_audio,
                tuple(self._reference_key(normalize_asset_reference(ref)) for ref in cfg.assets),
            )
            for cfg in configs
        )
        return (world.version, config_signature)

    def _gather_configs(self, world: World) -> list[ResourcePreloader]:
        configs: list[ResourcePreloader] = []
        for entity in world.get_entities_with(ResourcePreloader):
            preloader = entity.get_component(ResourcePreloader)
            if preloader is not None and preloader.enabled:
                configs.append(preloader)
        return configs

    def _scan_world(
        self,
        world: World,
        include_textures: bool,
        include_audio: bool,
    ) -> list[dict[str, str]]:
        refs: list[dict[str, str]] = []
        seen: set[str] = set()

        if include_textures:
            for entity in world.get_entities_with(Sprite):
                sprite = entity.get_component(Sprite)
                if sprite is not None and sprite.enabled:
                    self._add_reference(refs, seen, sprite.get_texture_reference())

            for entity in world.get_entities_with(Animator):
                animator = entity.get_component(Animator)
                if animator is not None and animator.enabled:
                    self._add_reference(refs, seen, animator.get_sprite_sheet_reference())

            for entity in world.get_entities_with(Tilemap):
                tilemap = entity.get_component(Tilemap)
                if tilemap is not None and tilemap.enabled:
                    self._scan_tilemap(tilemap, refs, seen)

        if include_audio:
            for entity in world.get_entities_with(AudioSource):
                audio = entity.get_component(AudioSource)
                if audio is not None and audio.enabled:
                    self._add_reference(refs, seen, audio.get_asset_reference())

        return refs

    def _scan_tilemap(
        self,
        tilemap: Tilemap,
        refs: list[dict[str, str]],
        seen: set[str],
    ) -> None:
        summary_dependencies_found = False

        tileset_ref = tilemap.get_tileset_reference()
        if self._add_reference(refs, seen, tileset_ref):
            summary_dependencies_found = self._add_reference_dependencies(refs, seen, tileset_ref) or summary_dependencies_found

        for layer in tilemap.layers:
            layer_ref = normalize_asset_reference(layer.get("tilemap_source"))
            if self._add_reference(refs, seen, layer_ref):
                summary_dependencies_found = self._add_reference_dependencies(refs, seen, layer_ref) or summary_dependencies_found

        if summary_dependencies_found:
            return

        # Fallback legacy: tiles individuales pueden referenciar texturas.
        for layer in tilemap.layers:
            for tile in layer.get("tiles", {}).values():
                if not isinstance(tile, dict):
                    continue
                self._add_reference(refs, seen, tile.get("source"))
                self._add_reference(refs, seen, tile.get("texture"))

    def _add_reference_dependencies(
        self,
        refs: list[dict[str, str]],
        seen: set[str],
        ref: Any,
    ) -> bool:
        if self._asset_service is None:
            return False
        resolver = self._asset_service.get_asset_resolver()
        entry = resolver.resolve_entry(normalize_asset_reference(ref)) if resolver is not None else None
        dependencies = entry.get("dependencies", []) if isinstance(entry, dict) else []
        found = False
        for dependency in dependencies:
            if self._add_reference(refs, seen, dependency):
                found = True
        return found

    def _add_reference(
        self,
        refs: list[dict[str, str]],
        seen: set[str],
        ref: Any,
    ) -> bool:
        normalized = normalize_asset_reference(ref)
        if not reference_has_identity(normalized):
            return False
        key = self._reference_key(normalized)
        if key in seen:
            return False
        seen.add(key)
        refs.append(normalized)
        return True

    def _reference_key(self, ref: dict[str, str]) -> str:
        path = str(ref.get("path", "")).strip()
        guid = str(ref.get("guid", "")).strip()
        return path or guid
