"""
engine/components/inputmap.py - Mapa declarativo de acciones de entrada
"""

from typing import Any, Dict, List

from engine.ecs.component import Component


class InputMap(Component):
    """Bindings simples en texto para mantener el sistema entendible por IA."""

    def __init__(
        self,
        move_left: str = "A,LEFT",
        move_right: str = "D,RIGHT",
        move_up: str = "W,UP",
        move_down: str = "S,DOWN",
        action_1: str = "SPACE",
        action_2: str = "ENTER",
    ) -> None:
        self.enabled: bool = True
        self.move_left: str = move_left
        self.move_right: str = move_right
        self.move_up: str = move_up
        self.move_down: str = move_down
        self.action_1: str = action_1
        self.action_2: str = action_2
        self.last_state: Dict[str, float] = {
            "horizontal": 0.0,
            "vertical": 0.0,
            "action_1": 0.0,
            "action_2": 0.0,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "move_left": self.move_left,
            "move_right": self.move_right,
            "move_up": self.move_up,
            "move_down": self.move_down,
            "action_1": self.action_1,
            "action_2": self.action_2,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InputMap":
        component = cls(
            move_left=data.get("move_left", "A,LEFT"),
            move_right=data.get("move_right", "D,RIGHT"),
            move_up=data.get("move_up", "W,UP"),
            move_down=data.get("move_down", "S,DOWN"),
            action_1=data.get("action_1", "SPACE"),
            action_2=data.get("action_2", "ENTER"),
        )
        component.enabled = data.get("enabled", True)
        return component

    def get_bindings(self) -> Dict[str, List[str]]:
        """Convierte los strings en listas de tokens de teclas."""
        return {
            "move_left": [item.strip().upper() for item in self.move_left.split(",") if item.strip()],
            "move_right": [item.strip().upper() for item in self.move_right.split(",") if item.strip()],
            "move_up": [item.strip().upper() for item in self.move_up.split(",") if item.strip()],
            "move_down": [item.strip().upper() for item in self.move_down.split(",") if item.strip()],
            "action_1": [item.strip().upper() for item in self.action_1.split(",") if item.strip()],
            "action_2": [item.strip().upper() for item in self.action_2.split(",") if item.strip()],
        }
