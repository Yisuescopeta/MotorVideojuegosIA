"""Player controller with attack, lives, contact damage, and HUD hearts."""

from __future__ import annotations

import math

MOVE_SPEED: float = 120.0
INPUT_DEAD_ZONE: float = 0.1
DIRECTION_HYSTERESIS: float = 0.3
DEFAULT_LIVES: int = 3
INVULNERABLE_DURATION: float = 3.0
BLINK_INTERVAL: float = 0.12
HEART_ENTITY_NAMES: tuple[str, ...] = ("Heart_1", "Heart_2", "Heart_3")


def _facing(horizontal: float, vertical: float, last_facing: str) -> str:
    abs_h = abs(horizontal)
    abs_v = abs(vertical)
    if abs_h < INPUT_DEAD_ZONE and abs_v < INPUT_DEAD_ZONE:
        return last_facing
    if abs_v > abs_h:
        raw = "up" if vertical > 0 else "down"
    else:
        raw = "side"
    if last_facing == "up" and raw == "side" and abs_v + DIRECTION_HYSTERESIS > abs_h:
        return "up"
    if last_facing == "down" and raw == "side" and abs_v + DIRECTION_HYSTERESIS > abs_h:
        return "down"
    if last_facing == "side" and raw != "side" and abs_h + DIRECTION_HYSTERESIS > abs_v:
        return "side"
    return raw


def _set_defaults(public: dict) -> None:
    public.setdefault("move_speed", MOVE_SPEED)
    public.setdefault("last_facing", "down")
    public.setdefault("attack_was_down", False)
    public.setdefault("action_2_was_down", False)
    public.setdefault("max_lives", DEFAULT_LIVES)
    public.setdefault("lives", public["max_lives"])
    public.setdefault("invulnerable_duration", INVULNERABLE_DURATION)
    public.setdefault("invulnerable_time_remaining", 0.0)
    public.setdefault("blink_interval", BLINK_INTERVAL)
    public.setdefault("blink_timer", 0.0)
    public.setdefault("blink_visible", True)
    public.setdefault("contacting_enemies", [])


def _set_player_visible(context, visible: bool) -> None:
    entity = context.get_entity()
    if entity is None:
        return
    sprite = entity.get_component_by_name("Sprite")
    animator = entity.get_component_by_name("Animator")
    if sprite is not None:
        sprite.enabled = bool(visible)
    if animator is not None:
        animator.enabled = bool(visible)


def _sync_hearts(context, lives: int) -> None:
    for index, entity_name in enumerate(HEART_ENTITY_NAMES, start=1):
        heart = context.get_entity_by_name(entity_name)
        if heart is None:
            continue
        image = heart.get_component_by_name("UIImage")
        if image is not None:
            image.enabled = lives >= index


def _aabb_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def _current_enemy_contacts(context, transform, collider) -> set[str]:
    overlaps: set[str] = set()
    player_bounds = collider.get_bounds(transform.x, transform.y)
    entity_name = context.entity_name
    for other in context.world.get_entities_with(type(transform), type(collider)):
        if other.name == entity_name or not other.active:
            continue
        if str(other.tag or "").strip().lower() != "enemy":
            continue
        other_transform = other.get_component_by_name("Transform")
        other_collider = other.get_component_by_name("Collider")
        if other_transform is None or other_collider is None or not other_collider.enabled:
            continue
        if _aabb_overlap(player_bounds, other_collider.get_bounds(other_transform.x, other_transform.y)):
            overlaps.add(other.name)
    return overlaps


def _update_invulnerability(context, public: dict, dt: float) -> bool:
    remaining = float(public.get("invulnerable_time_remaining", 0.0))
    if remaining <= 0.0:
        if not bool(public.get("blink_visible", True)):
            public["blink_visible"] = True
            _set_player_visible(context, True)
        public["blink_timer"] = 0.0
        public["invulnerable_time_remaining"] = 0.0
        return False

    remaining = max(0.0, remaining - dt)
    public["invulnerable_time_remaining"] = remaining

    blink_timer = float(public.get("blink_timer", 0.0)) + dt
    blink_interval = max(0.05, float(public.get("blink_interval", BLINK_INTERVAL)))
    visible = bool(public.get("blink_visible", True))
    while blink_timer >= blink_interval:
        blink_timer -= blink_interval
        visible = not visible
    public["blink_timer"] = blink_timer
    public["blink_visible"] = visible
    _set_player_visible(context, visible)

    if remaining <= 0.0:
        public["blink_visible"] = True
        public["blink_timer"] = 0.0
        _set_player_visible(context, True)
        return False
    return True


