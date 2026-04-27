"""
engine/systems/input_system.py - Lectura declarativa de InputMap
"""

from typing import Dict, Tuple

import pyray as rl
from engine.components.inputmap import InputMap
from engine.ecs.world import World

KEY_LOOKUP: Dict[str, int] = {
    "A": rl.KEY_A,
    "D": rl.KEY_D,
    "W": rl.KEY_W,
    "S": rl.KEY_S,
    "LEFT": rl.KEY_LEFT,
    "RIGHT": rl.KEY_RIGHT,
    "UP": rl.KEY_UP,
    "DOWN": rl.KEY_DOWN,
    "SPACE": rl.KEY_SPACE,
    "ENTER": rl.KEY_ENTER,
}


class InputSystem:
    """Actualiza estados de acciones a partir de un InputMap serializable."""

    def __init__(self) -> None:
        self._overrides: Dict[str, Tuple[Dict[str, float], int]] = {}

    def inject_state(self, entity_name: str, state: Dict[str, float], frames: int = 1) -> None:
        """Inyecta input para automatizacion visual o pruebas."""
        self._overrides[entity_name] = (dict(state), max(1, frames))

    def update(self, world: World) -> None:
        for entity in world.get_entities_with(InputMap):
            input_map = entity.get_component(InputMap)
            if input_map is None or not input_map.enabled:
                continue

            override = self._overrides.get(entity.name)
            if override is not None:
                state, frames = override
                input_map.last_state = dict(state)
                if frames <= 1:
                    del self._overrides[entity.name]
                else:
                    self._overrides[entity.name] = (state, frames - 1)
                continue

            bindings = input_map.get_bindings()
            horizontal = self._axis(bindings["move_left"], bindings["move_right"])
            vertical = self._axis(bindings["move_down"], bindings["move_up"])
            input_map.last_state = {
                "horizontal": horizontal,
                "vertical": vertical,
                "action_1": 1.0 if self._pressed(bindings["action_1"]) else 0.0,
                "action_2": 1.0 if self._pressed(bindings["action_2"]) else 0.0,
            }

    def _axis(self, negative_keys: list[str], positive_keys: list[str]) -> float:
        negative = 1.0 if self._pressed(negative_keys) else 0.0
        positive = 1.0 if self._pressed(positive_keys) else 0.0
        return positive - negative

    def _pressed(self, keys: list[str]) -> bool:
        for key_name in keys:
            key_code = KEY_LOOKUP.get(key_name)
            if key_code is not None and rl.is_key_down(key_code):
                return True
        return False
