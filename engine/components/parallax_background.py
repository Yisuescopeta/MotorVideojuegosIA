"""
engine/components/parallax_background.py - ParallaxBackground container component.

Groups child entities with ParallaxLayer, providing common scroll and limit
settings adapted from Godot ParallaxBackground.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class ParallaxBackground(Component):
    """Container that groups ParallaxLayers under shared base offset/scale/limit."""

    def __init__(
        self,
        scroll_base_offset_x: float = 0.0,
        scroll_base_offset_y: float = 0.0,
        scroll_base_scale_x: float = 1.0,
        scroll_base_scale_y: float = 1.0,
        scroll_limit_begin_x: float = 0.0,
        scroll_limit_begin_y: float = 0.0,
        scroll_limit_end_x: float = 0.0,
        scroll_limit_end_y: float = 0.0,
        scroll_ignore_camera_zoom: bool = False,
    ) -> None:
        self.scroll_base_offset_x: float = float(scroll_base_offset_x)
        self.scroll_base_offset_y: float = float(scroll_base_offset_y)
        self.scroll_base_scale_x: float = float(scroll_base_scale_x)
        self.scroll_base_scale_y: float = float(scroll_base_scale_y)
        self.scroll_limit_begin_x: float = float(scroll_limit_begin_x)
        self.scroll_limit_begin_y: float = float(scroll_limit_begin_y)
        self.scroll_limit_end_x: float = float(scroll_limit_end_x)
        self.scroll_limit_end_y: float = float(scroll_limit_end_y)
        self.scroll_ignore_camera_zoom: bool = bool(scroll_ignore_camera_zoom)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scroll_base_offset_x": self.scroll_base_offset_x,
            "scroll_base_offset_y": self.scroll_base_offset_y,
            "scroll_base_scale_x": self.scroll_base_scale_x,
            "scroll_base_scale_y": self.scroll_base_scale_y,
            "scroll_limit_begin_x": self.scroll_limit_begin_x,
            "scroll_limit_begin_y": self.scroll_limit_begin_y,
            "scroll_limit_end_x": self.scroll_limit_end_x,
            "scroll_limit_end_y": self.scroll_limit_end_y,
            "scroll_ignore_camera_zoom": self.scroll_ignore_camera_zoom,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParallaxBackground":
        return cls(
            scroll_base_offset_x=data.get("scroll_base_offset_x", 0.0),
            scroll_base_offset_y=data.get("scroll_base_offset_y", 0.0),
            scroll_base_scale_x=data.get("scroll_base_scale_x", 1.0),
            scroll_base_scale_y=data.get("scroll_base_scale_y", 1.0),
            scroll_limit_begin_x=data.get("scroll_limit_begin_x", 0.0),
            scroll_limit_begin_y=data.get("scroll_limit_begin_y", 0.0),
            scroll_limit_end_x=data.get("scroll_limit_end_x", 0.0),
            scroll_limit_end_y=data.get("scroll_limit_end_y", 0.0),
            scroll_ignore_camera_zoom=data.get("scroll_ignore_camera_zoom", False),
        )
