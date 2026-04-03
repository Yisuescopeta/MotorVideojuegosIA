"""
engine/components/scene_transition_on_interact.py - Disparador por interaccion.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class SceneTransitionOnInteract(Component):
    """Dispara una transicion al interactuar con un trigger cercano."""

    def __init__(self, require_player: bool = True) -> None:
        self.enabled: bool = True
        self.require_player: bool = bool(require_player)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "require_player": self.require_player,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneTransitionOnInteract":
        component = cls(require_player=bool(data.get("require_player", True)))
        component.enabled = bool(data.get("enabled", True))
        return component
