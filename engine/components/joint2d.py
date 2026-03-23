from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class Joint2D(Component):
    """Joint 2D serializable para backends que soporten restricciones fisicas."""

    VALID_TYPES = {"fixed", "distance"}

    def __init__(
        self,
        joint_type: str = "distance",
        connected_entity: str = "",
        anchor_x: float = 0.0,
        anchor_y: float = 0.0,
        connected_anchor_x: float = 0.0,
        connected_anchor_y: float = 0.0,
        rest_length: float = 0.0,
        damping_ratio: float = 0.0,
        frequency_hz: float = 0.0,
        collide_connected: bool = False,
    ) -> None:
        self.enabled: bool = True
        self.joint_type: str = str(joint_type or "distance")
        if self.joint_type not in self.VALID_TYPES:
            self.joint_type = "distance"
        self.connected_entity: str = str(connected_entity or "")
        self.anchor_x: float = float(anchor_x)
        self.anchor_y: float = float(anchor_y)
        self.connected_anchor_x: float = float(connected_anchor_x)
        self.connected_anchor_y: float = float(connected_anchor_y)
        self.rest_length: float = float(rest_length)
        self.damping_ratio: float = float(damping_ratio)
        self.frequency_hz: float = float(frequency_hz)
        self.collide_connected: bool = bool(collide_connected)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "joint_type": self.joint_type,
            "connected_entity": self.connected_entity,
            "anchor_x": self.anchor_x,
            "anchor_y": self.anchor_y,
            "connected_anchor_x": self.connected_anchor_x,
            "connected_anchor_y": self.connected_anchor_y,
            "rest_length": self.rest_length,
            "damping_ratio": self.damping_ratio,
            "frequency_hz": self.frequency_hz,
            "collide_connected": self.collide_connected,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Joint2D":
        component = cls(
            joint_type=data.get("joint_type", "distance"),
            connected_entity=data.get("connected_entity", ""),
            anchor_x=data.get("anchor_x", 0.0),
            anchor_y=data.get("anchor_y", 0.0),
            connected_anchor_x=data.get("connected_anchor_x", 0.0),
            connected_anchor_y=data.get("connected_anchor_y", 0.0),
            rest_length=data.get("rest_length", 0.0),
            damping_ratio=data.get("damping_ratio", 0.0),
            frequency_hz=data.get("frequency_hz", 0.0),
            collide_connected=data.get("collide_connected", False),
        )
        component.enabled = data.get("enabled", True)
        return component
