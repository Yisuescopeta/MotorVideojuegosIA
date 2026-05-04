"""Foundation interna para runtime de audio."""

from engine.audio.backend import AudioBackend, NullAudioBackend
from engine.audio.contracts import AudioPlaybackRequest, AudioRuntimeEvent, AudioVoiceState
from engine.audio.runtime import AudioRuntime

__all__ = [
    "AudioBackend",
    "AudioPlaybackRequest",
    "AudioRuntime",
    "AudioRuntimeEvent",
    "AudioVoiceState",
    "NullAudioBackend",
]
