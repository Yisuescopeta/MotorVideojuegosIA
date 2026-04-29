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


def _coerce_event_name(value: Any, default: str) -> str:
    event_name = str(value or "").strip()
    return event_name or default


def _coerce_bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


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
