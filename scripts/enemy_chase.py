"""
scripts/enemy_chase.py - Enemigo que persigue al jugador
"""

import math


def on_play(context) -> None:
    context.log_info("Enemy chase iniciado")


def on_update(context, dt: float) -> None:
    transform = context.get_component("Transform")
    rigidbody = context.get_component("RigidBody")
    if transform is None or rigidbody is None:
        return

    player = context.get_entity_by_name("Player")
    if player is None:
        return

    player_transform = player.get_component("Transform")
    if player_transform is None:
        return

    dx = player_transform.x - transform.x
    dy = player_transform.y - transform.y
    distance = math.sqrt(dx * dx + dy * dy)

    if distance < 10.0:
        return

    speed = 100.0
    vx = (dx / distance) * speed
    vy = (dy / distance) * speed

    current_vx = rigidbody.velocity_x
    current_vy = rigidbody.velocity_y

    rigidbody.velocity_x = vx
    rigidbody.velocity_y = vy
