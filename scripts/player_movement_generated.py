from __future__ import annotations


def on_play(context) -> None:
    context.public_data.setdefault("speed", 180.0)
    context.public_data.setdefault("jump_force", 320.0)
    context.public_data.setdefault("facing", 1)


def on_update(context, dt: float) -> None:
    rigidbody = context.get_component("RigidBody")
    input_map = context.get_component("InputMap")
    if rigidbody is None or input_map is None:
        return

    state = dict(getattr(input_map, "last_state", {}) or {})
    horizontal = float(state.get("horizontal", 0.0))
    jump_pressed = float(state.get("action_1", 0.0)) > 0.0

    speed = float(context.public_data.get("speed", 180.0))
    jump_force = float(context.public_data.get("jump_force", 320.0))
    rigidbody.velocity_x = horizontal * speed

    if horizontal > 0.0:
        context.public_data["facing"] = 1
    elif horizontal < 0.0:
        context.public_data["facing"] = -1

    if jump_pressed and bool(getattr(rigidbody, "is_grounded", False)):
        rigidbody.velocity_y = -abs(jump_force)
