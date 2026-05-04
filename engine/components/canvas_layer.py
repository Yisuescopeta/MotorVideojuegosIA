"""
engine/components/canvas_layer.py - CanvasLayer: independent render layer with its own transform.
Adapted from Godot CanvasLayer.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class CanvasLayer(Component):
    """Godot CanvasLayer — independent render layer with its own transform.

    Entities with this component define a render layer. Their own Sprite/Polygon2D
    children render with the layer's offset, rotation, and scale applied.
    The render system groups entities by canvas_layer_ref and renders each
    group sorted by CanvasLayer.layer value (higher = on top).
    """

    def __init__(
        self,
        layer: int = 1,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        visible: bool = True,
        follow_viewport: bool = False,
        follow_viewport_scale: float = 1.0,
        custom_viewport_path: str = "",
    ) -> None:
        self.layer: int = int(layer)
        self.offset_x: float = float(offset_x)
        self.offset_y: float = float(offset_y)
        self.rotation: float = float(rotation)
        self.scale_x: float = float(scale_x)
        self.scale_y: float = float(scale_y)
        self.visible: bool = bool(visible)
        self.follow_viewport: bool = bool(follow_viewport)
        self.follow_viewport_scale: float = float(follow_viewport_scale)
        self.custom_viewport_path: str = str(custom_viewport_path or "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "rotation": self.rotation,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "visible": self.visible,
            "follow_viewport": self.follow_viewport,
            "follow_viewport_scale": self.follow_viewport_scale,
            "custom_viewport_path": self.custom_viewport_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CanvasLayer":
        return cls(
            layer=data.get("layer", 1),
            offset_x=data.get("offset_x", 0.0),
            offset_y=data.get("offset_y", 0.0),
            rotation=data.get("rotation", 0.0),
            scale_x=data.get("scale_x", 1.0),
            scale_y=data.get("scale_y", 1.0),
            visible=data.get("visible", True),
            follow_viewport=data.get("follow_viewport", False),
            follow_viewport_scale=data.get("follow_viewport_scale", 1.0),
            custom_viewport_path=data.get("custom_viewport_path", ""),
        )
