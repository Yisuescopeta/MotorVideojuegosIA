from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any


@dataclass(frozen=True)
class EnemyProfile:
    id: str
    battle_frames: list[int]
    max_hp: int
    physical_defense: int
    magic_defense: int
    attack_pool: list[dict[str, Any]]


PLAYER_ACTIONS: dict[str, dict[str, Any]] = {
    "curar": {"type": "heal", "amount": 50},
    "curar_mana": {"type": "restore_mana", "amount": 10},
    "explosion": {"type": "attack", "power": 30, "mp_cost": 16, "uses": "magic_defense"},
}


ENEMY_CATALOG: dict[str, dict[str, Any]] = {
    "frog": {
        "id": "frog",
        "battle_frames": [0, 1, 2],
        "max_hp": 24,
        "physical_defense": 2,
        "magic_defense": 1,
        "attack_pool": [
            {"name": "tongue", "power": 6},
            {"name": "hop", "power": 4},
        ],
    },
    "mummy": {
        "id": "mummy",
        "battle_frames": [0, 1, 2, 3],
        "max_hp": 38,
        "physical_defense": 5,
        "magic_defense": 9,
        "attack_pool": [
            {"name": "curse", "power": 8},
            {"name": "sand", "power": 5},
        ],
    },
    "ogre": {
        "id": "ogre",
        "battle_frames": [0, 1, 2, 3, 4],
        "max_hp": 70,
        "physical_defense": 12,
        "magic_defense": 4,
        "attack_pool": [
            {"name": "club", "power": 11},
            {"name": "stomp", "power": 8},
        ],
    },
    "slime": {
        "id": "slime",
        "battle_frames": [0, 1],
        "max_hp": 18,
        "physical_defense": 1,
        "magic_defense": 2,
        "attack_pool": [
            {"name": "split", "power": 3},
            {"name": "bounce", "power": 2},
        ],
    },
    "wizard": {
        "id": "wizard",
        "battle_frames": [0, 1, 2, 3],
        "max_hp": 42,
        "physical_defense": 3,
        "magic_defense": 11,
        "attack_pool": [
            {"name": "bolt", "power": 9},
            {"name": "hex", "power": 7},
        ],
    },
}


_DEFEATED_ENEMIES: set[str] = set()


def reset_run_state() -> None:
    _DEFEATED_ENEMIES.clear()


def mark_enemy_defeated(enemy_id: str) -> None:
    if enemy_id:
        _DEFEATED_ENEMIES.add(enemy_id)


def is_enemy_defeated(enemy_id: str) -> bool:
    return enemy_id in _DEFEATED_ENEMIES


def compute_damage(power: int, defense: int) -> int:
    return max(1, int(power) - int(defense))


def _clamp_stat(value: int, maximum: int) -> int:
    return max(0, min(int(value), int(maximum)))


def perform_player_action(
    action_name: str,
    player_state: dict[str, int],
    enemy_state: dict[str, int],
    enemy_profile: dict[str, Any],
) -> dict[str, Any]:
    action = PLAYER_ACTIONS[action_name]
    if action_name == "curar":
        restored = action["amount"]
        player_state["hp"] = _clamp_stat(player_state.get("hp", 0) + restored, 120)
        enemy_state["hp"] = _clamp_stat(enemy_state.get("hp", 0), enemy_profile["max_hp"])
        return {"action": action_name, "restored": restored}
    if action_name == "curar_mana":
        restored = action["amount"]
        player_state["mp"] = _clamp_stat(player_state.get("mp", 0) + restored, 60)
        return {"action": action_name, "restored": restored}
    if action_name == "explosion":
        mp_cost = action["mp_cost"]
        player_state["mp"] = max(0, player_state.get("mp", 0) - mp_cost)
        damage = compute_damage(action["power"], enemy_profile["magic_defense"])
        enemy_state["hp"] = max(0, enemy_state.get("hp", 0) - damage)
        return {"action": action_name, "damage": damage, "mp_cost": mp_cost}
    raise KeyError(action_name)


def choose_enemy_attack(enemy_profile: dict[str, Any]) -> dict[str, Any]:
    pool = list(enemy_profile.get("attack_pool", []))
    if not pool:
        raise ValueError("Enemy attack pool is empty")
    return random.choice(pool)
