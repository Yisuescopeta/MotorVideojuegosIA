"""engine/resources/stylebox_flat.py — StyleBoxFlat con bordes, shadow, corner radius (adaptado Godot StyleBoxFlat).

StyleBoxFlat extiende StyleBoxResource con propiedades avanzadas de diseño:
sombras, esquinas redondeadas individuales, anti-aliasing, margenes expandidos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StyleBoxFlat:
    """StyleBox configurable con fill, borde, corner radius y shadow (adaptado Godot StyleBoxFlat)."""

    resource_id: str = ""
    name: str = "StyleBoxFlat"
    bg_color: tuple[int, int, int, int] = (40, 40, 40, 255)
    border_color: tuple[int, int, int, int] = (80, 80, 80, 255)
    border_width: int = 1
    corner_radius: int = 0
    corner_radius_top_left: int = 0
    corner_radius_top_right: int = 0
    corner_radius_bottom_right: int = 0
    corner_radius_bottom_left: int = 0
    shadow_color: tuple[int, int, int, int] = (0, 0, 0, 100)
    shadow_size: int = 0
    shadow_offset_x: int = 0
    shadow_offset_y: int = 0
    anti_aliasing: bool = True
    expand_margin_left: int = 0
    expand_margin_right: int = 0
    expand_margin_top: int = 0
    expand_margin_bottom: int = 0
    # Optional texture
    texture_path: str = ""
    # Content margins
    content_margin_left: int = 4
    content_margin_right: int = 4
    content_margin_top: int = 4
    content_margin_bottom: int = 4

    def get_corner_radius(self, corner: str) -> int:
        """Returns effective corner radius. Individual overrides take precedence."""
        overrides: dict[str, int] = {
            "top_left": self.corner_radius_top_left,
            "top_right": self.corner_radius_top_right,
            "bottom_right": self.corner_radius_bottom_right,
            "bottom_left": self.corner_radius_bottom_left,
        }
        return overrides.get(corner, 0) if overrides.get(corner, 0) > 0 else self.corner_radius

    @property
    def has_shadow(self) -> bool:
        return self.shadow_size > 0 and self.shadow_color[3] > 0

    @property
    def expand_size(self) -> tuple[int, int, int, int]:
        return (
            self.expand_margin_left,
            self.expand_margin_top,
            self.expand_margin_right,
            self.expand_margin_bottom,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "name": self.name,
            "bg_color": list(self.bg_color),
            "border_color": list(self.border_color),
            "border_width": self.border_width,
            "corner_radius": self.corner_radius,
            "corner_radius_top_left": self.corner_radius_top_left,
            "corner_radius_top_right": self.corner_radius_top_right,
            "corner_radius_bottom_right": self.corner_radius_bottom_right,
            "corner_radius_bottom_left": self.corner_radius_bottom_left,
            "shadow_color": list(self.shadow_color),
            "shadow_size": self.shadow_size,
            "shadow_offset_x": self.shadow_offset_x,
            "shadow_offset_y": self.shadow_offset_y,
            "anti_aliasing": self.anti_aliasing,
            "expand_margin_left": self.expand_margin_left,
            "expand_margin_right": self.expand_margin_right,
            "expand_margin_top": self.expand_margin_top,
            "expand_margin_bottom": self.expand_margin_bottom,
            "texture_path": self.texture_path,
            "content_margin_left": self.content_margin_left,
            "content_margin_right": self.content_margin_right,
            "content_margin_top": self.content_margin_top,
            "content_margin_bottom": self.content_margin_bottom,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StyleBoxFlat":
        return cls(
            resource_id=str(data.get("resource_id", "")),
            name=str(data.get("name", "StyleBoxFlat")),
            bg_color=tuple(data.get("bg_color", [40, 40, 40, 255])),
            border_color=tuple(data.get("border_color", [80, 80, 80, 255])),
            border_width=int(data.get("border_width", 1)),
            corner_radius=int(data.get("corner_radius", 0)),
            corner_radius_top_left=int(data.get("corner_radius_top_left", 0)),
            corner_radius_top_right=int(data.get("corner_radius_top_right", 0)),
            corner_radius_bottom_right=int(data.get("corner_radius_bottom_right", 0)),
            corner_radius_bottom_left=int(data.get("corner_radius_bottom_left", 0)),
            shadow_color=tuple(data.get("shadow_color", [0, 0, 0, 100])),
            shadow_size=int(data.get("shadow_size", 0)),
            shadow_offset_x=int(data.get("shadow_offset_x", 0)),
            shadow_offset_y=int(data.get("shadow_offset_y", 0)),
            anti_aliasing=bool(data.get("anti_aliasing", True)),
            expand_margin_left=int(data.get("expand_margin_left", 0)),
            expand_margin_right=int(data.get("expand_margin_right", 0)),
            expand_margin_top=int(data.get("expand_margin_top", 0)),
            expand_margin_bottom=int(data.get("expand_margin_bottom", 0)),
            texture_path=str(data.get("texture_path", "")),
            content_margin_left=int(data.get("content_margin_left", 4)),
            content_margin_right=int(data.get("content_margin_right", 4)),
            content_margin_top=int(data.get("content_margin_top", 4)),
            content_margin_bottom=int(data.get("content_margin_bottom", 4)),
        )

    def __repr__(self) -> str:
        return (
            f"StyleBoxFlat(id={self.resource_id!r}, name={self.name!r}, "
            f"bg={self.bg_color}, corner_radius={self.corner_radius})"
        )
