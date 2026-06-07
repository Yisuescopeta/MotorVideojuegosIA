"""Enemy slime ScriptBehaviour — chases the player, dies in one hit."""

from __future__ import annotations

import math

# Module-level runtime state (not serialized — stays out of Scene/World)
_dying: dict[str, bool] = {}
INPUT_DEAD_ZONE: float = 0.1
DIRECTION_HYSTERESIS: float = 0.3


def _facing(dx: float, dy: float, last_facing: str) -> str:
    abs_h = abs(dx)
    abs_v = abs(dy)
    if abs_h < INPUT_DEAD_ZONE and abs_v < INPUT_DEAD_ZONE:
        return last_facing
    if abs_v > abs_h:
        raw = "up" if dy < 0.0 else "down"
    else:
        raw = "side"
    if last_facing == "up" and raw == "side" and abs_v + DIRECTION_HYSTERESIS > abs_h:
        return "up"
    if last_facing == "down" and raw == "side" and abs_v + DIRECTION_HYSTERESIS > abs_h:
        return "down"
    if last_facing == "side" and raw != "side" and abs_h + DIRECTION_HYSTERESIS > abs_v:
        return "side"
    return raw


def _play(animator, preferred: str, fallback: str | None = None) -> None:
    target = None
    if preferred in animator.animations:
        target = preferred
    elif fallback and fallback in animator.animations:
        target = fallback
    if target and animator.current_state != target:
        animator.play(target)


def on_play(context) -> None:
    """Reset runtime state on scene load/reload so previously-killed slimes revive."""
    _dying.clear()


def on_update(context, dt: float) -> None:
    public = context.public_data
    entity_name: str = context.entity_name

    # Defaults initialization
    public.setdefault("target_entity", "Player")
    public.setdefault("move_speed", 60.0)
    public.setdefault("hit_radius", 24.0)
    public.setdefault("last_facing", "down")

    transform = context.get_component("Transform")
    animator = context.get_component("Animator")
    if transform is None or animator is None:
        return

    speed = public["move_speed"]
    hit_radius = public["hit_radius"]
    last_facing = str(public.get("last_facing", "down"))

    # Dying state — wait for death animation to finish, then deactivate
    if _dying.get(entity_name, False):
        if getattr(animator, "is_finished", False):
            entity = context.get_entity()
            if entity is not None:
                entity.active = False
            _dying.pop(entity_name, None)
        return

    # Find target
    target = context.world.get_entity_by_name(public["target_entity"])
    if target is None or not target.active:
        _play(animator, f"idle_{last_facing}", "idle")
        return

    target_trans = target.get_component_by_name("Transform")
    if target_trans is None:
        _play(animator, f"idle_{last_facing}", "idle")
        return

    # Distance to target
    dx = target_trans.local_x - transform.local_x
    dy = target_trans.local_y - transform.local_y
    dist = math.sqrt(dx * dx + dy * dy)

    # Check if player is attacking and hitting us
    target_anim = target.get_component_by_name("Animator")
    if (
        target_anim is not None
        and getattr(target_anim, "current_state", "").startswith("attack_")
        and dist <= hit_radius
    ):
        animator.play("death")
        _dying[entity_name] = True
        return

    facing = _facing(dx, dy, last_facing)
    public["last_facing"] = facing

    # Move towards player
    if dist > 1.0:
        transform.local_x += (dx / dist) * speed * dt
        transform.local_y += (dy / dist) * speed * dt
        if facing == "side":
            animator.flip_x = dx < -INPUT_DEAD_ZONE
        else:
            animator.flip_x = False
        _play(animator, f"walk_{facing}", "move")
    else:
        animator.flip_x = False if facing != "side" else animator.flip_x
        _play(animator, f"idle_{facing}", "idle")
