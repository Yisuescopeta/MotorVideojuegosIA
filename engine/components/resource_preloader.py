"""
engine/components/resource_preloader.py - Componente para precarga de assets al entrar en escena.
"""

from __future__ import annotations

from typing import Any, List

from engine.assets.asset_reference import normalize_asset_reference
from engine.ecs.component import Component


class ResourcePreloader(Component):
    """Configura la precarga automatica o manual de assets al entrar en PLAY."""

    def __init__(
        self,
        auto_scan: bool = True,
        assets: List[Any] | None = None,
        include_textures: bool = True,
        include_audio: bool = True,
    ) -> None:
        self.enabled: bool = True
        self.auto_scan: bool = auto_scan
        self.assets: List[Any] = assets if assets is not None else []
        self.include_textures: bool = include_textures
        self.include_audio: bool = include_audio

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "auto_scan": self.auto_scan,
            "assets": [normalize_asset_reference(ref) for ref in self.assets],
            "include_textures": self.include_textures,
            "include_audio": self.include_audio,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourcePreloader":
        raw_assets = data.get("assets", [])
        normalized = [normalize_asset_reference(ref) for ref in raw_assets]
        component = cls(
            auto_scan=data.get("auto_scan", True),
            assets=normalized,
            include_textures=data.get("include_textures", True),
            include_audio=data.get("include_audio", True),
        )
        component.enabled = data.get("enabled", True)
        return component
