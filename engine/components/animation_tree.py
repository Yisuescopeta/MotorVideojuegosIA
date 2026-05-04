"""engine/components/animation_tree.py - AnimationTree component (Godot-style)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from engine.ecs.component import Component
from engine.resources.animation_tree import AnimationTreeResource


class AnimationTree(Component):
    """Godot-style AnimationTree component for blend tree / state machine playback."""

    def __init__(
        self,
        animation_tree_path: str = "",
        active: bool = True,
        speed_scale: float = 1.0,
    ) -> None:
        self.enabled: bool = True
        self.animation_tree_path: str = animation_tree_path
        self.active: bool = active
        self.tree_root: Optional[AnimationTreeResource] = None
        self.parameters: Dict[str, Any] = {}
        self.speed_scale: float = max(0.01, float(speed_scale))
        # Runtime blend state
        self._current_weights: Dict[str, float] = {}
        self._current_positions: Dict[str, float] = {}

    def set_parameter(self, name: str, value: Any) -> None:
        self.parameters[name] = value

    def get_parameter(self, name: str, default: Any = None) -> Any:
        return self.parameters.get(name, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "animation_tree_path": self.animation_tree_path,
            "active": self.active,
            "speed_scale": self.speed_scale,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnimationTree":
        if not isinstance(data, dict):
            return cls()
        instance = cls(
            animation_tree_path=str(data.get("animation_tree_path", "")),
            active=bool(data.get("active", True)),
            speed_scale=float(data.get("speed_scale", 1.0)),
        )
        instance.enabled = bool(data.get("enabled", True))
        raw_params = data.get("parameters", {}) or {}
        if isinstance(raw_params, dict):
            instance.parameters = dict(raw_params)
        return instance
