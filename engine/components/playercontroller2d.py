"""
engine/components/playercontroller2d.py - Controlador 2D simple y serializable
"""

from typing import Any

from engine.ecs.component import Component


class PlayerController2D(Component):
    """Control lateral + salto apoyado en InputMap y RigidBody."""

    def __init__(
        self,
        move_speed: float = 180.0,
        jump_velocity: float = -320.0,
        air_control: float = 0.75,
    ) -> None:
        self.enabled: bool = True
        self.move_speed: float = move_speed
        self.jump_velocity: float = jump_velocity
        self.air_control: float = air_control
        self._jump_was_pressed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "move_speed": self.move_speed,
            "jump_velocity": self.jump_velocity,
            "air_control": self.air_control,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerController2D":
        component = cls(
            move_speed=data.get("move_speed", 180.0),
            jump_velocity=data.get("jump_velocity", -320.0),
            air_control=data.get("air_control", 0.75),
        )
        component.enabled = data.get("enabled", True)
        return component
