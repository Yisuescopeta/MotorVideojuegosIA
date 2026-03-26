"""
engine/components/uitext.py - Texto UI serializable.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class UIText(Component):
    """Texto renderizado en un Canvas overlay."""

    def __init__(
        self,
        enabled: bool = True,
        text: str = "",
        font_size: int = 24,
        color: tuple[int, int, int, int] = (255, 255, 255, 255),
        alignment: str = "center",
        wrap: bool = False,
    ) -> None:
        self.enabled = enabled
        self.text = str(text)
        self.font_size = max(1, int(font_size))
        self.color = tuple(int(v) for v in color)
        self.alignment = str(alignment or "center")
        self.wrap = bool(wrap)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "text": self.text,
            "font_size": self.font_size,
            "color": list(self.color),
            "alignment": self.alignment,
            "wrap": self.wrap,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIText":
        return cls(
            enabled=data.get("enabled", True),
            text=data.get("text", ""),
            font_size=data.get("font_size", 24),
            color=tuple(data.get("color", [255, 255, 255, 255])),  # type: ignore[arg-type]
            alignment=data.get("alignment", "center"),
            wrap=data.get("wrap", False),
        )
