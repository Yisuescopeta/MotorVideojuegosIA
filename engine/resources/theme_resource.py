"""engine/resources/theme_resource.py — Theme resource adaptado de Godot Theme.

ThemeResource agrupa StyleBoxes, colores y fuentes por tipo de control.
Mapea tipos de control a estilos: "Panel" → StyleBox, "Button" → StyleBox, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.resources.stylebox_resource import StyleBoxResource


@dataclass
class ThemeResource:
    """Tema UI que agrupa StyleBoxes, colores y fuentes (adaptado de Godot Theme).

    Mapea tipos de control a estilos: "Panel" → StyleBox, "Button" → StyleBox, etc.
    """

    resource_id: str = ""
    name: str = "Theme"
    default_font_size: int = 16
    default_font_color: tuple[int, int, int, int] = (255, 255, 255, 255)
    colors: dict[str, list[int]] = field(default_factory=dict)
    styleboxes: dict[str, dict[str, Any]] = field(default_factory=dict)
    fonts: dict[str, str] = field(default_factory=dict)

    def get_stylebox(self, control_type: str) -> StyleBoxResource | None:
        data = self.styleboxes.get(control_type)
        if data:
            return StyleBoxResource.from_dict(data)
        return None

    def set_stylebox(self, control_type: str, stylebox: StyleBoxResource) -> None:
        self.styleboxes[control_type] = stylebox.to_dict()

    def get_color(self, color_key: str) -> tuple[int, int, int, int] | None:
        raw = self.colors.get(color_key)
        if raw:
            return tuple(raw)
        return None

    def set_color(self, color_key: str, rgba: tuple[int, int, int, int]) -> None:
        self.colors[color_key] = list(rgba)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "name": self.name,
            "default_font_size": self.default_font_size,
            "default_font_color": list(self.default_font_color),
            "colors": {str(k): list(v) if isinstance(v, (list, tuple)) else v for k, v in self.colors.items()},
            "styleboxes": dict(self.styleboxes),
            "fonts": dict(self.fonts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ThemeResource":
        return cls(
            resource_id=str(data.get("resource_id", "")),
            name=str(data.get("name", "Theme")),
            default_font_size=int(data.get("default_font_size", 16)),
            default_font_color=tuple(data.get("default_font_color", [255, 255, 255, 255])),
            colors=data.get("colors", {}) or {},
            styleboxes=data.get("styleboxes", {}) or {},
            fonts=data.get("fonts", {}) or {},
        )

    def __repr__(self) -> str:
        return (
            f"ThemeResource(id={self.resource_id!r}, name={self.name!r}, "
            f"styleboxes={len(self.styleboxes)}, colors={len(self.colors)})"
        )
