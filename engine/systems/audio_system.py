"""
engine/systems/audio_system.py - Sistema de audio 2D basico y seguro para headless.
"""

from __future__ import annotations

import time
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
        self.set_content_resolver(self._asset_service.get_asset_resolver() if self._asset_service is not None else None)

    def set_content_resolver(self, resolver: Any) -> None:
        self._asset_resolver = resolver

    def resolve_asset_path(self, audio_source: AudioSource) -> str:
        if self._asset_resolver is None:
            return audio_source.asset_path
        entry = self._asset_resolver.resolve_entry(audio_source.get_asset_reference())
        if entry is not None:
            audio_source.sync_asset_reference(entry.get("reference", {}))
            return entry["absolute_path"]
        return self._asset_resolver.resolve_path(audio_source.get_asset_reference() or audio_source.asset_path)

    def _get_asset_duration(self, audio_source: AudioSource) -> float:
        """Return audio asset duration in seconds.

        Currently a stub: returns 0.0 because runtime audio does not require
        actual audio playback. The playback_duration is intentionally left as
        a user-settable/runtime-computed value that can be populated via
        play() when the real audio backend is integrated.
        """
        return 0.0

    def update(self, world: World, game_time: float | None = None) -> None:
        """Update all AudioSource components in the world.

        Args:
            world: The game world to update.
            game_time: Optional game time in seconds. When provided, this value
                is used for playback_position computation instead of time.time().
                This ensures deterministic behavior during stepping and testing.
        """
        wall_time = time.time()
        effective_time = game_time if game_time is not None else wall_time
        for entity in world.get_entities_with(AudioSource):
            audio_source = entity.get_component(AudioSource)
            if audio_source is None or not audio_source.enabled:
                continue
            if audio_source.play_on_awake and not audio_source.is_playing:
                audio_source._playback_start_time = effective_time
                audio_source.is_playing = True
            audio_source.set_effective_time(effective_time)
            if audio_source.is_playing and not audio_source.is_paused:
                if audio_source.playback_duration > 0:
                    current_pos = audio_source.playback_position
                    if current_pos >= audio_source.playback_duration and not audio_source.loop:
                        audio_source.is_playing = False
                        audio_source._playback_position = 0.0
                        audio_source._playback_start_time = 0.0

    def play(self, world: World, entity_name: str, game_time: float | None = None) -> bool:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        audio_source = entity.get_component(AudioSource)
        if audio_source is None or not audio_source.enabled:
            return False
        if not audio_source.asset_path and not audio_source.get_asset_reference().get("guid"):
            return False
        self.resolve_asset_path(audio_source)
        effective_time = game_time if game_time is not None else time.time()
        audio_source._playback_start_time = effective_time
        audio_source._playback_position = 0.0
        audio_source._is_paused = False
        audio_source.is_playing = True
        audio_source.set_effective_time(game_time)
        if audio_source.playback_duration <= 0:
            audio_source.playback_duration = self._get_asset_duration(audio_source)
        return True

    def pause(self, world: World, entity_name: str) -> bool:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        audio_source = entity.get_component(AudioSource)
        if audio_source is None or not audio_source.enabled:
            return False
        if not audio_source.is_playing or audio_source.is_paused:
            return False
        audio_source._playback_position = audio_source.playback_position
        audio_source._playback_start_time = 0.0
        audio_source._is_paused = True
        return True

    def resume(self, world: World, entity_name: str, game_time: float | None = None) -> bool:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        audio_source = entity.get_component(AudioSource)
        if audio_source is None or not audio_source.enabled:
            return False
        if not audio_source.is_paused:
            return False
        effective_time = game_time if game_time is not None else time.time()
        audio_source._playback_start_time = effective_time
        audio_source._is_paused = False
        audio_source.set_effective_time(game_time)
        return True

    def stop(self, world: World, entity_name: str) -> bool:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        audio_source = entity.get_component(AudioSource)
        if audio_source is None:
            return False
        audio_source.is_playing = False
        audio_source._playback_position = 0.0
        audio_source._playback_start_time = 0.0
        audio_source._is_paused = False
        return True
