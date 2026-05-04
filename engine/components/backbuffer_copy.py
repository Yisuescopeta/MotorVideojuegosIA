"""
engine/components/backbuffer_copy.py - Captura de region de pantalla para post-procesado.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class BackBufferCopy(Component):
    """Copies screen region for post-processing effects."""

    COPY_MODE_RECT: str = "rect"
    COPY_MODE_VIEWPORT: str = "viewport"

    def __init__(
        self,
        copy_mode: str = "rect",
        rect_x: float = 0.0,
        rect_y: float = 0.0,
        rect_w: float = 128.0,
        rect_h: float = 128.0,
    ) -> None:
        self.enabled: bool = True
        self.copy_mode: str = str(copy_mode or "rect")
        self.rect_x: float = float(rect_x)
        self.rect_y: float = float(rect_y)
        self.rect_w: float = max(1.0, float(rect_w))
        self.rect_h: float = max(1.0, float(rect_h))

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "copy_mode": self.copy_mode,
            "rect_x": self.rect_x,
            "rect_y": self.rect_y,
            "rect_w": self.rect_w,
            "rect_h": self.rect_h,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackBufferCopy":
        component = cls(
            copy_mode=data.get("copy_mode", "rect"),
            rect_x=data.get("rect_x", 0.0),
            rect_y=data.get("rect_y", 0.0),
            rect_w=data.get("rect_w", 128.0),
            rect_h=data.get("rect_h", 128.0),
        )
        component.enabled = data.get("enabled", True)
        return component
