"""
scripts/platformer_character.py - Script demo para personaje jugable
"""


def on_play(context) -> None:
    context.public_data["play_count"] = int(context.public_data.get("play_count", 0)) + 1
    context.public_data.setdefault("max_x", 0.0)
    context.public_data.setdefault("jump_count", 0)
    context.public_data["last_hook"] = "on_play"
    context.log_info("ScriptBehaviour activo")


def on_update(context, dt: float) -> None:
    transform = context.get_component("Transform")
    rigidbody = context.get_component("RigidBody")
    if transform is None:
        return

    current_max = float(context.public_data.get("max_x", transform.x))
    context.public_data["max_x"] = max(current_max, float(transform.x))

    was_airborne = bool(context.public_data.get("was_airborne", False))
    is_airborne = rigidbody is not None and float(rigidbody.velocity_y) < -0.1
    if is_airborne and not was_airborne:
        context.public_data["jump_count"] = int(context.public_data.get("jump_count", 0)) + 1

    context.public_data["was_airborne"] = bool(is_airborne)
    context.public_data["last_dt"] = round(float(dt), 4)
    context.public_data["last_hook"] = "on_update"


def on_stop(context) -> None:
    context.public_data["last_hook"] = "on_stop"
    context.log_info(
        f"Resumen play_count={context.public_data.get('play_count', 0)} "
        f"jump_count={context.public_data.get('jump_count', 0)} "
        f"max_x={context.public_data.get('max_x', 0.0)}"
    )
