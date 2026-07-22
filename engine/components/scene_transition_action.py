"""
engine/components/scene_transition_action.py - Accion base de cambio de escena.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class SceneTransitionAction(Component):
    """Define el destino comun reutilizable por varios disparadores."""

    def __init__(
        self,
        target_scene_path: str = "",
        target_entry_id: str = "",
        target_scene: dict[str, str] | None = None,
    ) -> None:
        self.enabled: bool = True
        self.target_scene_path: str = str(target_scene_path or "").strip()
        self.target_entry_id: str = str(target_entry_id or "").strip()
        self.target_scene: dict[str, str] | None = (
            {
                "guid": str(target_scene.get("guid", "") or "").strip(),
                "path_hint": str(target_scene.get("path_hint", "") or "").strip(),
            }
            if isinstance(target_scene, dict)
            else None
        )
        if self.target_scene is not None and not self.target_scene_path:
            # Runtime lookup consumes only the path hint. Persistence remains
            # GUID-first because to_dict() removes target_scene_path.
            self.target_scene_path = self.target_scene.get("path_hint", "")

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "enabled": self.enabled,
            "target_scene_path": self.target_scene_path,
            "target_entry_id": self.target_entry_id,
        }
        if self.target_scene is not None:
            payload["target_scene"] = dict(self.target_scene)
            payload.pop("target_scene_path", None)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneTransitionAction":
        component = cls(
            target_scene_path=str(data.get("target_scene_path", "") or ""),
            target_entry_id=str(data.get("target_entry_id", "") or ""),
            target_scene=data.get("target_scene") if isinstance(data.get("target_scene"), dict) else None,
        )
        component.enabled = bool(data.get("enabled", True))
        return component
