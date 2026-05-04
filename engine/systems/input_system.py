"""
engine/systems/input_system.py - Lectura declarativa de InputMap con soporte
para teclado, ratón y gamepad + detección de bordes just_pressed/just_released.
"""

from typing import Dict, List, Optional, Tuple

import pyray as rl
from engine.components.inputmap import InputMap
from engine.ecs.world import World

KEY_LOOKUP: Dict[str, int] = {
    "A": rl.KEY_A,
    "B": rl.KEY_B,
    "C": rl.KEY_C,
    "D": rl.KEY_D,
    "E": rl.KEY_E,
    "F": rl.KEY_F,
    "G": rl.KEY_G,
    "H": rl.KEY_H,
    "I": rl.KEY_I,
    "J": rl.KEY_J,
    "K": rl.KEY_K,
    "L": rl.KEY_L,
    "M": rl.KEY_M,
    "N": rl.KEY_N,
    "O": rl.KEY_O,
    "P": rl.KEY_P,
    "Q": rl.KEY_Q,
    "R": rl.KEY_R,
    "S": rl.KEY_S,
    "T": rl.KEY_T,
    "U": rl.KEY_U,
    "V": rl.KEY_V,
    "W": rl.KEY_W,
    "X": rl.KEY_X,
    "Y": rl.KEY_Y,
    "Z": rl.KEY_Z,
    "LEFT": rl.KEY_LEFT,
    "RIGHT": rl.KEY_RIGHT,
    "UP": rl.KEY_UP,
    "DOWN": rl.KEY_DOWN,
    "SPACE": rl.KEY_SPACE,
    "ENTER": rl.KEY_ENTER,
    "ESCAPE": rl.KEY_ESCAPE,
    "TAB": rl.KEY_TAB,
    "BACKSPACE": rl.KEY_BACKSPACE,
    "LEFT_SHIFT": rl.KEY_LEFT_SHIFT,
    "RIGHT_SHIFT": rl.KEY_RIGHT_SHIFT,
    "LEFT_CONTROL": rl.KEY_LEFT_CONTROL,
    "RIGHT_CONTROL": rl.KEY_RIGHT_CONTROL,
    "LEFT_ALT": rl.KEY_LEFT_ALT,
    "RIGHT_ALT": rl.KEY_RIGHT_ALT,
}

MOUSE_BUTTON_LOOKUP: Dict[str, int] = {
    "MOUSE_LEFT": rl.MOUSE_BUTTON_LEFT,
    "MOUSE_RIGHT": rl.MOUSE_BUTTON_RIGHT,
    "MOUSE_MIDDLE": rl.MOUSE_BUTTON_MIDDLE,
}

GAMEPAD_AXIS_LOOKUP: Dict[str, int] = {
    "LEFT_X": rl.GAMEPAD_AXIS_LEFT_X,
    "LEFT_Y": rl.GAMEPAD_AXIS_LEFT_Y,
    "RIGHT_X": rl.GAMEPAD_AXIS_RIGHT_X,
    "RIGHT_Y": rl.GAMEPAD_AXIS_RIGHT_Y,
    "LEFT_TRIGGER": rl.GAMEPAD_AXIS_LEFT_TRIGGER,
    "RIGHT_TRIGGER": rl.GAMEPAD_AXIS_RIGHT_TRIGGER,
}

GAMEPAD_BUTTON_LOOKUP: Dict[str, int] = {
    "BUTTON_A": rl.GAMEPAD_BUTTON_RIGHT_FACE_DOWN,
    "BUTTON_B": rl.GAMEPAD_BUTTON_RIGHT_FACE_RIGHT,
    "BUTTON_X": rl.GAMEPAD_BUTTON_RIGHT_FACE_LEFT,
    "BUTTON_Y": rl.GAMEPAD_BUTTON_RIGHT_FACE_UP,
    "LEFT_SHOULDER": rl.GAMEPAD_BUTTON_LEFT_TRIGGER_1,
    "RIGHT_SHOULDER": rl.GAMEPAD_BUTTON_RIGHT_TRIGGER_1,
}


