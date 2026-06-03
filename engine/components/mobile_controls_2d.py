"""Serializable mobile control overlay configuration."""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class MobileControls2D(Component):
    """Virtual joystick/buttons that drive a target InputMap at runtime."""

    def __init__(
        self,
        enabled: bool = True,
        target_entity: str = "Player",
        profile: str = "platformer",
        left_stick_enabled: bool = True,
        action_1_enabled: bool = True,
        action_2_enabled: bool = True,
        left_stick_anchor_x: float = 0.16,
        left_stick_anchor_y: float = 0.78,
        left_stick_radius: float = 86.0,
        left_stick_knob_radius: float = 34.0,
        action_1_anchor_x: float = 0.84,
        action_1_anchor_y: float = 0.78,
        action_1_radius: float = 54.0,
        action_2_anchor_x: float = 0.72,
        action_2_anchor_y: float = 0.84,
        action_2_radius: float = 46.0,
        opacity: float = 0.65,
        deadzone: float = 0.18,
        movement_mode: str = "joystick",
    ) -> None:
        self.enabled = bool(enabled)
        self.target_entity = str(target_entity or "Player")
        self.profile = str(profile or "platformer")
        self.movement_mode = self._normalize_movement_mode(movement_mode)
        self.left_stick_enabled = bool(left_stick_enabled)
        self.action_1_enabled = bool(action_1_enabled)
        self.action_2_enabled = bool(action_2_enabled)
        self.left_stick_anchor_x = float(left_stick_anchor_x)
        self.left_stick_anchor_y = float(left_stick_anchor_y)
        self.left_stick_radius = max(1.0, float(left_stick_radius))
        self.left_stick_knob_radius = max(1.0, float(left_stick_knob_radius))
        self.action_1_anchor_x = float(action_1_anchor_x)
        self.action_1_anchor_y = float(action_1_anchor_y)
        self.action_1_radius = max(1.0, float(action_1_radius))
        self.action_2_anchor_x = float(action_2_anchor_x)
        self.action_2_anchor_y = float(action_2_anchor_y)
        self.action_2_radius = max(1.0, float(action_2_radius))
        self.opacity = max(0.0, min(1.0, float(opacity)))
        self.deadzone = max(0.0, min(0.95, float(deadzone)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "target_entity": self.target_entity,
            "profile": self.profile,
            "movement_mode": self.movement_mode,
            "left_stick_enabled": self.left_stick_enabled,
            "action_1_enabled": self.action_1_enabled,
            "action_2_enabled": self.action_2_enabled,
            "left_stick_anchor_x": self.left_stick_anchor_x,
            "left_stick_anchor_y": self.left_stick_anchor_y,
            "left_stick_radius": self.left_stick_radius,
            "left_stick_knob_radius": self.left_stick_knob_radius,
            "action_1_anchor_x": self.action_1_anchor_x,
            "action_1_anchor_y": self.action_1_anchor_y,
            "action_1_radius": self.action_1_radius,
            "action_2_anchor_x": self.action_2_anchor_x,
            "action_2_anchor_y": self.action_2_anchor_y,
            "action_2_radius": self.action_2_radius,
            "opacity": self.opacity,
            "deadzone": self.deadzone,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MobileControls2D":
        return cls(
            enabled=data.get("enabled", True),
            target_entity=data.get("target_entity", "Player"),
            profile=data.get("profile", "platformer"),
            movement_mode=data.get("movement_mode", "joystick"),
            left_stick_enabled=data.get("left_stick_enabled", True),
            action_1_enabled=data.get("action_1_enabled", True),
            action_2_enabled=data.get("action_2_enabled", True),
            left_stick_anchor_x=data.get("left_stick_anchor_x", 0.16),
            left_stick_anchor_y=data.get("left_stick_anchor_y", 0.78),
            left_stick_radius=data.get("left_stick_radius", 86.0),
            left_stick_knob_radius=data.get("left_stick_knob_radius", 34.0),
            action_1_anchor_x=data.get("action_1_anchor_x", 0.84),
            action_1_anchor_y=data.get("action_1_anchor_y", 0.78),
            action_1_radius=data.get("action_1_radius", 54.0),
            action_2_anchor_x=data.get("action_2_anchor_x", 0.72),
            action_2_anchor_y=data.get("action_2_anchor_y", 0.84),
            action_2_radius=data.get("action_2_radius", 46.0),
            opacity=data.get("opacity", 0.65),
            deadzone=data.get("deadzone", 0.18),
        )

    @staticmethod
    def _normalize_movement_mode(value: str) -> str:
        mode = str(value or "joystick").strip().lower()
        return mode if mode in {"joystick", "dpad"} else "joystick"
