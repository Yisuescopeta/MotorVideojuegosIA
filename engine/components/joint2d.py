"""Joint2D — Godot-style physical constraints between entities."""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component

VALID_JOINT_TYPES = {"fixed", "distance", "pin", "groove", "damped_spring"}


class Joint2D(Component):
    """Physical joint connecting this entity to another entity."""

    def __init__(self) -> None:
        self.enabled: bool = True
        self.joint_type: str = "fixed"
        self.connected_entity: str = ""
        self.collide_connected: bool = False

        # Pin joint
        self.softness: float = 0.0
        self.angular_limit_lower: float = -3.14159
        self.angular_limit_upper: float = 3.14159
        self.angular_limit_enabled: bool = False
        self.motor_enabled: bool = False
        self.motor_target_velocity: float = 0.0

        # Groove joint
        self.groove_length: float = 100.0
        self.initial_offset: tuple[float, float] = (0.0, 0.0)

        # Anchors (world-space offsets relative to each body)
        self.anchor_x: float = 0.0
        self.anchor_y: float = 0.0
        self.connected_anchor_x: float = 0.0
        self.connected_anchor_y: float = 0.0

        # Frequency/damping for distance joints
        self.frequency_hz: float = 0.0
        self.damping_ratio: float = 0.0

        # Damped spring
        self.rest_length: float = 50.0
        self.stiffness: float = 20.0
        self.damping: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "joint_type": self.joint_type,
            "connected_entity": self.connected_entity,
            "collide_connected": self.collide_connected,
            "softness": self.softness,
            "angular_limit_lower": self.angular_limit_lower,
            "angular_limit_upper": self.angular_limit_upper,
            "angular_limit_enabled": self.angular_limit_enabled,
            "motor_enabled": self.motor_enabled,
            "motor_target_velocity": self.motor_target_velocity,
            "anchor_x": self.anchor_x,
            "anchor_y": self.anchor_y,
            "connected_anchor_x": self.connected_anchor_x,
            "connected_anchor_y": self.connected_anchor_y,
            "frequency_hz": self.frequency_hz,
            "damping_ratio": self.damping_ratio,
            "groove_length": self.groove_length,
            "initial_offset": list(self.initial_offset),
            "rest_length": self.rest_length,
            "stiffness": self.stiffness,
            "damping": self.damping,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Joint2D:
        j = cls()
        j.enabled = data.get("enabled", True)
        j.joint_type = data.get("joint_type", "fixed")
        if j.joint_type not in VALID_JOINT_TYPES:
            j.joint_type = "fixed"
        j.connected_entity = data.get("connected_entity", "")
        j.collide_connected = data.get("collide_connected", False)
        j.softness = data.get("softness", 0.0)
        j.angular_limit_lower = data.get("angular_limit_lower", -3.14159)
        j.angular_limit_upper = data.get("angular_limit_upper", 3.14159)
        j.angular_limit_enabled = data.get("angular_limit_enabled", False)
        j.motor_enabled = data.get("motor_enabled", False)
        j.motor_target_velocity = data.get("motor_target_velocity", 0.0)
        j.anchor_x = data.get("anchor_x", 0.0)
        j.anchor_y = data.get("anchor_y", 0.0)
        j.connected_anchor_x = data.get("connected_anchor_x", 0.0)
        j.connected_anchor_y = data.get("connected_anchor_y", 0.0)
        j.frequency_hz = data.get("frequency_hz", 0.0)
        j.damping_ratio = data.get("damping_ratio", 0.0)
        j.groove_length = data.get("groove_length", 100.0)
        io = data.get("initial_offset", [0.0, 0.0])
        j.initial_offset = tuple(io) if isinstance(io, list) else (0.0, 0.0)
        j.rest_length = data.get("rest_length", 50.0)
        j.stiffness = data.get("stiffness", 20.0)
        j.damping = data.get("damping", 1.0)
        return j
