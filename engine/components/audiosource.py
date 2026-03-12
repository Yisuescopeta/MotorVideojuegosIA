"""
engine/components/audiosource.py - Fuente de audio 2D simple y serializable
"""

from typing import Any

from engine.ecs.component import Component


class AudioSource(Component):
    """Representa una fuente de audio editable por API y por UI."""

    def __init__(
        self,
        asset_path: str = "",
        volume: float = 1.0,
        pitch: float = 1.0,
        loop: bool = False,
        play_on_awake: bool = False,
        spatial_blend: float = 0.0,
    ) -> None:
        self.enabled: bool = True
        self.asset_path: str = asset_path
        self.volume: float = volume
        self.pitch: float = pitch
        self.loop: bool = loop
        self.play_on_awake: bool = play_on_awake
        self.spatial_blend: float = spatial_blend
        self.is_playing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "asset_path": self.asset_path,
            "volume": self.volume,
            "pitch": self.pitch,
            "loop": self.loop,
            "play_on_awake": self.play_on_awake,
            "spatial_blend": self.spatial_blend,
            "is_playing": self.is_playing,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AudioSource":
        component = cls(
            asset_path=data.get("asset_path", ""),
            volume=data.get("volume", 1.0),
            pitch=data.get("pitch", 1.0),
            loop=data.get("loop", False),
            play_on_awake=data.get("play_on_awake", False),
            spatial_blend=data.get("spatial_blend", 0.0),
        )
        component.enabled = data.get("enabled", True)
        component.is_playing = data.get("is_playing", False)
        return component
