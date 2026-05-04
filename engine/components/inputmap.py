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
        mouse_move_enabled: bool = False,
        mouse_action_1: str = "MOUSE_LEFT",
        mouse_action_2: str = "MOUSE_RIGHT",
        gamepad_move: str = "",
        gamepad_look: str = "",
        gamepad_action_1: str = "BUTTON_A",
        gamepad_action_2: str = "BUTTON_X",
        deadzone: float = 0.2,
    ) -> None:
        self.enabled: bool = True
        self.move_left: str = move_left
        self.move_right: str = move_right
        self.move_up: str = move_up
        self.move_down: str = move_down
        self.action_1: str = action_1
        self.action_2: str = action_2
        self.mouse_move_enabled: bool = mouse_move_enabled
        self.mouse_action_1: str = mouse_action_1
        self.mouse_action_2: str = mouse_action_2
        self.gamepad_move: str = gamepad_move
        self.gamepad_look: str = gamepad_look
        self.gamepad_action_1: str = gamepad_action_1
        self.gamepad_action_2: str = gamepad_action_2
        self.deadzone: float = deadzone
        self.midi_enabled: bool = False
        self.midi_action_map: dict = {}  # note_number -> action_name
        self.last_state: Dict[str, float] = {
            "horizontal": 0.0,
            "vertical": 0.0,
            "action_1": 0.0,
            "action_2": 0.0,
            "action_1_just_pressed": 0.0,
            "action_1_just_released": 0.0,
            "action_2_just_pressed": 0.0,
            "action_2_just_released": 0.0,
            "jump_just_pressed": 0.0,
            "jump_just_released": 0.0,
            "mouse_x": 0.0,
            "mouse_y": 0.0,
            "mouse_wheel": 0.0,
            "mouse_left_just_pressed": 0.0,
            "mouse_right_just_pressed": 0.0,
            "mouse_left_held": 0.0,
            "mouse_right_held": 0.0,
            "gamepad_left_x": 0.0,
            "gamepad_left_y": 0.0,
            "gamepad_right_x": 0.0,
            "gamepad_right_y": 0.0,
            "gamepad_a_just_pressed": 0.0,
            "gamepad_x_just_pressed": 0.0,
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
            "mouse_move_enabled": self.mouse_move_enabled,
            "mouse_action_1": self.mouse_action_1,
            "mouse_action_2": self.mouse_action_2,
            "gamepad_move": self.gamepad_move,
            "gamepad_look": self.gamepad_look,
            "gamepad_action_1": self.gamepad_action_1,
            "gamepad_action_2": self.gamepad_action_2,
            "deadzone": self.deadzone,
            "midi_enabled": self.midi_enabled,
            "midi_action_map": dict(self.midi_action_map),
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
            mouse_move_enabled=data.get("mouse_move_enabled", False),
            mouse_action_1=data.get("mouse_action_1", "MOUSE_LEFT"),
            mouse_action_2=data.get("mouse_action_2", "MOUSE_RIGHT"),
            gamepad_move=data.get("gamepad_move", ""),
            gamepad_look=data.get("gamepad_look", ""),
            gamepad_action_1=data.get("gamepad_action_1", "BUTTON_A"),
            gamepad_action_2=data.get("gamepad_action_2", "BUTTON_X"),
            deadzone=data.get("deadzone", 0.2),
        )
        component.enabled = data.get("enabled", True)
        component.midi_enabled = data.get("midi_enabled", False)
        component.midi_action_map = dict(data.get("midi_action_map", {}))
        return component

    def get_bindings(self) -> Dict[str, List[str]]:
        """Convierte los strings en listas de tokens de teclas/ratón/gamepad."""
        return {
            "move_left": [item.strip().upper() for item in self.move_left.split(",") if item.strip()],
            "move_right": [item.strip().upper() for item in self.move_right.split(",") if item.strip()],
            "move_up": [item.strip().upper() for item in self.move_up.split(",") if item.strip()],
            "move_down": [item.strip().upper() for item in self.move_down.split(",") if item.strip()],
            "action_1": [item.strip().upper() for item in self.action_1.split(",") if item.strip()],
            "action_2": [item.strip().upper() for item in self.action_2.split(",") if item.strip()],
            "mouse_action_1": [item.strip().upper() for item in self.mouse_action_1.split(",") if item.strip()],
            "mouse_action_2": [item.strip().upper() for item in self.mouse_action_2.split(",") if item.strip()],
            "gamepad_action_1": [item.strip().upper() for item in self.gamepad_action_1.split(",") if item.strip()],
            "gamepad_action_2": [item.strip().upper() for item in self.gamepad_action_2.split(",") if item.strip()],
        }
