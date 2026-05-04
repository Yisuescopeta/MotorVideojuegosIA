"""
engine/components/ui_ninepatch.py - Rectangulo 9-slice escalable (adaptado Godot NinePatchRect).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


def _color_tuple(value: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    r, g, b, a = value
    return (int(r), int(g), int(b), int(a))


class UINinePatchRect(Component):
    """Rectangulo 9-slice escalable (adaptado Godot NinePatchRect).

    Divide una textura en 9 regiones: 4 esquinas fijas, 4 bordes escalables,
    y centro escalable. Util para paneles y botones con bordes decorativos.
    """

    def __init__(
        self,
        enabled: bool = True,
        texture_path: str = "",
        patch_margin_left: int = 8,
        patch_margin_right: int = 8,
        patch_margin_top: int = 8,
        patch_margin_bottom: int = 8,
        draw_center: bool = True,
        modulate: tuple[int, int, int, int] = (255, 255, 255, 255),
    ) -> None:
        self.enabled = enabled
        self.texture_path = str(texture_path or "")
        self.patch_margin_left = int(patch_margin_left)
        self.patch_margin_right = int(patch_margin_right)
        self.patch_margin_top = int(patch_margin_top)
        self.patch_margin_bottom = int(patch_margin_bottom)
        self.draw_center = bool(draw_center)
        self.modulate = _color_tuple(modulate)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "texture_path": self.texture_path,
            "patch_margin_left": self.patch_margin_left,
            "patch_margin_right": self.patch_margin_right,
            "patch_margin_top": self.patch_margin_top,
            "patch_margin_bottom": self.patch_margin_bottom,
            "draw_center": self.draw_center,
            "modulate": list(self.modulate),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UINinePatchRect":
        return cls(
            enabled=data.get("enabled", True),
            texture_path=data.get("texture_path", ""),
            patch_margin_left=data.get("patch_margin_left", 8),
            patch_margin_right=data.get("patch_margin_right", 8),
            patch_margin_top=data.get("patch_margin_top", 8),
            patch_margin_bottom=data.get("patch_margin_bottom", 8),
            draw_center=data.get("draw_center", True),
            modulate=tuple(data.get("modulate", [255, 255, 255, 255])),  # type: ignore[arg-type]
        )
