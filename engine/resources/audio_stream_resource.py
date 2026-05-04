"""engine/resources/audio_stream_resource.py — Audio stream resource adaptado de Godot AudioStream.

AudioStreamResource es un recurso serializable para datos de audio.
MVP: WAV, loop playback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AudioStreamResource:
    """Recurso de audio serializable (adaptado de Godot AudioStream).

    MVP: solo WAV, loop playback.
    """

    resource_id: str = ""
    resource_name: str = "New AudioStream"
    audio_type: str = "wav"  # wav, mp3, ogg
    data_path: str = ""  # Ruta al archivo de audio
    loop: bool = False
    volume_db: float = 0.0  # Volumen en decibelios
    pitch_scale: float = 1.0
    stream: bool = False  # Streaming vs cargar todo en memoria

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "audio_type": self.audio_type,
            "data_path": self.data_path,
            "loop": self.loop,
            "volume_db": self.volume_db,
            "pitch_scale": self.pitch_scale,
            "stream": self.stream,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AudioStreamResource":
        if not isinstance(data, dict):
            return cls()
        return cls(
            resource_id=str(data.get("resource_id", "")),
            resource_name=str(data.get("resource_name", "New AudioStream")),
            audio_type=str(data.get("audio_type", "wav")),
            data_path=str(data.get("data_path", "")),
            loop=bool(data.get("loop", False)),
            volume_db=float(data.get("volume_db", 0.0)),
            pitch_scale=float(data.get("pitch_scale", 1.0)),
            stream=bool(data.get("stream", False)),
        )
