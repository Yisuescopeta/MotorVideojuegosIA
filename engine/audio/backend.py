from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from engine.audio.contracts import AudioPlaybackRequest, AudioVoiceState


class AudioBackend(Protocol):
    """Contrato interno para futuros backends de audio."""

    def start(self, request: AudioPlaybackRequest, voice: AudioVoiceState) -> None:
        """Inicializa una voz para reproduccion."""

    def pause(self, voice: AudioVoiceState) -> None:
        """Pausa una voz activa."""

    def resume(self, voice: AudioVoiceState) -> None:
        """Reanuda una voz pausada."""

    def stop(self, voice: AudioVoiceState) -> None:
        """Detiene una voz activa."""

    def update(self, voices: Iterable[AudioVoiceState], *, game_time: float | None = None) -> None:
        """Actualiza el backend para las voces activas."""


class NullAudioBackend:
    """Backend nulo y headless-safe para el runtime inicial de audio."""

    def start(self, request: AudioPlaybackRequest, voice: AudioVoiceState) -> None:
        return None

    def pause(self, voice: AudioVoiceState) -> None:
        return None

    def resume(self, voice: AudioVoiceState) -> None:
        return None

    def stop(self, voice: AudioVoiceState) -> None:
        return None

    def update(self, voices: Iterable[AudioVoiceState], *, game_time: float | None = None) -> None:
        return None
