"""
engine/components/audiosource.py - Fuente de audio 2D serializable.
"""

from __future__ import annotations

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
