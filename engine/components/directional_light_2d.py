"""
engine/components/directional_light_2d.py - Luz direccional 2D serializable.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class DirectionalLight2D(Component):
    """Light that projects in one direction with configurable distance."""

    BLEND_ADD: str = "add"
    BLEND_SUB: str = "sub"
    BLEND_MIX: str = "mix"

    def __init__(
        self,
        color_r: int = 255,
        color_g: int = 255,
        color_b: int = 255,
        color_a: int = 255,
        energy: float = 1.0,
        max_distance: float = 500.0,
        direction_x: float = 0.0,
        direction_y: float = -1.0,
        blend_mode: str = "add",
        shadow_enabled: bool = False,
        shadow_color_r: int = 0,
        shadow_color_g: int = 0,
        shadow_color_b: int = 0,
        shadow_color_a: int = 100,
        shadow_smooth: float = 0.0,
        z_min: float = -1024.0,
        z_max: float = 1024.0,
    ) -> None:
        self.enabled: bool = True
        self.color_r: int = max(0, min(255, color_r))
        self.color_g: int = max(0, min(255, color_g))
        self.color_b: int = max(0, min(255, color_b))
        self.color_a: int = max(0, min(255, color_a))
        self.energy: float = max(0.0, float(energy))
        self.max_distance: float = max(1.0, float(max_distance))
        self.direction_x: float = float(direction_x)
        self.direction_y: float = float(direction_y)
        self.blend_mode: str = str(blend_mode or "add")
        self.shadow_enabled: bool = bool(shadow_enabled)
        self.shadow_color_r: int = max(0, min(255, shadow_color_r))
        self.shadow_color_g: int = max(0, min(255, shadow_color_g))
        self.shadow_color_b: int = max(0, min(255, shadow_color_b))
        self.shadow_color_a: int = max(0, min(255, shadow_color_a))
        self.shadow_smooth: float = max(0.0, float(shadow_smooth))
        self.z_min: float = float(z_min)
        self.z_max: float = float(z_max)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "color_r": self.color_r,
            "color_g": self.color_g,
            "color_b": self.color_b,
            "color_a": self.color_a,
            "energy": self.energy,
            "max_distance": self.max_distance,
            "direction_x": self.direction_x,
            "direction_y": self.direction_y,
            "blend_mode": self.blend_mode,
            "shadow_enabled": self.shadow_enabled,
            "shadow_color_r": self.shadow_color_r,
            "shadow_color_g": self.shadow_color_g,
            "shadow_color_b": self.shadow_color_b,
            "shadow_color_a": self.shadow_color_a,
            "shadow_smooth": self.shadow_smooth,
            "z_min": self.z_min,
            "z_max": self.z_max,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DirectionalLight2D":
        component = cls(
            color_r=data.get("color_r", 255),
            color_g=data.get("color_g", 255),
            color_b=data.get("color_b", 255),
            color_a=data.get("color_a", 255),
            energy=data.get("energy", 1.0),
            max_distance=data.get("max_distance", 500.0),
            direction_x=data.get("direction_x", 0.0),
            direction_y=data.get("direction_y", -1.0),
            blend_mode=data.get("blend_mode", "add"),
            shadow_enabled=data.get("shadow_enabled", False),
            shadow_color_r=data.get("shadow_color_r", 0),
            shadow_color_g=data.get("shadow_color_g", 0),
            shadow_color_b=data.get("shadow_color_b", 0),
            shadow_color_a=data.get("shadow_color_a", 100),
            shadow_smooth=data.get("shadow_smooth", 0.0),
            z_min=data.get("z_min", -1024.0),
            z_max=data.get("z_max", 1024.0),
        )
        component.enabled = data.get("enabled", True)
        return component
