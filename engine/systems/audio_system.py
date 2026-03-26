"""
engine/systems/audio_system.py - Sistema de audio 2D basico y seguro para headless.
"""

from __future__ import annotations

from typing import Any

from engine.assets.asset_service import AssetService
from engine.components.audiosource import AudioSource
from engine.ecs.world import World


class AudioSystem:
    """Gestion minima de AudioSource sin introducir estado opaco en la UI."""

    def __init__(self) -> None:
        self._asset_service: AssetService | None = None
        self._asset_resolver: Any = None

    def set_project_service(self, project_service: Any) -> None:
        self._asset_service = AssetService(project_service) if project_service is not None else None
        self._asset_resolver = self._asset_service.get_asset_resolver() if self._asset_service is not None else None

    def resolve_asset_path(self, audio_source: AudioSource) -> str:
        if self._asset_resolver is None:
            return audio_source.asset_path
        entry = self._asset_resolver.resolve_entry(audio_source.get_asset_reference())
        if entry is not None:
            audio_source.sync_asset_reference(entry.get("reference", {}))
            return entry["absolute_path"]
        return self._asset_resolver.resolve_path(audio_source.get_asset_reference() or audio_source.asset_path)

    def update(self, world: World) -> None:
        for entity in world.get_entities_with(AudioSource):
            audio_source = entity.get_component(AudioSource)
            if audio_source is None or not audio_source.enabled:
                continue
            if audio_source.play_on_awake and not audio_source.is_playing:
                audio_source.is_playing = True

    def play(self, world: World, entity_name: str) -> bool:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        audio_source = entity.get_component(AudioSource)
        if audio_source is None or not audio_source.enabled:
            return False
        if not audio_source.asset_path and not audio_source.get_asset_reference().get("guid"):
            return False
        self.resolve_asset_path(audio_source)
        audio_source.is_playing = True
        return True

    def stop(self, world: World, entity_name: str) -> bool:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        audio_source = entity.get_component(AudioSource)
        if audio_source is None:
            return False
        audio_source.is_playing = False
        return True