def _start_invulnerability(context, public: dict) -> None:
    public["invulnerable_time_remaining"] = max(
        0.1,
        float(public.get("invulnerable_duration", INVULNERABLE_DURATION)),
    )
    public["blink_timer"] = 0.0
    public["blink_visible"] = False
    _set_player_visible(context, False)


def _damage_player(context, public: dict) -> bool:
    lives = max(0, int(public.get("lives", DEFAULT_LIVES)) - 1)
    public["lives"] = lives
    _sync_hearts(context, lives)
    if lives <= 0:
        public["invulnerable_time_remaining"] = 0.0
        public["blink_timer"] = 0.0
        public["blink_visible"] = True
        _set_player_visible(context, True)
        return bool(context.load_scene_flow_target("restart"))
    _start_invulnerability(context, public)
    return False


def on_play(context) -> None:
    public = context.public_data
    _set_defaults(public)
    public["lives"] = int(public.get("max_lives", DEFAULT_LIVES))
    public["invulnerable_time_remaining"] = 0.0
    public["blink_timer"] = 0.0
    public["blink_visible"] = True
    public["contacting_enemies"] = []
    _set_player_visible(context, True)
    _sync_hearts(context, int(public["lives"]))


def on_update(context, dt: float) -> None:
    input_map = context.get_component("InputMap")
    animator = context.get_component("Animator")
    transform = context.get_component("Transform")
    collider = context.get_component("Collider")

    if input_map is None or animator is None or transform is None:
        return

    public = context.public_data
    _set_defaults(public)

    move_speed = float(public.get("move_speed", MOVE_SPEED))
    last_facing = str(public.get("last_facing", "down"))

    state = input_map.last_state
    horizontal = float(state.get("horizontal") or 0.0)
    vertical = float(state.get("vertical") or 0.0)
    action_1 = float(state.get("action_1") or 0.0)

    is_attacking = str(animator.current_state or "").startswith("attack_")

    action_2_val = float(state.get("action_2") or 0.0)
    action_2_was_down = bool(public.get("action_2_was_down", False))
    action_2_just_pressed = action_2_val > 0.5 and not action_2_was_down
    public["action_2_was_down"] = action_2_val > 0.5

    if action_2_just_pressed:
        if context.load_scene_flow_target("menu"):
            return

    attack_was_down = bool(public.get("attack_was_down", False))
    attack_just_pressed = action_1 > 0.5 and not attack_was_down
    public["attack_was_down"] = action_1 > 0.5

    if not is_attacking and attack_just_pressed:
        attack_state = f"attack_{last_facing}"
        if attack_state in animator.animations:
            animator.play(attack_state)
            is_attacking = True

    dir_x = horizontal
    dir_y = -vertical
    length = math.sqrt(dir_x * dir_x + dir_y * dir_y)
    if length > 1.0:
        dir_x /= length
        dir_y /= length

    if not is_attacking:
        transform.local_x += dir_x * move_speed * dt
        transform.local_y += dir_y * move_speed * dt

    moving = length > INPUT_DEAD_ZONE and not is_attacking
    facing = _facing(horizontal, vertical, last_facing)

    if facing == "side":
        if abs(horizontal) > INPUT_DEAD_ZONE:
            animator.flip_x = horizontal < 0
        target_state = "walk_side" if moving else "idle_side"
    elif facing == "up":
        target_state = "walk_up" if moving else "idle_up"
    else:
        target_state = "walk_down" if moving else "idle_down"

    if not is_attacking and animator.current_state != target_state:
        animator.play(target_state)

    public["last_facing"] = facing

    if collider is not None and collider.enabled:
        contacts = _current_enemy_contacts(context, transform, collider)
        previous_contacts = {str(name) for name in public.get("contacting_enemies", []) if str(name)}
        if contacts and float(public.get("invulnerable_time_remaining", 0.0)) <= 0.0 and contacts - previous_contacts:
            if _damage_player(context, public):
                return
        public["contacting_enemies"] = sorted(contacts)

    _update_invulnerability(context, public, dt)
    _sync_hearts(context, int(public.get("lives", DEFAULT_LIVES)))
