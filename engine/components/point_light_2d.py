"""
engine/components/point_light_2d.py - Radial point light 2D.

Separate from Light2D. Adapted from Godot PointLight2D.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component

VALID_SHADOW_FILTERS = {"none", "pcf5", "pcf13"}


class PointLight2D(Component):
    """Godot PointLight2D — radial point light."""

    def __init__(
        self,
        color: tuple[int, int, int, int] = (255, 255, 255, 255),
        energy: float = 1.0,
        radius: float = 100.0,
        texture_path: str = "",
        texture_scale: float = 1.0,
        texture_offset_x: float = 0.0,
        texture_offset_y: float = 0.0,
        shadow_enabled: bool = False,
        shadow_color: tuple[int, int, int, int] = (0, 0, 0, 100),
        shadow_filter: str = "none",
        blend_mode: str = "add",
        z_min: int = -1024,
        z_max: int = 1024,
    ) -> None:
        self.enabled: bool = True
        self.color: tuple[int, int, int, int] = self._clamp_color(color)
        self.energy: float = max(0.0, float(energy))
        self.radius: float = max(0.0, float(radius))
        self.texture_path: str = str(texture_path or "")
        self.texture_scale: float = float(texture_scale)
        self.texture_offset_x: float = float(texture_offset_x)
        self.texture_offset_y: float = float(texture_offset_y)
        self.shadow_enabled: bool = bool(shadow_enabled)
        self.shadow_color: tuple[int, int, int, int] = self._clamp_color(shadow_color)
        self.shadow_filter: str = shadow_filter if shadow_filter in VALID_SHADOW_FILTERS else "none"
        self.blend_mode: str = str(blend_mode or "add")
        self.z_min: int = int(z_min)
        self.z_max: int = int(z_max)

    @staticmethod
    def _clamp_color(value: object) -> tuple[int, int, int, int]:
        if not isinstance(value, (tuple, list)):
            return (255, 255, 255, 255)
        seq = list(value)
        while len(seq) < 4:
            seq.append(255)
        seq = seq[:4]
        try:
            return tuple(max(0, min(255, int(v))) for v in seq)
        except (ValueError, TypeError):
            return (255, 255, 255, 255)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "color": list(self.color),
            "energy": self.energy,
            "radius": self.radius,
            "texture_path": self.texture_path,
            "texture_scale": self.texture_scale,
            "texture_offset_x": self.texture_offset_x,
            "texture_offset_y": self.texture_offset_y,
            "shadow_enabled": self.shadow_enabled,
            "shadow_color": list(self.shadow_color),
            "shadow_filter": self.shadow_filter,
            "blend_mode": self.blend_mode,
            "z_min": self.z_min,
            "z_max": self.z_max,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PointLight2D":
        raw_color = data.get("color", [255, 255, 255, 255])
        raw_shadow_color = data.get("shadow_color", [0, 0, 0, 100])
        component = cls(
            color=tuple(raw_color) if isinstance(raw_color, (tuple, list)) else (255, 255, 255, 255),
            energy=data.get("energy", 1.0),
            radius=data.get("radius", 100.0),
            texture_path=data.get("texture_path", ""),
            texture_scale=data.get("texture_scale", 1.0),
            texture_offset_x=data.get("texture_offset_x", 0.0),
            texture_offset_y=data.get("texture_offset_y", 0.0),
            shadow_enabled=data.get("shadow_enabled", False),
            shadow_color=tuple(raw_shadow_color) if isinstance(raw_shadow_color, (tuple, list)) else (0, 0, 0, 100),
            shadow_filter=data.get("shadow_filter", "none"),
            blend_mode=data.get("blend_mode", "add"),
            z_min=data.get("z_min", -1024),
            z_max=data.get("z_max", 1024),
        )
        component.enabled = bool(data.get("enabled", True))
        return component
