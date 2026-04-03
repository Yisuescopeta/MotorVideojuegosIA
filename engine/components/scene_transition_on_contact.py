"""
engine/components/scene_transition_on_contact.py - Disparador por contacto.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class SceneTransitionOnContact(Component):
    """Dispara una transicion al entrar en trigger o al colisionar."""

    def __init__(self, mode: str = "trigger_enter", require_player: bool = True) -> None:
        self.enabled: bool = True
        self.mode: str = str(mode or "trigger_enter").strip() or "trigger_enter"
        self.require_player: bool = bool(require_player)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "require_player": self.require_player,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneTransitionOnContact":
        component = cls(
            mode=str(data.get("mode", "trigger_enter") or "trigger_enter"),
            require_player=bool(data.get("require_player", True)),
        )
        component.enabled = bool(data.get("enabled", True))
        return component
