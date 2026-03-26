"""
engine/components/sprite.py - Componente de renderizado de sprites.
"""

from __future__ import annotations

from typing import Any, Tuple

from engine.assets.asset_reference import build_asset_reference, clone_asset_reference, normalize_asset_reference
from engine.ecs.component import Component


class Sprite(Component):
    """Componente para renderizar una textura 2D."""

    def __init__(
        self,
        texture_path: str = "",
        texture: Any = None,
        width: int = 0,
        height: int = 0,
        origin_x: float = 0.5,
        origin_y: float = 0.5,
        flip_x: bool = False,
        flip_y: bool = False,
        tint: Tuple[int, int, int, int] = (255, 255, 255, 255),
    ) -> None:
        self.enabled: bool = True
        self.texture = normalize_asset_reference(texture if texture is not None else texture_path)
        self.texture_path: str = self.texture.get("path", "")
        self.width: int = width
        self.height: int = height
        self.origin_x: float = origin_x
        self.origin_y: float = origin_y
        self.flip_x: bool = flip_x
        self.flip_y: bool = flip_y
        self.tint: Tuple[int, int, int, int] = tint

    def get_texture_reference(self) -> dict[str, str]:
        return clone_asset_reference(self.texture)

    def sync_texture_reference(self, reference: Any) -> None:
        self.texture = normalize_asset_reference(reference)
        self.texture_path = self.texture.get("path", "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "texture": self.get_texture_reference(),
            "texture_path": self.texture_path,
            "width": self.width,
            "height": self.height,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
            "tint": list(self.tint),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Sprite":
        tint = data.get("tint", [255, 255, 255, 255])
        texture_ref = normalize_asset_reference(data.get("texture"))
        texture_path = data.get("texture_path", "")
        if texture_path and texture_ref.get("path") != texture_path:
            texture_ref = build_asset_reference(texture_path, texture_ref.get("guid", ""))
        component = cls(
            texture_path=texture_path,
            texture=texture_ref,
            width=data.get("width", 0),
            height=data.get("height", 0),
            origin_x=data.get("origin_x", 0.5),
            origin_y=data.get("origin_y", 0.5),
            flip_x=data.get("flip_x", False),
            flip_y=data.get("flip_y", False),
            tint=tuple(tint),  # type: ignore[arg-type]
        )
        component.enabled = data.get("enabled", True)
        return component
