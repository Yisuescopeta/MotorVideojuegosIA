from __future__ import annotations

import time

from engine.audio.backend import AudioBackend, NullAudioBackend
from engine.audio.contracts import AudioPlaybackRequest, AudioRuntimeEvent, AudioVoiceState


class AudioRuntime:
    """Nucleo interno del runtime de audio sin dependencia de ECS."""

    def __init__(self, backend: AudioBackend | None = None) -> None:
        self._backend: AudioBackend = backend or NullAudioBackend()
        self._voices: dict[str, AudioVoiceState] = {}
        self._events: list[AudioRuntimeEvent] = []

    def get_voice(self, entity_name: str) -> AudioVoiceState | None:
        return self._voices.get(entity_name)

    def play(self, request: AudioPlaybackRequest, *, game_time: float | None = None) -> AudioVoiceState:
        current_time = self._resolve_time(game_time)
        self._emit("audio_play_requested", request)
        voice = AudioVoiceState(
            entity_name=request.entity_name,
            asset_path=request.asset_path,
            resolved_asset_path=request.resolved_asset_path,
            bus_id=request.bus_id,
            volume=request.volume,
            pitch=request.pitch,
            loop=request.loop,
            spatial_blend=request.spatial_blend,
            position=request.position,
            is_playing=True,
            is_paused=False,
            playback_start_time=current_time,
            playback_position=0.0,
            playback_duration=max(0.0, float(request.playback_duration)),
        )
        self._voices[request.entity_name] = voice
        self._backend.start(request, voice)
        self._emit("audio_started", voice)
        return voice

    def restore_voice(
        self,
        request: AudioPlaybackRequest,
        *,
        playback_start_time: float,
        playback_position: float,
        playback_duration: float,
        is_playing: bool,
        is_paused: bool,
    ) -> AudioVoiceState:
        voice = AudioVoiceState(
            entity_name=request.entity_name,
            asset_path=request.asset_path,
            resolved_asset_path=request.resolved_asset_path,
            bus_id=request.bus_id,
            volume=request.volume,
            pitch=request.pitch,
            loop=request.loop,
            spatial_blend=request.spatial_blend,
            position=request.position,
            is_playing=bool(is_playing),
            is_paused=bool(is_paused),
            playback_start_time=float(playback_start_time),
            playback_position=max(0.0, float(playback_position)),
            playback_duration=max(0.0, float(playback_duration)),
        )
        self._voices[request.entity_name] = voice
        return voice

    def pause(self, entity_name: str, *, game_time: float | None = None) -> AudioVoiceState | None:
        voice = self._voices.get(entity_name)
        if voice is None or not voice.is_playing or voice.is_paused:
            return None
        current_time = self._resolve_time(game_time)
        voice.playback_position = voice.current_position(current_time)
        voice.playback_start_time = 0.0
        voice.is_paused = True
        self._backend.pause(voice)
        self._emit("audio_paused", voice)
        return voice

    def resume(self, entity_name: str, *, game_time: float | None = None) -> AudioVoiceState | None:
        voice = self._voices.get(entity_name)
        if voice is None or not voice.is_paused:
            return None
        current_time = self._resolve_time(game_time)
        voice.playback_start_time = current_time
        voice.is_paused = False
        self._backend.resume(voice)
        self._emit("audio_resumed", voice)
        return voice

    def stop(self, entity_name: str, *, event_name: str = "audio_stopped") -> AudioVoiceState | None:
        voice = self._voices.pop(entity_name, None)
        if voice is None:
            return None
        voice.is_playing = False
        voice.is_paused = False
        voice.playback_position = 0.0
        voice.playback_start_time = 0.0
        self._backend.stop(voice)
        self._emit(event_name, voice)
        return voice

    def update(self, *, game_time: float | None = None) -> None:
        current_time = self._resolve_time(game_time)
        self._backend.update(self._voices.values(), game_time=current_time)
        completed: list[str] = []
        for entity_name, voice in self._voices.items():
            if not voice.is_playing or voice.is_paused:
                continue
            if voice.playback_duration <= 0 or voice.loop:
                continue
            if voice.current_position(current_time) >= voice.playback_duration:
                completed.append(entity_name)
        for entity_name in completed:
            self.stop(entity_name, event_name="audio_completed")

    def drain_events(self) -> list[AudioRuntimeEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def _resolve_time(self, game_time: float | None) -> float:
        return float(game_time) if game_time is not None else time.time()

    def _emit(self, event_name: str, source: AudioPlaybackRequest | AudioVoiceState) -> None:
        self._events.append(
            AudioRuntimeEvent(
                name=event_name,
                entity_name=source.entity_name,
                bus_id=source.bus_id,
                asset_path=source.asset_path,
                resolved_asset_path=source.resolved_asset_path,
            )
        )
