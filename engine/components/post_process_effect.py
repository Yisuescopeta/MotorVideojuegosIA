"""
engine/components/post_process_effect.py - Post-processing effect component.
"""
from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class PostProcessEffectComp(Component):
    """Stores a list of post-processing effects to apply after rendering."""

    def __init__(self, effects: list[dict[str, Any]] | None = None) -> None:
        self.enabled: bool = True
        self.effects: list[dict[str, Any]] = []
        if effects is not None:
            self.effects = [dict(e) for e in effects]

    def add_effect(self, effect_data: dict[str, Any]) -> None:
        self.effects.append(dict(effect_data))

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "effects": [dict(e) for e in self.effects],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PostProcessEffectComp":
        component = cls(
            effects=data.get("effects", []),
        )
        component.enabled = data.get("enabled", True)
        return component
