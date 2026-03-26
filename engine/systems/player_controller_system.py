"""
engine/systems/player_controller_system.py - Gameplay basico para personaje 2D
"""

from engine.components.animator import Animator
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
            animator = entity.get_component(Animator)

            if input_map is None or rigidbody is None or controller is None:
                continue
            if not input_map.enabled or not rigidbody.enabled or not controller.enabled:
                continue

            horizontal = float(input_map.last_state.get("horizontal", 0.0))
            control = 1.0 if rigidbody.is_grounded else controller.air_control
            rigidbody.velocity_x = horizontal * controller.move_speed * control

            jump_pressed = float(input_map.last_state.get("action_1", 0.0)) > 0.5
            
            if jump_pressed and not controller._jump_was_pressed:
                can_jump = rigidbody.is_grounded or controller._jump_count < controller.max_jumps
                if can_jump:
                    rigidbody.velocity_y = controller.jump_velocity
                    rigidbody.is_grounded = False
                    controller._jump_count += 1

            if rigidbody.is_grounded:
                controller._jump_count = 0

            controller._jump_was_pressed = jump_pressed
            self._update_animator_facing(animator, horizontal)
            self._update_animator_state(animator, rigidbody, horizontal)

    def _update_animator_facing(self, animator: Animator | None, horizontal: float) -> None:
        if animator is None or not animator.enabled:
            return
        if horizontal < -0.05:
            animator.flip_x = True
        elif horizontal > 0.05:
            animator.flip_x = False

    def _update_animator_state(self, animator: Animator | None, rigidbody: RigidBody, horizontal: float) -> None:
        if animator is None or not animator.enabled or not animator.animations:
            return
        target_state = animator.current_state
        if not rigidbody.is_grounded:
            if "jump" in animator.animations:
                target_state = "jump"
        elif abs(horizontal) > 0.05 or abs(rigidbody.velocity_x) > 1.0:
            if "run" in animator.animations:
                target_state = "run"
            elif "walk" in animator.animations:
                target_state = "walk"
        else:
            if "idle" in animator.animations:
                target_state = "idle"

        if target_state != animator.current_state:
            animator.play(target_state)
