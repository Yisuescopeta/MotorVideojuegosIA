"""
engine/components/light2d.py - Fuente de luz 2D serializable y editable por IA
"""

from typing import Any

from engine.ecs.component import Component


class Light2D(Component):
    """Luz 2D puntual con radio, energia, modo de blend y falloff."""

    FALLOFF_CONSTANT: str = "constant"
    FALLOFF_LINEAR: str = "linear"
    FALLOFF_QUADRATIC: str = "quadratic"
    BLEND_ADDITIVE: str = "additive"
    BLEND_MULTIPLIED: str = "multiplied"

    def __init__(
        self,
        color_r: int = 255,
        color_g: int = 255,
        color_b: int = 255,
        color_a: int = 200,
        energy: float = 1.0,
        radius: float = 100.0,
        falloff_type: str = "quadratic",
        blend_mode: str = "additive",
        z_index: int = 0,
    ) -> None:
        self.enabled: bool = True
        self.color_r: int = max(0, min(255, color_r))
        self.color_g: int = max(0, min(255, color_g))
        self.color_b: int = max(0, min(255, color_b))
        self.color_a: int = max(0, min(255, color_a))
        self.energy: float = max(0.0, energy)
        self.radius: float = max(1.0, radius)
        self.falloff_type: str = falloff_type
        self.blend_mode: str = blend_mode
        self.z_index: int = z_index

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "color_r": self.color_r,
            "color_g": self.color_g,
            "color_b": self.color_b,
            "color_a": self.color_a,
            "energy": self.energy,
            "radius": self.radius,
            "falloff_type": self.falloff_type,
            "blend_mode": self.blend_mode,
            "z_index": self.z_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Light2D":
        component = cls(
            color_r=data.get("color_r", 255),
            color_g=data.get("color_g", 255),
            color_b=data.get("color_b", 255),
            color_a=data.get("color_a", 200),
            energy=data.get("energy", 1.0),
            radius=data.get("radius", 100.0),
            falloff_type=data.get("falloff_type", "quadratic"),
            blend_mode=data.get("blend_mode", "additive"),
            z_index=data.get("z_index", 0),
        )
        component.enabled = data.get("enabled", True)
        return component
