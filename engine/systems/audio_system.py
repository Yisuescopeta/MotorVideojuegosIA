"""Adaptador ECS para la foundation interna de audio runtime."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Any

from engine.assets.asset_service import AssetService
from engine.audio import AudioPlaybackRequest, AudioRuntime, AudioRuntimeEvent, NullAudioBackend
from engine.components.audio_listener_2d import AudioListener2D
from engine.components.audiosource import AudioSource
from engine.components.transform import Transform
from engine.ecs.world import World


class AudioSystem:
    """Adaptador fino entre ECS y el runtime interno de audio."""

    def __init__(self, backend=None) -> None:
        self._asset_service: AssetService | None = None
        self._asset_resolver: Any = None
        self._runtime = AudioRuntime(backend=backend if backend is not None else NullAudioBackend())
        self._event_sink: Callable[[AudioRuntimeEvent], None] | None = None
        self._active_listener_transform: Transform | None = None

    def set_project_service(self, project_service: Any) -> None:
        self._asset_service = AssetService(project_service) if project_service is not None else None
        self._asset_resolver = self._asset_service.get_asset_resolver() if self._asset_service is not None else None

    def set_event_sink(self, sink: Callable[[AudioRuntimeEvent], None] | None) -> None:
        self._event_sink = sink

    def resolve_asset_path(self, audio_source: AudioSource) -> str:
        if self._asset_resolver is None:
            return audio_source.asset_path
        entry = self._asset_resolver.resolve_entry(audio_source.get_asset_reference())
        if entry is not None:
            audio_source.sync_asset_reference(entry.get("reference", {}))
            return entry["absolute_path"]
        return self._asset_resolver.resolve_path(audio_source.get_asset_reference() or audio_source.asset_path)

    def _get_asset_duration(self, audio_source) -> float:
        """Intenta leer duración de archivo WAV. Retorna 0.0 si falla."""
        path = audio_source.asset_path or ""
        resolved = getattr(audio_source, 'resolved_asset_path', '') or path
        if resolved.lower().endswith('.wav'):
            try:
                import wave
                with wave.open(resolved, 'rb') as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    if rate > 0:
                        return frames / rate
            except Exception:
                pass
        return 0.0

    def _get_active_listener(self, world: World) -> tuple[Transform | None, AudioListener2D | None]:
        """Find the active AudioListener2D and its Transform in the world.

        Only one listener with is_active=True and enabled=True is used.
        Returns (transform, listener) or (None, None) if no active listener found.
        """
        for entity in world.get_entities_with(AudioListener2D):
            listener = entity.get_component(AudioListener2D)
            if listener is not None and listener.enabled and listener.is_active:
                transform = entity.get_component(Transform)
                return transform, listener
        return None, None

    @staticmethod
    def _spatial_attenuation(
        distance: float,
        max_distance: float,
        mode: str,
    ) -> float:
        """Compute attenuation factor for spatial audio at given distance."""
        if mode == "linear":
            return max(0.0, 1.0 - distance / max(max_distance, 1.0))
        elif mode == "exponential":
            return math.exp(-distance * 0.005)
        else:  # 'inverse' (default)
            return 1.0 / (1.0 + distance * 0.01)

    @staticmethod
    def _spatial_pan(
        source_x: float,
        source_y: float,
        listener_x: float,
        listener_y: float,
        pan_strength: float,
    ) -> float:
        """Compute stereo pan from -1 to 1 based on source angle relative to listener."""
        angle = math.atan2(source_y - listener_y, source_x - listener_x)
        return math.sin(angle) * pan_strength

    @staticmethod
    def _compute_spatial_volume(
        base_volume: float,
        spatial_blend: float,
        distance: float,
        max_distance: float,
        attenuation_mode: str,
    ) -> float:
        """Compute effective volume with spatial attenuation blended in."""
        if spatial_blend <= 0.0:
            return base_volume
        attenuation = AudioSystem._spatial_attenuation(distance, max_distance, attenuation_mode)
        return base_volume * (1.0 + (attenuation - 1.0) * spatial_blend)

    def _apply_spatial_audio(self, world: World) -> None:
        """Apply spatial volume and pan to all active voices based on listener position.

        Called each frame to update voice volume/pan for AudioSources with spatial_blend > 0.
        """
        listener_transform, listener = self._get_active_listener(world)
        self._active_listener_transform = listener_transform

        if listener_transform is None or listener is None:
            return

        listener_x = float(listener_transform.x)
        listener_y = float(listener_transform.y)

        for entity in world.get_entities_with(AudioSource):
            audio_source = entity.get_component(AudioSource)
            if audio_source is None or not audio_source.enabled:
                continue
            if audio_source.spatial_blend <= 0.0:
                continue

            voice = self._runtime.get_voice(entity.name)
            if voice is None:
                continue

            transform = entity.get_component(Transform)
            if transform is None:
                continue

            source_x = float(transform.x)
            source_y = float(transform.y)
            dx = source_x - listener_x
            dy = source_y - listener_y
            distance = math.sqrt(dx * dx + dy * dy)

            effective_volume = self._compute_spatial_volume(
                float(audio_source.volume),
                float(audio_source.spatial_blend),
                distance,
                float(listener.max_distance),
                str(listener.attenuation_mode),
            )

            pan = self._spatial_pan(
                source_x, source_y,
                listener_x, listener_y,
                float(listener.pan_strength),
            )

            voice.volume = effective_volume
            voice.position = (source_x, source_y)

    def update(self, world: World, game_time: float | None = None) -> None:
        """Update all AudioSource components in the world.

        Args:
            world: The game world to update.
            game_time: Optional game time in seconds. When provided, this value
                is used for playback_position computation instead of time.time().
                This ensures deterministic behavior during stepping and testing.
        """
        wall_time = time.time()
        effective_time = float(game_time) if game_time is not None else wall_time
        listener_transform, listener = self._get_active_listener(world)
        self._active_listener_transform = listener_transform
        for entity in world.get_entities_with(AudioSource):
            audio_source = entity.get_component(AudioSource)
            if audio_source is None or not audio_source.enabled:
                continue
            audio_source.set_effective_time(effective_time)
            if audio_source.is_playing:
                self._restore_runtime_voice_from_component(entity.name, audio_source, entity.get_component(Transform))
            if audio_source.play_on_awake and not audio_source.is_playing and self._runtime.get_voice(entity.name) is None:
                request = self._build_playback_request(
                    entity.name, audio_source, entity.get_component(Transform),
                    listener_transform=listener_transform, listener=listener,
                )
                self._runtime.play(request, game_time=effective_time)
        self._apply_spatial_audio(world)
        self._runtime.update(game_time=effective_time)
        self._sync_active_components(world, effective_time=effective_time)
        self._flush_runtime_events(world, effective_time=effective_time)

    def play(self, world: World, entity_name: str, game_time: float | None = None) -> bool:
        entity, audio_source = self._get_entity_audio_source(world, entity_name)
        if entity is None or audio_source is None:
            return False
        if not audio_source.asset_path and not audio_source.get_asset_reference().get("guid"):
            return False
        listener_transform, listener = self._get_active_listener(world)
        request = self._build_playback_request(
            entity.name, audio_source, entity.get_component(Transform),
            listener_transform=listener_transform, listener=listener,
        )
        voice = self._runtime.play(request, game_time=game_time)
        self._sync_component_from_voice(audio_source, voice, effective_time=game_time, clear_effective_time=game_time is None)
        self._flush_runtime_events(world, effective_time=game_time)
        return True

    def pause(self, world: World, entity_name: str) -> bool:
        entity, audio_source = self._get_entity_audio_source(world, entity_name)
        if entity is None or audio_source is None:
            return False
        self._restore_runtime_voice_from_component(entity.name, audio_source, entity.get_component(Transform))
        voice = self._runtime.pause(entity_name)
        if voice is None:
            return False
        self._sync_component_from_voice(audio_source, voice)
        self._flush_runtime_events(world)
        return True

    def resume(self, world: World, entity_name: str, game_time: float | None = None) -> bool:
        entity, audio_source = self._get_entity_audio_source(world, entity_name)
        if entity is None or audio_source is None:
            return False
        self._restore_runtime_voice_from_component(entity.name, audio_source, entity.get_component(Transform))
        voice = self._runtime.resume(entity_name, game_time=game_time)
        if voice is None:
            return False
        self._sync_component_from_voice(audio_source, voice, effective_time=game_time, clear_effective_time=game_time is None)
        self._flush_runtime_events(world, effective_time=game_time)
        return True

    def stop(self, world: World, entity_name: str) -> bool:
        _, audio_source = self._get_entity_audio_source(world, entity_name, require_enabled=False)
        if audio_source is None:
            return False
        self._runtime.stop(entity_name)
        self._sync_component_stopped(audio_source)
        self._flush_runtime_events(world)
        return True

    def _build_playback_request(
        self,
        entity_name: str,
        audio_source: AudioSource,
        transform: Transform | None = None,
        *,
        listener_transform: Transform | None = None,
        listener: AudioListener2D | None = None,
    ) -> AudioPlaybackRequest:
        resolved_asset_path = self.resolve_asset_path(audio_source)
        playback_duration = audio_source.playback_duration
        if playback_duration <= 0:
            playback_duration = self._get_asset_duration(audio_source)
        position = (float(transform.x), float(transform.y)) if transform is not None else None
        volume = float(audio_source.volume)
        if (
            listener_transform is not None
            and listener is not None
            and transform is not None
            and audio_source.spatial_blend > 0.0
        ):
            dx = float(transform.x) - float(listener_transform.x)
            dy = float(transform.y) - float(listener_transform.y)
            distance = math.sqrt(dx * dx + dy * dy)
            volume = self._compute_spatial_volume(
                volume,
                float(audio_source.spatial_blend),
                distance,
                float(listener.max_distance),
                str(listener.attenuation_mode),
            )
        return AudioPlaybackRequest(
            entity_name=entity_name,
            asset_path=audio_source.asset_path,
            resolved_asset_path=resolved_asset_path,
            volume=volume,
            pitch=float(audio_source.pitch),
            loop=bool(audio_source.loop),
            spatial_blend=float(audio_source.spatial_blend),
            position=position,
            playback_duration=playback_duration,
        )

    def _get_entity_audio_source(
        self,
        world: World,
        entity_name: str,
        *,
        require_enabled: bool = True,
    ) -> tuple[Any | None, AudioSource | None]:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return None, None
        audio_source = entity.get_component(AudioSource)
        if audio_source is None:
            return entity, None
        if require_enabled and not audio_source.enabled:
            return entity, None
        return entity, audio_source

    def _sync_active_components(self, world: World, *, effective_time: float) -> None:
        for entity in world.get_entities_with(AudioSource):
            audio_source = entity.get_component(AudioSource)
            if audio_source is None or not audio_source.enabled:
                continue
            voice = self._runtime.get_voice(entity.name)
            if voice is None:
                continue
            self._sync_component_from_voice(audio_source, voice, effective_time=effective_time)

    def _sync_component_from_voice(
        self,
        audio_source: AudioSource,
        voice: Any,
        *,
        effective_time: float | None = None,
        clear_effective_time: bool = False,
    ) -> None:
        audio_source.is_playing = voice.is_playing
        audio_source._playback_start_time = voice.playback_start_time
        audio_source._playback_position = voice.playback_position
        audio_source.playback_duration = voice.playback_duration
        audio_source._is_paused = voice.is_paused
        if clear_effective_time:
            audio_source.clear_effective_time()
        elif effective_time is not None:
            audio_source.set_effective_time(effective_time)

    def _sync_component_stopped(self, audio_source: AudioSource) -> None:
        audio_source.is_playing = False
        audio_source._playback_position = 0.0
        audio_source._playback_start_time = 0.0
        audio_source._is_paused = False

    def _restore_runtime_voice_from_component(
        self,
        entity_name: str,
        audio_source: AudioSource,
        transform: Transform | None = None,
    ) -> None:
        request = self._build_playback_request(entity_name, audio_source, transform)
        self._runtime.restore_voice(
            request,
            playback_start_time=audio_source._playback_start_time,
            playback_position=audio_source._playback_position,
            playback_duration=audio_source.playback_duration,
            is_playing=audio_source.is_playing,
            is_paused=audio_source.is_paused,
        )

    def _flush_runtime_events(self, world: World, *, effective_time: float | None = None) -> None:
        for event in self._runtime.drain_events():
            entity = world.get_entity_by_name(event.entity_name)
            if entity is not None:
                audio_source = entity.get_component(AudioSource)
                if audio_source is not None:
                    if event.name in {"audio_stopped", "audio_completed"}:
                        self._sync_component_stopped(audio_source)
                    else:
                        voice = self._runtime.get_voice(event.entity_name)
                        if voice is not None:
                            self._sync_component_from_voice(audio_source, voice, effective_time=effective_time)
            if self._event_sink is not None:
                self._event_sink(event)

    def shutdown(self) -> None:
        """Limpia recursos del backend de audio."""
        if hasattr(self._runtime, '_backend') and hasattr(self._runtime._backend, 'shutdown'):
            try:
                self._runtime._backend.shutdown()
            except Exception:
                pass
