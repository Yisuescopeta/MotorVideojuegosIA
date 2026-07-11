"""Deterministic semantic prefab payloads for experimental GameSpec2D scenes."""

from __future__ import annotations

from typing import Any

JsonDict = dict[str, Any]

SEMANTIC_RGBA_PALETTE: dict[str, tuple[int, int, int, int]] = {
    "player_spawn": (80, 160, 255, 255),
    "solid_ground": (110, 95, 70, 255),
    "platform": (130, 130, 150, 255),
    "coin": (255, 220, 50, 255),
    "enemy_patrol": (220, 60, 60, 255),
    "hazard": (255, 80, 20, 255),
    "goal": (80, 230, 120, 255),
    "checkpoint": (80, 220, 255, 255),
    "killzone": (180, 20, 20, 150),
    "decorative_prop": (180, 180, 180, 255),
}


def transform_payload(x: float, y: float) -> JsonDict:
    return {"x": float(x), "y": float(y), "rotation": 0.0, "scale_x": 1.0, "scale_y": 1.0}


def collider_payload(width: float, height: float, *, is_trigger: bool = False) -> JsonDict:
    return {
        "width": float(width),
        "height": float(height),
        "offset_x": 0.0,
        "offset_y": 0.0,
        "is_trigger": bool(is_trigger),
        "shape_type": "box",
        "radius": float(width) / 2.0,
        "points": [],
        "friction": 0.2,
        "restitution": 0.0,
        "density": 1.0,
        "capsule_height": 0.0,
        "one_way_collision": False,
        "one_way_collision_direction_y": -1.0,
        "one_way_collision_margin": 1.0,
        "one_way_collision_direction_x": 0.0,
    }


def sprite_payload(width: float, height: float, tint: tuple[int, int, int, int]) -> JsonDict:
    return {
        "texture": {"guid": "", "path": ""},
        "texture_path": "",
        "width": int(round(width)),
        "height": int(round(height)),
        "origin_x": 0.5,
        "origin_y": 0.5,
        "flip_x": False,
        "flip_y": False,
        "tint": list(tint),
        "source_slice": "",
    }


def polygon_payload(width: float, height: float, color: tuple[int, int, int, int]) -> JsonDict:
    """Return an asset-free rectangle centered on its entity Transform."""
    half_width = float(width) / 2.0
    half_height = float(height) / 2.0
    return {
        "enabled": True,
        "points": [
            [-half_width, -half_height],
            [half_width, -half_height],
            [half_width, half_height],
            [-half_width, half_height],
        ],
        "color": list(color),
        "texture": {"guid": "", "path": ""},
        "texture_path": "",
        "offset_x": 0.0,
        "offset_y": 0.0,
    }


def camera_payload(world_width: float, world_height: float, follow_entity: str = "") -> JsonDict:
    return {
        "offset_x": 0.0,
        "offset_y": 0.0,
        "zoom": 1.0,
        "rotation": 0.0,
        "is_primary": True,
        "follow_entity": follow_entity,
        "framing_mode": "platformer",
        "dead_zone_width": 0.0,
        "dead_zone_height": 0.0,
        "clamp_left": 0.0,
        "clamp_right": float(world_width),
        "clamp_top": 0.0,
        "clamp_bottom": float(world_height),
        "recenter_on_play": True,
        "profile_overrides": {},
    }


def semantic_components(entity_type: str, width: float, height: float, *, index: int = 1) -> JsonDict:
    """Return registered component payloads for a GameSpec2D entity type."""
    color = SEMANTIC_RGBA_PALETTE.get(entity_type, SEMANTIC_RGBA_PALETTE["decorative_prop"])
    if entity_type == "player_spawn":
        return {
            "RespawnPoint2D": {"spawn_id": "player", "active": True},
            "Sprite": sprite_payload(width, height, color),
            "Polygon2D": polygon_payload(width, height, color),
        }
    if entity_type == "solid_ground":
        return {
            "Collider": collider_payload(width, height),
            "Sprite": sprite_payload(width, height, color),
            "Polygon2D": polygon_payload(width, height, color),
        }
    if entity_type == "platform":
        return {
            "Collider": collider_payload(width, height),
            "MovingPlatform2D": {"path": [], "speed": 80.0, "loop": True, "start_active": True},
            "Sprite": sprite_payload(width, height, color),
            "Polygon2D": polygon_payload(width, height, color),
        }
    if entity_type == "coin":
        return {
            "Collider": collider_payload(width, height, is_trigger=True),
            "Collectible2D": {"points": 1, "destroy_on_collect": True, "event_name": "collectible_collected"},
            "Sprite": sprite_payload(width, height, color),
            "Polygon2D": polygon_payload(width, height, color),
        }
    if entity_type == "enemy_patrol":
        return {
            "Collider": collider_payload(width, height, is_trigger=True),
            "EnemyPatrol2D": {"patrol_points": [], "speed": 80.0, "damage": 1, "event_name": "enemy_touched"},
            "Sprite": sprite_payload(width, height, color),
            "Polygon2D": polygon_payload(width, height, color),
        }
    if entity_type == "hazard":
        return {
            "Collider": collider_payload(width, height, is_trigger=True),
            "Hazard2D": {"damage": 1, "respawn_on_touch": True, "event_name": "hazard_touched"},
            "Sprite": sprite_payload(width, height, color),
            "Polygon2D": polygon_payload(width, height, color),
        }
    if entity_type == "goal":
        return {
            "Collider": collider_payload(width, height, is_trigger=True),
            "Goal2D": {"complete_on_touch": True, "next_scene": "", "event_name": "goal_reached"},
            "Sprite": sprite_payload(width, height, color),
            "Polygon2D": polygon_payload(width, height, color),
        }
    if entity_type == "checkpoint":
        return {
            "Collider": collider_payload(width, height, is_trigger=True),
            "Checkpoint2D": {
                "checkpoint_id": f"checkpoint_{index:03d}",
                "active": True,
                "set_respawn_on_touch": True,
                "event_name": "checkpoint_reached",
            },
            "Sprite": sprite_payload(width, height, color),
            "Polygon2D": polygon_payload(width, height, color),
        }
    if entity_type == "killzone":
        return {
            "Collider": collider_payload(width, height, is_trigger=True),
            "KillZone2D": {"damage": 1, "respawn_on_touch": True, "event_name": "killzone_touched"},
            "Sprite": sprite_payload(width, height, color),
            "Polygon2D": polygon_payload(width, height, color),
        }
    return {
        "Sprite": sprite_payload(width, height, color),
        "Polygon2D": polygon_payload(width, height, color),
    }


REGISTERED_COMPONENTS_USED = frozenset(
    {
        "Transform",
        "Collider",
        "Sprite",
        "Polygon2D",
        "Camera2D",
        "RespawnPoint2D",
        "MovingPlatform2D",
        "Collectible2D",
        "EnemyPatrol2D",
        "Hazard2D",
        "Goal2D",
        "Checkpoint2D",
        "KillZone2D",
    }
)
