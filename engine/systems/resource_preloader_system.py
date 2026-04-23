"""
engine/systems/resource_preloader_system.py - Sistema de precarga de assets.

Precarga texturas y resuelve rutas de audio al entrar en PLAY para evitar
stalls durante el gameplay.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple

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

        preloader_configs = self._gather_configs(world)
        include_textures = any(cfg.include_textures for cfg in preloader_configs) if preloader_configs else True
        include_audio = any(cfg.include_audio for cfg in preloader_configs) if preloader_configs else True

        references: Set[str] = set()

        # Assets manuales desde los preloaders
        for cfg in preloader_configs:
            for ref in cfg.assets:
                normalized = normalize_asset_reference(ref)
                if reference_has_identity(normalized):
                    references.add(str(normalized))

        if not preloader_configs or any(cfg.auto_scan for cfg in preloader_configs):
            references.update(self._scan_world(world, include_textures, include_audio))

        texture_count = 0
        resolved_count = 0
        resolver = self._asset_service.get_asset_resolver() if self._asset_service is not None else None

        for ref_str in references:
            ref = eval(ref_str) if ref_str.startswith("{") else {"path": ref_str}
            if not isinstance(ref, dict):
                ref = {"path": ref_str}

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
    ) -> Set[str]:
        refs: Set[str] = set()

        if include_textures:
            for entity in world.get_entities_with(Sprite):
                sprite = entity.get_component(Sprite)
                if sprite is not None and sprite.enabled:
                    ref = sprite.get_texture_reference()
                    if reference_has_identity(ref):
                        refs.add(str(ref))

            for entity in world.get_entities_with(Animator):
                animator = entity.get_component(Animator)
                if animator is not None and animator.enabled:
                    ref = animator.get_sprite_sheet_reference()
                    if reference_has_identity(ref):
                        refs.add(str(ref))

            for entity in world.get_entities_with(Tilemap):
                tilemap = entity.get_component(Tilemap)
                if tilemap is not None and tilemap.enabled:
                    tileset_ref = tilemap.get_tileset_reference()
                    if reference_has_identity(tileset_ref):
                        refs.add(str(tileset_ref))
                    # Tiles individuales pueden referenciar texturas
                    for layer in tilemap.layers:
                        for tile_key, tile in layer.get("tiles", {}).items():
                            source = tile.get("source")
                            if source is not None:
                                normalized = normalize_asset_reference(source)
                                if reference_has_identity(normalized):
                                    refs.add(str(normalized))
                            texture = tile.get("texture")
                            if texture is not None:
                                normalized = normalize_asset_reference(texture)
                                if reference_has_identity(normalized):
                                    refs.add(str(normalized))

        if include_audio:
            for entity in world.get_entities_with(AudioSource):
                audio = entity.get_component(AudioSource)
                if audio is not None and audio.enabled:
                    ref = audio.get_asset_reference()
                    if reference_has_identity(ref):
                        refs.add(str(ref))

        return refs
