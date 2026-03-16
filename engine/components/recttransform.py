"""
engine/components/recttransform.py - Layout serializable para UI overlay.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class RectTransform(Component):
    """Describe anclas, pivote y tamano de un nodo UI."""

    def __init__(
        self,
        enabled: bool = True,
        anchor_min_x: float = 0.5,
        anchor_min_y: float = 0.5,
        anchor_max_x: float = 0.5,
        anchor_max_y: float = 0.5,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        anchored_x: float = 0.0,
        anchored_y: float = 0.0,
        width: float = 100.0,
        height: float = 40.0,
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
    ) -> None:
        self.enabled = enabled
        self.anchor_min_x = float(anchor_min_x)
        self.anchor_min_y = float(anchor_min_y)
        self.anchor_max_x = float(anchor_max_x)
        self.anchor_max_y = float(anchor_max_y)
        self.pivot_x = float(pivot_x)
        self.pivot_y = float(pivot_y)
        self.anchored_x = float(anchored_x)
        self.anchored_y = float(anchored_y)
        self.width = float(width)
        self.height = float(height)
        self.rotation = float(rotation)
        self.scale_x = float(scale_x)
        self.scale_y = float(scale_y)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "anchor_min_x": self.anchor_min_x,
            "anchor_min_y": self.anchor_min_y,
            "anchor_max_x": self.anchor_max_x,
            "anchor_max_y": self.anchor_max_y,
            "pivot_x": self.pivot_x,
            "pivot_y": self.pivot_y,
            "anchored_x": self.anchored_x,
            "anchored_y": self.anchored_y,
            "width": self.width,
            "height": self.height,
            "rotation": self.rotation,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RectTransform":
        return cls(
            enabled=data.get("enabled", True),
            anchor_min_x=data.get("anchor_min_x", 0.5),
            anchor_min_y=data.get("anchor_min_y", 0.5),
            anchor_max_x=data.get("anchor_max_x", data.get("anchor_min_x", 0.5)),
            anchor_max_y=data.get("anchor_max_y", data.get("anchor_min_y", 0.5)),
            pivot_x=data.get("pivot_x", 0.5),
            pivot_y=data.get("pivot_y", 0.5),
            anchored_x=data.get("anchored_x", 0.0),
            anchored_y=data.get("anchored_y", 0.0),
            width=data.get("width", 100.0),
            height=data.get("height", 40.0),
            rotation=data.get("rotation", 0.0),
            scale_x=data.get("scale_x", 1.0),
            scale_y=data.get("scale_y", 1.0),
        )
