"""
engine/components/canvas.py - Canvas UI overlay serializable.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class Canvas(Component):
    """Define un arbol UI overlay y su escalado base."""

    def __init__(
        self,
        enabled: bool = True,
        render_mode: str = "screen_space_overlay",
        reference_width: int = 800,
        reference_height: int = 600,
        match_mode: str = "stretch",
        sort_order: int = 0,
        theme_resource_path: str = "",
        follow_viewport: bool = True,
        follow_viewport_scale: float = 1.0,
        layer_transform_x: float = 0.0,
        layer_transform_y: float = 0.0,
        layer_rotation: float = 0.0,
        layer_scale_x: float = 1.0,
        layer_scale_y: float = 1.0,
    ) -> None:
        self.enabled = enabled
        self.render_mode = str(render_mode or "screen_space_overlay")
        self.reference_width = max(1, int(reference_width))
        self.reference_height = max(1, int(reference_height))
        self.match_mode = str(match_mode or "stretch")
        self.sort_order = int(sort_order)
        self.theme_resource_path = str(theme_resource_path or "")
        self.follow_viewport = bool(follow_viewport)
        self.follow_viewport_scale = float(follow_viewport_scale)
        self.layer_transform_x = float(layer_transform_x)
        self.layer_transform_y = float(layer_transform_y)
        self.layer_rotation = float(layer_rotation)
        self.layer_scale_x = float(layer_scale_x)
        self.layer_scale_y = float(layer_scale_y)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "render_mode": self.render_mode,
            "reference_width": self.reference_width,
            "reference_height": self.reference_height,
            "match_mode": self.match_mode,
            "sort_order": self.sort_order,
            "theme_resource_path": self.theme_resource_path,
            "follow_viewport": self.follow_viewport,
            "follow_viewport_scale": self.follow_viewport_scale,
            "layer_transform_x": self.layer_transform_x,
            "layer_transform_y": self.layer_transform_y,
            "layer_rotation": self.layer_rotation,
            "layer_scale_x": self.layer_scale_x,
            "layer_scale_y": self.layer_scale_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Canvas":
        return cls(
            enabled=data.get("enabled", True),
            render_mode=data.get("render_mode", "screen_space_overlay"),
            reference_width=data.get("reference_width", 800),
            reference_height=data.get("reference_height", 600),
            match_mode=data.get("match_mode", "stretch"),
            sort_order=data.get("sort_order", 0),
            theme_resource_path=data.get("theme_resource_path", ""),
            follow_viewport=data.get("follow_viewport", True),
            follow_viewport_scale=data.get("follow_viewport_scale", 1.0),
            layer_transform_x=data.get("layer_transform_x", 0.0),
            layer_transform_y=data.get("layer_transform_y", 0.0),
            layer_rotation=data.get("layer_rotation", 0.0),
            layer_scale_x=data.get("layer_scale_x", 1.0),
            layer_scale_y=data.get("layer_scale_y", 1.0),
        )
