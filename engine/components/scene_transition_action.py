"""
engine/components/scene_transition_action.py - Accion base de cambio de escena.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class SceneTransitionAction(Component):
    """Define el destino comun reutilizable por varios disparadores."""

    def __init__(self, target_scene_path: str = "", target_entry_id: str = "") -> None:
        self.enabled: bool = True
        self.target_scene_path: str = str(target_scene_path or "").strip()
        self.target_entry_id: str = str(target_entry_id or "").strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "target_scene_path": self.target_scene_path,
            "target_entry_id": self.target_entry_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneTransitionAction":
        component = cls(
            target_scene_path=str(data.get("target_scene_path", "") or ""),
            target_entry_id=str(data.get("target_entry_id", "") or ""),
        )
        component.enabled = bool(data.get("enabled", True))
        return component
