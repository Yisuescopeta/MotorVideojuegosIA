"""
engine/components/scene_entry_point.py - Punto de entrada serializable para transiciones.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class SceneEntryPoint(Component):
    """Marca una entidad como destino de entrada dentro de una escena."""

    def __init__(self, entry_id: str = "", label: str = "") -> None:
        self.enabled: bool = True
        self.entry_id: str = str(entry_id or "").strip()
        self.label: str = str(label or "").strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "entry_id": self.entry_id,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SceneEntryPoint":
        component = cls(
            entry_id=str(data.get("entry_id", "") or ""),
            label=str(data.get("label", "") or ""),
        )
        component.enabled = bool(data.get("enabled", True))
        return component
