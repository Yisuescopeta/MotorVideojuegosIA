"""
tests/test_input_system.py - Tests para el sistema de input con mock de pyray
"""
import unittest
from unittest.mock import MagicMock, patch

import pyray as rl
from engine.components.inputmap import InputMap
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.systems.input_system import InputSystem


class TestInputSystemEdgeDetection(unittest.TestCase):
    """Tests for just_pressed/just_released edge detection."""

    def setUp(self) -> None:
        self.input_system = InputSystem()
        world = World()
        self.entity = Entity("Player")
        self.entity.add_component(InputMap(
            action_1="SPACE",
            action_2="ENTER",
        ))
        world.add_entity(self.entity)
        self._world = world
        self._entity_name = "Player"

    def _patch_is_key_down(self, return_values: dict) -> MagicMock:
        """Helper to mock is_key_down with custom return values."""
        original = rl.is_key_down

        def mock_fn(key_code):
            return return_values.get(key_code, False)

        patcher = patch.object(rl, 'is_key_down', side_effect=mock_fn)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def _mock_all_inputs_inactive(self) -> None:
        """Mock all input functions to return inactive/false."""
        patchers = [
            patch.object(rl, 'is_key_down', return_value=False),
            patch.object(rl, 'is_mouse_button_down', return_value=False),
            patch.object(rl, 'is_mouse_button_pressed', return_value=False),
            patch.object(rl, 'is_gamepad_available', return_value=False),
            patch.object(rl, 'get_mouse_position', return_value=rl.Vector2(0.0, 0.0)),
            patch.object(rl, 'get_mouse_wheel_move', return_value=0.0),
            patch.object(rl, 'get_gamepad_axis_movement', return_value=0.0),
            patch.object(rl, 'is_gamepad_button_pressed', return_value=False),
            patch.object(rl, 'is_gamepad_button_down', return_value=False),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def _get_last_state(self) -> dict:
        return dict(self.entity.get_component(InputMap).last_state)

    def test_just_pressed_detected_on_first_frame(self) -> None:
        """Action_1 just_pressed debe ser 1.0 cuando la tecla se presiona por primera vez."""
        self._mock_all_inputs_inactive()

        # Frame 1: no key down → nothing
        self.input_system.update(self._world)
        state = self._get_last_state()
        self.assertEqual(state['action_1_just_pressed'], 0.0)
        self.assertEqual(state['action_1'], 0.0)

        # Frame 2: key pressed → just_pressed must be 1.0
        with patch.object(rl, 'is_key_down', side_effect=lambda k: k == rl.KEY_SPACE):
            self.input_system.update(self._world)

        state = self._get_last_state()
        self.assertEqual(state['action_1'], 1.0)
        self.assertEqual(state['action_1_just_pressed'], 1.0)
        self.assertEqual(state['action_1_just_released'], 0.0)

    def test_just_pressed_only_on_second_frame(self) -> None:
        """just_pressed debe ser 1.0 solo en el primer frame de presión, no en frames posteriores."""
        # Frame 1: SPACE held
        with patch.object(rl, 'is_key_down', side_effect=lambda k: k == rl.KEY_SPACE):
            self.input_system.update(self._world)

        state = self._get_last_state()
        self.assertEqual(state['action_1_just_pressed'], 1.0)

        # Frame 2: SPACE still held → just_pressed should be 0.0
        with patch.object(rl, 'is_key_down', side_effect=lambda k: k == rl.KEY_SPACE):
            self.input_system.update(self._world)

        state = self._get_last_state()
        self.assertEqual(state['action_1'], 1.0)
        self.assertEqual(state['action_1_just_pressed'], 0.0)
        self.assertEqual(state['action_1_just_released'], 0.0)

    def test_just_released_on_release(self) -> None:
        """just_released debe ser 1.0 en el frame en que se suelta la tecla."""
        # Frame 1: SPACE held
        with patch.object(rl, 'is_key_down', side_effect=lambda k: k == rl.KEY_SPACE):
            self.input_system.update(self._world)

        # Frame 2: SPACE held (continue)
        with patch.object(rl, 'is_key_down', side_effect=lambda k: k == rl.KEY_SPACE):
            self.input_system.update(self._world)

        state = self._get_last_state()
        self.assertEqual(state['action_1_just_pressed'], 0.0)

        # Frame 3: SPACE released
        self._mock_all_inputs_inactive()
        self.input_system.update(self._world)

        state = self._get_last_state()
        self.assertEqual(state['action_1'], 0.0)
        self.assertEqual(state['action_1_just_pressed'], 0.0)
        self.assertEqual(state['action_1_just_released'], 1.0)

    def test_deadzone_filters_small_values(self) -> None:
        """Valores por debajo del deadzone deben redondearse a 0."""
        self._mock_all_inputs_inactive()

        result = self.input_system._apply_deadzone(0.1, 0.2)
        self.assertEqual(result, 0.0)

        result = self.input_system._apply_deadzone(-0.15, 0.2)
        self.assertEqual(result, 0.0)

        result = self.input_system._apply_deadzone(0.3, 0.2)
        self.assertGreater(result, 0.0)
        self.assertLess(result, 1.0)

    def test_inject_state_backward_compat(self) -> None:
        """inject_state debe seguir funcionando con el contrato antiguo (horizontal, action_1, etc.)."""
        self._mock_all_inputs_inactive()

        self.input_system.inject_state(
            self._entity_name,
            {"horizontal": 1.0, "vertical": -1.0, "action_1": 0.5, "action_2": 1.0},
            frames=2,
        )

        # Frame 1 of override
        self.input_system.update(self._world)
        state = self._get_last_state()
        self.assertEqual(state['horizontal'], 1.0)
        self.assertEqual(state['vertical'], -1.0)
        self.assertEqual(state['action_1'], 0.5)

        # Frame 2 of override
        self.input_system.update(self._world)
        state = self._get_last_state()
        self.assertEqual(state['horizontal'], 1.0)
        self.assertEqual(state['action_2'], 1.0)

        # Frame 3: override expired, real input (all inactive)
        self.input_system.update(self._world)
        state = self._get_last_state()
        self.assertEqual(state['horizontal'], 0.0)
        self.assertEqual(state['action_1'], 0.0)

    def test_get_vector_returns_correct_direction(self) -> None:
        """get_vector debe devolver (horizontal, vertical) para una entidad tras procesar input."""
        self._mock_all_inputs_inactive()

        # Simulate pressing RIGHT and DOWN
        with patch.object(rl, 'is_key_down', side_effect=lambda k: k in (rl.KEY_RIGHT, rl.KEY_DOWN)):
            self.input_system.update(self._world)

        h, v = self.input_system.get_vector(self._entity_name)
        self.assertGreater(h, 0.0)
        self.assertGreater(v, 0.0)

    def test_multiple_actions_edge_detection_independent(self) -> None:
        """action_1 y action_2 deben tener detección de bordes independiente."""
        self._mock_all_inputs_inactive()

        # Press action_1 only
        with patch.object(rl, 'is_key_down', side_effect=lambda k: k == rl.KEY_SPACE):
            self.input_system.update(self._world)

        state = self._get_last_state()
        self.assertEqual(state['action_1_just_pressed'], 1.0)
        self.assertEqual(state['action_2_just_pressed'], 0.0)
        self.assertEqual(state['action_2'], 0.0)

        # Hold action_1, press action_2
        with patch.object(rl, 'is_key_down', side_effect=lambda k: k in (rl.KEY_SPACE, rl.KEY_ENTER)):
            self.input_system.update(self._world)

        state = self._get_last_state()
        self.assertEqual(state['action_1_just_pressed'], 0.0)
        self.assertEqual(state['action_2_just_pressed'], 1.0)

        # Release only action_1
        with patch.object(rl, 'is_key_down', side_effect=lambda k: k == rl.KEY_ENTER):
            self.input_system.update(self._world)

        state = self._get_last_state()
        self.assertEqual(state['action_1_just_released'], 1.0)
        self.assertEqual(state['action_2_just_released'], 0.0)

    def test_mouse_left_just_pressed_uses_is_mouse_button_pressed(self) -> None:
        """mouse_left_just_pressed debe llamar a is_mouse_button_pressed (no is_mouse_button_down)."""
        self._mock_all_inputs_inactive()

        with patch.object(rl, 'is_mouse_button_pressed', return_value=True):
            self.input_system.update(self._world)

        state = self._get_last_state()
        self.assertEqual(state['mouse_left_just_pressed'], 1.0)

    def test_action_strength_combines_keyboard_mouse_gamepad(self) -> None:
        """_action_strength debe devolver 1.0 si cualquiera de teclado/ratón/gamepad está activo."""
        self._mock_all_inputs_inactive()

        # Keyboard only
        result = self.input_system._action_strength(["SPACE"], [], [])
        with patch.object(rl, 'is_key_down', side_effect=lambda k: k == rl.KEY_SPACE):
            result = self.input_system._action_strength(["SPACE"], [], [])
        self.assertEqual(result, 1.0)

        # Nothing pressed
        self._mock_all_inputs_inactive()
        result = self.input_system._action_strength(["SPACE"], [], [])
        self.assertEqual(result, 0.0)

    def test_disabled_input_map_skipped(self) -> None:
        """InputMap desactivado no debe procesarse."""
        self._mock_all_inputs_inactive()

        input_map = self.entity.get_component(InputMap)
        input_map.enabled = False

        with patch.object(rl, 'is_key_down', side_effect=lambda k: k == rl.KEY_SPACE):
            self.input_system.update(self._world)

        state = self._get_last_state()
        self.assertEqual(state['action_1'], 0.0)

    def test_axis_deadzone_scaling(self) -> None:
        """_axis debe aplicar deadzone correctamente: si ambos lados presionados, debe ser 0."""
        self._mock_all_inputs_inactive()

        with patch.object(rl, 'is_key_down', side_effect=lambda k: k in (rl.KEY_LEFT, rl.KEY_RIGHT)):
            result = self.input_system._axis(["LEFT"], ["RIGHT"], deadzone=0.2)

        self.assertEqual(result, 0.0)


if __name__ == "__main__":
    unittest.main()
