"""
engine/components/uiimage.py - Imagen UI serializable no interactiva.
"""

from __future__ import annotations

from typing import Any

from engine.assets.asset_reference import clone_asset_reference, normalize_asset_reference, reference_has_identity
from engine.ecs.component import Component


def _color_tuple(value: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    r, g, b, a = value
    return (int(r), int(g), int(b), int(a))


class UIImage(Component):
    """Imagen UI overlay serializable para banners, logos y decoracion."""

    def __init__(
        self,
        enabled: bool = True,
        sprite: Any = None,
        slice_name: str = "",
        tint: tuple[int, int, int, int] = (255, 255, 255, 255),
        preserve_aspect: bool = True,
    ) -> None:
        self.enabled = bool(enabled)
        self.sprite = normalize_asset_reference(sprite)
        self.slice_name = str(slice_name or "")
        self.tint = _color_tuple(tint)
        self.preserve_aspect = bool(preserve_aspect)

    def has_sprite(self) -> bool:
        return reference_has_identity(self.sprite)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "sprite": clone_asset_reference(self.sprite),
            "slice_name": self.slice_name,
            "tint": list(self.tint),
            "preserve_aspect": self.preserve_aspect,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIImage":
        return cls(
            enabled=data.get("enabled", True),
            sprite=data.get("sprite"),
            slice_name=data.get("slice_name", ""),
            tint=tuple(data.get("tint", [255, 255, 255, 255])),  # type: ignore[arg-type]
            preserve_aspect=data.get("preserve_aspect", True),
        )
