"""
engine/components/audiosource.py - Fuente de audio 2D serializable.
"""

from __future__ import annotations

import time
from typing import Any

from engine.assets.asset_reference import build_asset_reference, clone_asset_reference, normalize_asset_reference
from engine.ecs.component import Component


class AudioSource(Component):
    """Representa una fuente de audio editable por API y por UI."""

    def __init__(
        self,
        asset_path: str = "",
        asset: Any = None,
        volume: float = 1.0,
        pitch: float = 1.0,
        loop: bool = False,
        play_on_awake: bool = False,
        spatial_blend: float = 0.0,
    ) -> None:
        self.enabled: bool = True
        self.asset = normalize_asset_reference(asset if asset is not None else asset_path)
        self.asset_path: str = self.asset.get("path", "")
        self.volume: float = volume
        self.pitch: float = pitch
        self.loop: bool = loop
        self.play_on_awake: bool = play_on_awake
        self.spatial_blend: float = spatial_blend
        self.is_playing: bool = False
        self._playback_start_time: float = 0.0
        self._playback_position: float = 0.0
        self._playback_duration: float = 0.0
        self._is_paused: bool = False

    @property
    def playback_position(self) -> float:
        if self._is_paused:
            return self._playback_position
        if self.is_playing and not self._is_paused and self._playback_start_time > 0:
            return self._playback_position + (time.time() - self._playback_start_time)
        return self._playback_position

    @playback_position.setter
    def playback_position(self, value: float) -> None:
        self._playback_position = max(0.0, float(value))
        if self._is_paused:
            self._playback_start_time = 0.0

    @property
    def playback_duration(self) -> float:
        return self._playback_duration

    @playback_duration.setter
    def playback_duration(self, value: float) -> None:
        self._playback_duration = max(0.0, float(value))

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def get_asset_reference(self) -> dict[str, str]:
        return clone_asset_reference(self.asset)

    def sync_asset_reference(self, reference: Any) -> None:
        self.asset = normalize_asset_reference(reference)
        self.asset_path = self.asset.get("path", "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "asset": self.get_asset_reference(),
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
        asset_ref = normalize_asset_reference(data.get("asset"))
        asset_path = data.get("asset_path", "")
        if asset_path and asset_ref.get("path") != asset_path:
            asset_ref = build_asset_reference(asset_path, asset_ref.get("guid", ""))
        component = cls(
            asset_path=asset_path,
            asset=asset_ref,
            volume=data.get("volume", 1.0),
            pitch=data.get("pitch", 1.0),
            loop=data.get("loop", False),
            play_on_awake=data.get("play_on_awake", False),
            spatial_blend=data.get("spatial_blend", 0.0),
        )
        component.enabled = data.get("enabled", True)
        component.is_playing = data.get("is_playing", False)
        return component
