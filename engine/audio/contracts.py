from __future__ import annotations

from dataclasses import dataclass


AudioPosition = tuple[float, float]


@dataclass(slots=True)
class AudioPlaybackRequest:
    """Solicitud interna de reproduccion construida desde ECS."""

    entity_name: str
    asset_path: str = ""
    resolved_asset_path: str = ""
    bus_id: str = "master"
    volume: float = 1.0
    pitch: float = 1.0
    loop: bool = False
    spatial_blend: float = 0.0
    position: AudioPosition | None = None
    playback_duration: float = 0.0


@dataclass(slots=True)
class AudioVoiceState:
    """Estado runtime no serializable de una voz activa de audio."""

    entity_name: str
    asset_path: str = ""
    resolved_asset_path: str = ""
    bus_id: str = "master"
    volume: float = 1.0
    pitch: float = 1.0
    loop: bool = False
    spatial_blend: float = 0.0
    position: AudioPosition | None = None
    is_playing: bool = False
    is_paused: bool = False
    playback_start_time: float = 0.0
    playback_position: float = 0.0
    playback_duration: float = 0.0

    def current_position(self, current_time: float) -> float:
        if self.is_paused or not self.is_playing or self.playback_start_time <= 0:
            return self.playback_position
        return self.playback_position + (current_time - self.playback_start_time)


@dataclass(slots=True)
class AudioRuntimeEvent:
    """Evento interno del runtime de audio."""

    name: str
    entity_name: str
    bus_id: str = "master"
    asset_path: str = ""
    resolved_asset_path: str = ""
