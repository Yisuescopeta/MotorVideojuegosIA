"""engine/resources/stylebox_resource.py — StyleBox resource adaptado de Godot StyleBox.

StyleBoxResource define estilos de fondo para controles UI.
Soporta: flat (color sólido), texture (imagen de fondo),
ninepatch (9-slice para bordes escalables).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StyleBoxResource:
    """Estilo de fondo para controles UI (adaptado de Godot StyleBox).

    Soporta: flat (color sólido), texture (imagen de fondo),
    ninepatch (9-slice para bordes escalables).
    """

    resource_id: str = ""
    name: str = "StyleBox"
    style_type: str = "flat"
    bg_color: tuple[int, int, int, int] = (40, 40, 40, 255)
    border_color: tuple[int, int, int, int] = (60, 60, 60, 255)
    border_width: int = 0
    corner_radius: int = 0
    texture_path: str = ""
    margin_left: int = 8
    margin_right: int = 8
    margin_top: int = 8
    margin_bottom: int = 8
    content_margin_left: int = 4
    content_margin_right: int = 4
    content_margin_top: int = 4
    content_margin_bottom: int = 4

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "name": self.name,
            "style_type": self.style_type,
            "bg_color": list(self.bg_color),
            "border_color": list(self.border_color),
            "border_width": self.border_width,
            "corner_radius": self.corner_radius,
            "texture_path": self.texture_path,
            "margin_left": self.margin_left,
            "margin_right": self.margin_right,
            "margin_top": self.margin_top,
            "margin_bottom": self.margin_bottom,
            "content_margin_left": self.content_margin_left,
            "content_margin_right": self.content_margin_right,
            "content_margin_top": self.content_margin_top,
            "content_margin_bottom": self.content_margin_bottom,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StyleBoxResource":
        return cls(
            resource_id=str(data.get("resource_id", "")),
            name=str(data.get("name", "StyleBox")),
            style_type=str(data.get("style_type", "flat")),
            bg_color=tuple(data.get("bg_color", [40, 40, 40, 255])),
            border_color=tuple(data.get("border_color", [60, 60, 60, 255])),
            border_width=int(data.get("border_width", 0)),
            corner_radius=int(data.get("corner_radius", 0)),
            texture_path=str(data.get("texture_path", "")),
            margin_left=int(data.get("margin_left", 8)),
            margin_right=int(data.get("margin_right", 8)),
            margin_top=int(data.get("margin_top", 8)),
            margin_bottom=int(data.get("margin_bottom", 8)),
            content_margin_left=int(data.get("content_margin_left", 4)),
            content_margin_right=int(data.get("content_margin_right", 4)),
            content_margin_top=int(data.get("content_margin_top", 4)),
            content_margin_bottom=int(data.get("content_margin_bottom", 4)),
        )

    def __repr__(self) -> str:
        return (
            f"StyleBoxResource(id={self.resource_id!r}, name={self.name!r}, "
            f"type={self.style_type})"
        )
