"""
engine/components/scene_transition_on_player_death.py - Disparador por muerte.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class SceneTransitionOnPlayerDeath(Component):
    """Dispara una transicion cuando la entidad recibe el evento player_death."""

    def __init__(self) -> None:
        self.enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneTransitionOnPlayerDeath":
        component = cls()
        component.enabled = bool(data.get("enabled", True))
        return component
