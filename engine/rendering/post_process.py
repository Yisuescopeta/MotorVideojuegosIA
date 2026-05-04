"""
engine/rendering/post_process.py - Efectos de post-procesado serializables.
"""

from __future__ import annotations

from typing import Any


class PostProcessEffect:
    """Base class for post-processing effects."""

    def __init__(self, name: str = "", enabled: bool = True) -> None:
        self.name: str = str(name or self.__class__.__name__)
        self.enabled: bool = bool(enabled)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "enabled": self.enabled, "type": self.__class__.__name__}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PostProcessEffect":
        return cls(name=data.get("name", ""), enabled=data.get("enabled", True))


class BlurEffect(PostProcessEffect):
    """Gaussian blur post-processing effect."""

    def __init__(self, radius: float = 4.0, name: str = "", enabled: bool = True) -> None:
        super().__init__(name=name or "Blur", enabled=enabled)
        self.radius: float = max(0.0, float(radius))

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["radius"] = self.radius
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BlurEffect":
        return cls(
            radius=data.get("radius", 4.0),
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
        )


class ColorCorrectEffect(PostProcessEffect):
    """Color correction post-processing effect."""

    def __init__(
        self,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        name: str = "",
        enabled: bool = True,
    ) -> None:
        super().__init__(name=name or "ColorCorrect", enabled=enabled)
        self.brightness: float = max(0.0, float(brightness))
        self.contrast: float = max(0.0, float(contrast))
        self.saturation: float = max(0.0, float(saturation))

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["brightness"] = self.brightness
        result["contrast"] = self.contrast
        result["saturation"] = self.saturation
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColorCorrectEffect":
        return cls(
            brightness=data.get("brightness", 1.0),
            contrast=data.get("contrast", 1.0),
            saturation=data.get("saturation", 1.0),
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
        )
