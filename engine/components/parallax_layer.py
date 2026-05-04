"""
engine/components/parallax_layer.py - Capa de parallax serializable.

Controla como se desplaza una capa respecto al movimiento de camara.
"""
from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class ParallaxLayer(Component):
    """Define una capa de parallax que se desplaza relativo al movimiento de camara."""

    def __init__(
        self,
        motion_scale_x: float = 1.0,
        motion_scale_y: float = 1.0,
        scroll_offset_x: float = 0.0,
        scroll_offset_y: float = 0.0,
        mirror_x: float = 0.0,
        mirror_y: float = 0.0,
        follow_viewport: bool = True,
        autoscroll_x: float = 0.0,
        autoscroll_y: float = 0.0,
    ) -> None:
        self.enabled: bool = True
        self.motion_scale_x: float = float(motion_scale_x)
        self.motion_scale_y: float = float(motion_scale_y)
        self.scroll_offset_x: float = float(scroll_offset_x)
        self.scroll_offset_y: float = float(scroll_offset_y)
        self.mirror_x: float = float(mirror_x)
        self.mirror_y: float = float(mirror_y)
        self.follow_viewport: bool = bool(follow_viewport)
        self.autoscroll_x: float = float(autoscroll_x)
        self.autoscroll_y: float = float(autoscroll_y)

        # Estado de runtime (no serializable)
        self._rest_x: float = 0.0
        self._rest_y: float = 0.0
        self._autoscroll_accum_x: float = 0.0
        self._autoscroll_accum_y: float = 0.0
        self._rest_captured: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "motion_scale_x": self.motion_scale_x,
            "motion_scale_y": self.motion_scale_y,
            "scroll_offset_x": self.scroll_offset_x,
            "scroll_offset_y": self.scroll_offset_y,
            "mirror_x": self.mirror_x,
            "mirror_y": self.mirror_y,
            "follow_viewport": self.follow_viewport,
            "autoscroll_x": self.autoscroll_x,
            "autoscroll_y": self.autoscroll_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParallaxLayer":
        component = cls(
            motion_scale_x=data.get("motion_scale_x", 1.0),
            motion_scale_y=data.get("motion_scale_y", 1.0),
            scroll_offset_x=data.get("scroll_offset_x", 0.0),
            scroll_offset_y=data.get("scroll_offset_y", 0.0),
            mirror_x=data.get("mirror_x", 0.0),
            mirror_y=data.get("mirror_y", 0.0),
            follow_viewport=data.get("follow_viewport", True),
            autoscroll_x=data.get("autoscroll_x", 0.0),
            autoscroll_y=data.get("autoscroll_y", 0.0),
        )
        component.enabled = data.get("enabled", True)
        return component
