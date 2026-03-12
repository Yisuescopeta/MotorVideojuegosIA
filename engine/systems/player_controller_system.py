"""
engine/systems/player_controller_system.py - Gameplay basico para personaje 2D
"""

from engine.components.inputmap import InputMap
from engine.components.playercontroller2d import PlayerController2D
from engine.components.rigidbody import RigidBody
from engine.ecs.world import World


class PlayerControllerSystem:
    """Convierte InputMap en movimiento lateral y salto."""

    def update(self, world: World) -> None:
        for entity in world.get_entities_with(InputMap, RigidBody, PlayerController2D):
            input_map = entity.get_component(InputMap)
            rigidbody = entity.get_component(RigidBody)
            controller = entity.get_component(PlayerController2D)

            if input_map is None or rigidbody is None or controller is None:
                continue
            if not input_map.enabled or not rigidbody.enabled or not controller.enabled:
                continue

            horizontal = float(input_map.last_state.get("horizontal", 0.0))
            control = 1.0 if rigidbody.is_grounded else controller.air_control
            rigidbody.velocity_x = horizontal * controller.move_speed * control

            jump_pressed = float(input_map.last_state.get("action_1", 0.0)) > 0.5
            if jump_pressed and not controller._jump_was_pressed and rigidbody.is_grounded:
                rigidbody.velocity_y = controller.jump_velocity
                rigidbody.is_grounded = False

            controller._jump_was_pressed = jump_pressed