class InputSystem:
    """Actualiza estados de acciones a partir de un InputMap serializable,
    con soporte para teclado, ratón y gamepad."""

    def __init__(self) -> None:
        self._overrides: Dict[str, Tuple[Dict[str, float], int]] = {}
        self._prev_states: Dict[str, Dict[str, float]] = {}

    def inject_state(self, entity_name: str, state: Dict[str, float], frames: int = 1) -> None:
        """Inyecta input para automatización visual o pruebas."""
        self._overrides[entity_name] = (dict(state), max(1, frames))
        self._prev_states[entity_name] = {
            'action_1_held': state.get('action_1', 0.0),
            'action_2_held': state.get('action_2', 0.0),
        }

    def get_vector(self, entity_name: str) -> Tuple[float, float]:
        """Obtiene el vector horizontal/vertical actual de una entidad
        (estilo Godot Input.get_vector).
        """
        prev = self._prev_states.get(entity_name, {})
        return (prev.get("horizontal", 0.0), prev.get("vertical", 0.0))

    def update(self, world: World) -> None:
        for entity in world.get_entities_with(InputMap):
            input_map = entity.get_component(InputMap)
            if input_map is None or not input_map.enabled:
                continue

            entity_name = entity.name

            # Check overrides first
            if entity_name in self._overrides:
                state, frames = self._overrides[entity_name]
                input_map.last_state = dict(state)
                self._prev_states[entity_name] = {
                    'action_1_held': state.get('action_1', 0.0),
                    'action_2_held': state.get('action_2', 0.0),
                    'horizontal': state.get('horizontal', 0.0),
                    'vertical': state.get('vertical', 0.0),
                }
                if frames <= 1:
                    del self._overrides[entity_name]
                else:
                    self._overrides[entity_name] = (state, frames - 1)
                continue

            deadzone = getattr(input_map, 'deadzone', 0.2)
            bindings = input_map.get_bindings()

            # Axes
            neg_x = bindings.get('move_left', [])
            pos_x = bindings.get('move_right', [])
            neg_y = bindings.get('move_up', [])
            pos_y = bindings.get('move_down', [])

            horizontal = self._axis(neg_x, pos_x, deadzone)
            vertical = self._axis(neg_y, pos_y, deadzone)

            # Action strengths
            act1_keys = bindings.get('action_1', [])
            act2_keys = bindings.get('action_2', [])
            mouse1 = bindings.get('mouse_action_1', [])
            mouse2 = bindings.get('mouse_action_2', [])
            gp1 = bindings.get('gamepad_action_1', [])
            gp2 = bindings.get('gamepad_action_2', [])

            action_1 = self._action_strength(act1_keys, mouse1, gp1)
            action_2 = self._action_strength(act2_keys, mouse2, gp2)

            # Edge detection
            current_held = {
                'action_1_held': action_1,
                'action_2_held': action_2,
            }
            edges = self._compute_edge_state(entity_name, current_held)

            # Mouse
            mouse_x, mouse_y = 0.0, 0.0
            mouse_wheel = 0.0
            mouse_left_held, mouse_right_held = 0.0, 0.0
            try:
                mpos = rl.get_mouse_position()
                mouse_x, mouse_y = float(mpos.x), float(mpos.y)
                mouse_wheel = float(rl.get_mouse_wheel_move())
                if rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
                    mouse_left_held = 1.0
                if rl.is_mouse_button_down(rl.MOUSE_BUTTON_RIGHT):
                    mouse_right_held = 1.0
            except Exception:
                pass

            # Gamepad
            gpad_lx, gpad_ly, gpad_rx, gpad_ry = 0.0, 0.0, 0.0, 0.0
            try:
                if rl.is_gamepad_available(0):
                    gpad_lx = rl.get_gamepad_axis_movement(0, rl.GAMEPAD_AXIS_LEFT_X)
                    gpad_ly = rl.get_gamepad_axis_movement(0, rl.GAMEPAD_AXIS_LEFT_Y)
                    gpad_rx = rl.get_gamepad_axis_movement(0, rl.GAMEPAD_AXIS_RIGHT_X)
                    gpad_ry = rl.get_gamepad_axis_movement(0, rl.GAMEPAD_AXIS_RIGHT_Y)
                    if abs(gpad_lx) > deadzone:
                        horizontal = gpad_lx
                    if abs(gpad_ly) > deadzone:
                        vertical = gpad_ly
            except Exception:
                pass

            # Build last_state
            input_map.last_state = {
                'horizontal': horizontal,
                'vertical': vertical,
                'action_1': action_1,
                'action_2': action_2,
                'action_1_just_pressed': edges.get('action_1_just_pressed', 0.0),
                'action_1_just_released': edges.get('action_1_just_released', 0.0),
                'action_2_just_pressed': edges.get('action_2_just_pressed', 0.0),
                'action_2_just_released': edges.get('action_2_just_released', 0.0),
                'jump_just_pressed': edges.get('action_1_just_pressed', 0.0),
                'jump_just_released': edges.get('action_1_just_released', 0.0),
                'mouse_x': mouse_x,
                'mouse_y': mouse_y,
                'mouse_wheel': mouse_wheel,
                'mouse_left_just_pressed': self._mouse_just_pressed(['MOUSE_LEFT']),
                'mouse_right_just_pressed': self._mouse_just_pressed(['MOUSE_RIGHT']),
                'mouse_left_held': mouse_left_held,
                'mouse_right_held': mouse_right_held,
                'gamepad_left_x': gpad_lx,
                'gamepad_left_y': gpad_ly,
                'gamepad_right_x': gpad_rx,
                'gamepad_right_y': gpad_ry,
                'gamepad_a_just_pressed': self._gamepad_button_just_pressed(['BUTTON_A']),
                'gamepad_x_just_pressed': self._gamepad_button_just_pressed(['BUTTON_X']),
            }

            # Store prev states for next frame edge detection
            self._prev_states[entity_name] = {
                'action_1_held': action_1,
                'action_2_held': action_2,
                'horizontal': horizontal,
                'vertical': vertical,
            }

    def _axis(self, negative_keys: List[str], positive_keys: List[str], deadzone: float = 0.2) -> float:
        negative = 1.0 if self._held(negative_keys) else 0.0
        positive = 1.0 if self._held(positive_keys) else 0.0
        raw = positive - negative
        return self._apply_deadzone(raw, deadzone)

    def _action_strength(self, key_bindings: List[str], mouse_bindings: List[str], gamepad_bindings: List[str]) -> float:
        if self._held(key_bindings):
            return 1.0
        if self._mouse_held(mouse_bindings) > 0.0:
            return 1.0
        if self._gamepad_button_held(gamepad_bindings) > 0.0:
            return 1.0
        return 0.0

    def _held(self, keys: List[str]) -> bool:
        for key_name in keys:
            key_code = KEY_LOOKUP.get(key_name)
            if key_code is not None and rl.is_key_down(key_code):
                return True
        return False

    def _mouse_held(self, buttons: List[str]) -> float:
        for token in buttons:
            btn_code = MOUSE_BUTTON_LOOKUP.get(token)
            if btn_code is not None and rl.is_mouse_button_down(btn_code):
                return 1.0
        return 0.0

    def _mouse_just_pressed(self, buttons: List[str]) -> float:
        for token in buttons:
            btn_code = MOUSE_BUTTON_LOOKUP.get(token)
            if btn_code is not None and rl.is_mouse_button_pressed(btn_code):
                return 1.0
        return 0.0

    def _gamepad_button_held(self, buttons: List[str]) -> float:
        try:
            if rl.is_gamepad_available(0):
                for token in buttons:
                    btn_code = GAMEPAD_BUTTON_LOOKUP.get(token)
                    if btn_code is not None and rl.is_gamepad_button_down(0, btn_code):
                        return 1.0
        except Exception:
            pass
        return 0.0

    def _gamepad_button_just_pressed(self, buttons: List[str]) -> float:
        try:
            if rl.is_gamepad_available(0):
                for token in buttons:
                    btn_code = GAMEPAD_BUTTON_LOOKUP.get(token)
                    if btn_code is not None and rl.is_gamepad_button_pressed(0, btn_code):
                        return 1.0
        except Exception:
            pass
        return 0.0

    def _apply_deadzone(self, value: float, deadzone: float) -> float:
        if deadzone >= 1.0:
            return 0.0
        abs_val = abs(value)
        if abs_val <= deadzone:
            return 0.0
        sign = 1.0 if value > 0.0 else -1.0
        return sign * (abs_val - deadzone) / (1.0 - deadzone)

    def _compute_edge_state(self, entity_name: str, current_held: Dict[str, float]) -> Dict[str, float]:
        prev = self._prev_states.get(entity_name, {})
        edges: Dict[str, float] = {}

        for action_key, held_key in [("action_1", "action_1_held"), ("action_2", "action_2_held")]:
            was_held = prev.get(held_key, 0.0) > 0.5
            is_held = current_held.get(held_key, 0.0) > 0.5

            if is_held and not was_held:
                edges[f'{action_key}_just_pressed'] = 1.0
                edges[f'{action_key}_just_released'] = 0.0
            elif not is_held and was_held:
                edges[f'{action_key}_just_pressed'] = 0.0
                edges[f'{action_key}_just_released'] = 1.0
            else:
                edges[f'{action_key}_just_pressed'] = 0.0
                edges[f'{action_key}_just_released'] = 0.0

        return edges
