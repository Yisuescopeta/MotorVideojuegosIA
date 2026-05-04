"""
engine/components/gameplay2d.py - Componentes semanticos minimos de gameplay 2D.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


def _coerce_non_negative_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _coerce_non_negative_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_event_name(value: Any, default: str) -> str:
    event_name = str(value or "").strip()
    return event_name or default


def _coerce_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _coerce_points(value: Any) -> list[dict[str, float]]:
    if not isinstance(value, list):
        return []
    points: list[dict[str, float]] = []
    for item in value:
        if isinstance(item, dict):
            points.append(
                {
                    "x": _coerce_float(item.get("x", 0.0), 0.0),
                    "y": _coerce_float(item.get("y", 0.0), 0.0),
                }
            )
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            points.append(
                {
                    "x": _coerce_float(item[0], 0.0),
                    "y": _coerce_float(item[1], 0.0),
                }
            )
    return points


class Collectible2D(Component):
    """Marca una entidad como coleccionable 2D serializable."""

    DEFAULT_EVENT_NAME = "collectible_collected"

    def __init__(
        self,
        points: int = 1,
        destroy_on_collect: bool = True,
        event_name: str = DEFAULT_EVENT_NAME,
    ) -> None:
        self.enabled: bool = True
        self.points: int = _coerce_non_negative_int(points, 1)
        self.destroy_on_collect: bool = _coerce_bool(destroy_on_collect, True)
        self.event_name: str = _coerce_event_name(event_name, self.DEFAULT_EVENT_NAME)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "points": self.points,
            "destroy_on_collect": self.destroy_on_collect,
            "event_name": self.event_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Collectible2D":
        component = cls(
            points=data.get("points", 1),
            destroy_on_collect=data.get("destroy_on_collect", True),
            event_name=data.get("event_name", cls.DEFAULT_EVENT_NAME),
        )
        component.enabled = _coerce_bool(data.get("enabled", True), True)
        return component


class Hazard2D(Component):
    """Marca una entidad como amenaza 2D serializable."""

    DEFAULT_EVENT_NAME = "hazard_touched"

    def __init__(
        self,
        damage: int = 1,
        respawn_on_touch: bool = True,
        event_name: str = DEFAULT_EVENT_NAME,
    ) -> None:
        self.enabled: bool = True
        self.damage: int = _coerce_non_negative_int(damage, 1)
        self.respawn_on_touch: bool = _coerce_bool(respawn_on_touch, True)
        self.event_name: str = _coerce_event_name(event_name, self.DEFAULT_EVENT_NAME)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "damage": self.damage,
            "respawn_on_touch": self.respawn_on_touch,
            "event_name": self.event_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Hazard2D":
        component = cls(
            damage=data.get("damage", 1),
            respawn_on_touch=data.get("respawn_on_touch", True),
            event_name=data.get("event_name", cls.DEFAULT_EVENT_NAME),
        )
        component.enabled = _coerce_bool(data.get("enabled", True), True)
        return component


class Goal2D(Component):
    """Marca una entidad como meta 2D serializable."""

    DEFAULT_EVENT_NAME = "goal_reached"

    def __init__(
        self,
        complete_on_touch: bool = True,
        next_scene: str = "",
        event_name: str = DEFAULT_EVENT_NAME,
    ) -> None:
        self.enabled: bool = True
        self.complete_on_touch: bool = _coerce_bool(complete_on_touch, True)
        self.next_scene: str = str(next_scene or "").strip()
        self.event_name: str = _coerce_event_name(event_name, self.DEFAULT_EVENT_NAME)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "complete_on_touch": self.complete_on_touch,
            "next_scene": self.next_scene,
            "event_name": self.event_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Goal2D":
        component = cls(
            complete_on_touch=data.get("complete_on_touch", True),
            next_scene=data.get("next_scene", ""),
            event_name=data.get("event_name", cls.DEFAULT_EVENT_NAME),
        )
        component.enabled = _coerce_bool(data.get("enabled", True), True)
        return component


class RespawnPoint2D(Component):
    """Marca un punto de respawn 2D serializable."""

    def __init__(self, spawn_id: str = "default", active: bool = True) -> None:
        self.enabled: bool = True
        self.spawn_id: str = str(spawn_id or "default").strip() or "default"
        self.active: bool = _coerce_bool(active, True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "spawn_id": self.spawn_id,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RespawnPoint2D":
        component = cls(
            spawn_id=data.get("spawn_id", "default"),
            active=data.get("active", True),
        )
        component.enabled = _coerce_bool(data.get("enabled", True), True)
        return component


class MovingPlatform2D(Component):
    """Datos serializables para una plataforma movil 2D."""

    def __init__(
        self,
        path: list[dict[str, float]] | None = None,
        speed: float = 80.0,
        loop: bool = True,
        start_active: bool = True,
    ) -> None:
        self.enabled: bool = True
        self.path: list[dict[str, float]] = _coerce_points(path or [])
        self.speed: float = _coerce_non_negative_float(speed, 80.0)
        self.loop: bool = _coerce_bool(loop, True)
        self.start_active: bool = _coerce_bool(start_active, True)
        # Runtime fields (not serialized)
        self.platform_velocity_x: float = 0.0
        self.platform_velocity_y: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "path": [dict(point) for point in self.path],
            "speed": self.speed,
            "loop": self.loop,
            "start_active": self.start_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MovingPlatform2D":
        component = cls(
            path=data.get("path", []),
            speed=data.get("speed", 80.0),
            loop=data.get("loop", True),
            start_active=data.get("start_active", True),
        )
        component.enabled = _coerce_bool(data.get("enabled", True), True)
        return component


class EnemyPatrol2D(Component):
    """Datos serializables para una patrulla enemiga 2D."""

    DEFAULT_EVENT_NAME = "enemy_touched"

    def __init__(
        self,
        patrol_points: list[dict[str, float]] | None = None,
        speed: float = 80.0,
        damage: int = 1,
        event_name: str = DEFAULT_EVENT_NAME,
    ) -> None:
        self.enabled: bool = True
        self.patrol_points: list[dict[str, float]] = _coerce_points(patrol_points or [])
        self.speed: float = _coerce_non_negative_float(speed, 80.0)
        self.damage: int = _coerce_non_negative_int(damage, 1)
        self.event_name: str = _coerce_event_name(event_name, self.DEFAULT_EVENT_NAME)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "patrol_points": [dict(point) for point in self.patrol_points],
            "speed": self.speed,
            "damage": self.damage,
            "event_name": self.event_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnemyPatrol2D":
        component = cls(
            patrol_points=data.get("patrol_points", []),
            speed=data.get("speed", 80.0),
            damage=data.get("damage", 1),
            event_name=data.get("event_name", cls.DEFAULT_EVENT_NAME),
        )
        component.enabled = _coerce_bool(data.get("enabled", True), True)
        return component


class Checkpoint2D(Component):
    """Datos serializables para checkpoint 2D."""

    DEFAULT_EVENT_NAME = "checkpoint_reached"

    def __init__(
        self,
        checkpoint_id: str = "default",
        active: bool = True,
        set_respawn_on_touch: bool = True,
        event_name: str = DEFAULT_EVENT_NAME,
    ) -> None:
        self.enabled: bool = True
        self.checkpoint_id: str = str(checkpoint_id or "default").strip() or "default"
        self.active: bool = _coerce_bool(active, True)
        self.set_respawn_on_touch: bool = _coerce_bool(set_respawn_on_touch, True)
        self.event_name: str = _coerce_event_name(event_name, self.DEFAULT_EVENT_NAME)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "checkpoint_id": self.checkpoint_id,
            "active": self.active,
            "set_respawn_on_touch": self.set_respawn_on_touch,
            "event_name": self.event_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint2D":
        component = cls(
            checkpoint_id=data.get("checkpoint_id", "default"),
            active=data.get("active", True),
            set_respawn_on_touch=data.get("set_respawn_on_touch", True),
            event_name=data.get("event_name", cls.DEFAULT_EVENT_NAME),
        )
        component.enabled = _coerce_bool(data.get("enabled", True), True)
        return component


class KillZone2D(Component):
    """Datos serializables para zona letal 2D."""

    DEFAULT_EVENT_NAME = "killzone_touched"

    def __init__(
        self,
        damage: int = 1,
        respawn_on_touch: bool = True,
        event_name: str = DEFAULT_EVENT_NAME,
    ) -> None:
        self.enabled: bool = True
        self.damage: int = _coerce_non_negative_int(damage, 1)
        self.respawn_on_touch: bool = _coerce_bool(respawn_on_touch, True)
        self.event_name: str = _coerce_event_name(event_name, self.DEFAULT_EVENT_NAME)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "damage": self.damage,
            "respawn_on_touch": self.respawn_on_touch,
            "event_name": self.event_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KillZone2D":
        component = cls(
            damage=data.get("damage", 1),
            respawn_on_touch=data.get("respawn_on_touch", True),
            event_name=data.get("event_name", cls.DEFAULT_EVENT_NAME),
        )
        component.enabled = _coerce_bool(data.get("enabled", True), True)
        return component


class LevelBounds2D(Component):
    """Datos serializables de limites de nivel 2D."""

    def __init__(
        self,
        left: float = 0.0,
        right: float = 1280.0,
        top: float = 0.0,
        bottom: float = 720.0,
    ) -> None:
        self.enabled: bool = True
        self.left: float = _coerce_float(left, 0.0)
        self.right: float = _coerce_float(right, 1280.0)
        self.top: float = _coerce_float(top, 0.0)
        self.bottom: float = _coerce_float(bottom, 720.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "left": self.left,
            "right": self.right,
            "top": self.top,
            "bottom": self.bottom,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LevelBounds2D":
        component = cls(
            left=data.get("left", 0.0),
            right=data.get("right", 1280.0),
            top=data.get("top", 0.0),
            bottom=data.get("bottom", 720.0),
        )
        component.enabled = _coerce_bool(data.get("enabled", True), True)
        return component
