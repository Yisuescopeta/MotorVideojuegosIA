"""
scripts/main_menu_controller.py - Controlador de menu principal.
"""

import pyray as rl


def _point_inside_button(context) -> bool:
    button = context.world.get_entity_by_name("PlayButton")
    if button is None:
        return False

    transform = None
    collider = None
    for component in button.get_all_components():
        component_name = type(component).__name__
        if component_name == "Transform":
            transform = component
        elif component_name == "Collider":
            collider = component

    if transform is None or collider is None:
        return False

    mouse = rl.get_mouse_position()
    left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
    return left <= mouse.x <= right and top <= mouse.y <= bottom


def _request_transition(context) -> None:
    context.public_data["transition_requested"] = True
    if context.load_scene_flow_target("next_scene"):
        context.log_info("Cargando platformer_test_scene...")
    else:
        context.public_data["transition_requested"] = False
        context.log_error("No se pudo cargar scene_flow.next_scene")


def on_play(context) -> None:
    context.public_data.setdefault("action_1_was_pressed", False)
    context.public_data.setdefault("action_2_was_pressed", False)
    context.public_data.setdefault("transition_requested", False)
    context.public_data.setdefault("mouse_was_pressed", False)
    context.log_info("Menu listo. Pulsa SPACE/ENTER o haz clic en PlayButton para iniciar.")


def on_update(context, dt: float) -> None:
    input_map = context.get_component("InputMap")
    if input_map is None:
        return

    action_1 = float(input_map.last_state.get("action_1", 0.0))
    action_2 = float(input_map.last_state.get("action_2", 0.0))
    is_action_1_pressed = action_1 > 0.5
    is_pressed = action_2 > 0.5
    was_action_1_pressed = bool(context.public_data.get("action_1_was_pressed", False))
    was_pressed = bool(context.public_data.get("action_2_was_pressed", False))
    mouse_pressed = rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)
    was_mouse_pressed = bool(context.public_data.get("mouse_was_pressed", False))
    clicked_button = mouse_pressed and not was_mouse_pressed and _point_inside_button(context)

    if not bool(context.public_data.get("transition_requested", False)):
        if (is_action_1_pressed and not was_action_1_pressed) or (is_pressed and not was_pressed) or clicked_button:
            _request_transition(context)

    context.public_data["action_1_was_pressed"] = is_action_1_pressed
    context.public_data["action_2_was_pressed"] = is_pressed
    context.public_data["mouse_was_pressed"] = mouse_pressed


def on_stop(context) -> None:
    context.public_data["action_1_was_pressed"] = False
    context.public_data["action_2_was_pressed"] = False
    context.public_data["mouse_was_pressed"] = False
