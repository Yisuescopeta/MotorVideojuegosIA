"""
engine/components/camera2d.py - Camara 2D serializable y editable por IA
"""

from typing import Any

from engine.ecs.component import Component


class Camera2D(Component):
    """Camara 2D simple al estilo Unity, orientada a datos serializables."""

    def __init__(
        self,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        zoom: float = 1.0,
        rotation: float = 0.0,
        is_primary: bool = True,
        follow_entity: str = "",
        framing_mode: str = "platformer",
        dead_zone_width: float = 0.0,
        dead_zone_height: float = 0.0,
        clamp_left: float | None = None,
        clamp_right: float | None = None,
        clamp_top: float | None = None,
        clamp_bottom: float | None = None,
        recenter_on_play: bool = True,
    ) -> None:
        self.enabled: bool = True
        self.offset_x: float = offset_x
        self.offset_y: float = offset_y
        self.zoom: float = zoom
        self.rotation: float = rotation
        self.is_primary: bool = is_primary
        self.follow_entity: str = follow_entity
        self.framing_mode: str = framing_mode
        self.dead_zone_width: float = dead_zone_width
        self.dead_zone_height: float = dead_zone_height
        self.clamp_left: float | None = clamp_left
        self.clamp_right: float | None = clamp_right
        self.clamp_top: float | None = clamp_top
        self.clamp_bottom: float | None = clamp_bottom
        self.recenter_on_play: bool = recenter_on_play

        # Estado de runtime no serializable para seguimiento suave.
        self._runtime_target_x: float = 0.0
        self._runtime_target_y: float = 0.0
        self._has_recentred: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "zoom": self.zoom,
            "rotation": self.rotation,
            "is_primary": self.is_primary,
            "follow_entity": self.follow_entity,
            "framing_mode": self.framing_mode,
            "dead_zone_width": self.dead_zone_width,
            "dead_zone_height": self.dead_zone_height,
            "clamp_left": self.clamp_left,
            "clamp_right": self.clamp_right,
            "clamp_top": self.clamp_top,
            "clamp_bottom": self.clamp_bottom,
            "recenter_on_play": self.recenter_on_play,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Camera2D":
        component = cls(
            offset_x=data.get("offset_x", 0.0),
            offset_y=data.get("offset_y", 0.0),
            zoom=data.get("zoom", 1.0),
            rotation=data.get("rotation", 0.0),
            is_primary=data.get("is_primary", True),
            follow_entity=data.get("follow_entity", ""),
            framing_mode=data.get("framing_mode", "platformer"),
            dead_zone_width=data.get("dead_zone_width", 0.0),
            dead_zone_height=data.get("dead_zone_height", 0.0),
            clamp_left=data.get("clamp_left"),
            clamp_right=data.get("clamp_right"),
            clamp_top=data.get("clamp_top"),
            clamp_bottom=data.get("clamp_bottom"),
            recenter_on_play=data.get("recenter_on_play", True),
        )
        component.enabled = data.get("enabled", True)
        return component
