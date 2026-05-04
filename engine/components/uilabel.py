"""
engine/components/uilabel.py — Label con soporte rich text (adaptado Godot Label).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


def _color_tuple(value: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    r, g, b, a = value
    return (int(r), int(g), int(b), int(a))


class Label(Component):
    """Etiqueta de texto con soporte rich text (adaptado Godot Label)."""

    def __init__(
        self,
        enabled: bool = True,
        text: str = "",
        font_size: int = 16,
        color: tuple[int, int, int, int] = (255, 255, 255, 255),
        alignment: str = "left",
        autowrap: bool = False,
        clip_text: bool = False,
    ) -> None:
        self.enabled = enabled
        self.text = str(text)
        self.font_size = max(10, int(font_size))
        self.color = _color_tuple(color)
        self.alignment = str(alignment or "left")
        self.autowrap = bool(autowrap)
        self.clip_text = bool(clip_text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "text": self.text,
            "font_size": self.font_size,
            "color": list(self.color),
            "alignment": self.alignment,
            "autowrap": self.autowrap,
            "clip_text": self.clip_text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Label":
        return cls(
            enabled=data.get("enabled", True),
            text=data.get("text", ""),
            font_size=data.get("font_size", 16),
            color=tuple(data.get("color", [255, 255, 255, 255])),  # type: ignore[arg-type]
            alignment=data.get("alignment", "left"),
            autowrap=data.get("autowrap", False),
            clip_text=data.get("clip_text", False),
        )
