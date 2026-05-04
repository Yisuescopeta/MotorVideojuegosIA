"""
engine/components/sub_viewport.py - SubViewport + ViewportTexture components (Godot inspired).
"""
from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class SubViewport(Component):
    """Godot SubViewport — renders a subtree to a texture."""

    RENDER_TARGET_UPDATE_ALWAYS: str = "always"
    RENDER_TARGET_UPDATE_ONCE: str = "once"
    RENDER_TARGET_UPDATE_WHEN_VISIBLE: str = "when_visible"

    def __init__(
        self,
        size_x: int = 512,
        size_y: int = 512,
        transparent_bg: bool = True,
        own_world_2d: bool = False,
        render_target_update_mode: str = "always",
    ) -> None:
        self.enabled: bool = True
        self.size_x: int = max(1, int(size_x))
        self.size_y: int = max(1, int(size_y))
        self.transparent_bg: bool = bool(transparent_bg)
        self.own_world_2d: bool = bool(own_world_2d)
        self.render_target_update_mode: str = str(render_target_update_mode or "always")
        # Runtime
        self._render_texture: Any = None
        self._needs_update: bool = True

    @property
    def needs_update(self) -> bool:
        return self._needs_update

    @needs_update.setter
    def needs_update(self, value: bool) -> None:
        self._needs_update = bool(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "size_x": self.size_x,
            "size_y": self.size_y,
            "transparent_bg": self.transparent_bg,
            "own_world_2d": self.own_world_2d,
            "render_target_update_mode": self.render_target_update_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubViewport":
        component = cls(
            size_x=data.get("size_x", 512),
            size_y=data.get("size_y", 512),
            transparent_bg=data.get("transparent_bg", True),
            own_world_2d=data.get("own_world_2d", False),
            render_target_update_mode=data.get("render_target_update_mode", "always"),
        )
        component.enabled = data.get("enabled", True)
        return component


class ViewportTexture(Component):
    """Texture dynamically updated from a SubViewport (apply to Sprite)."""

    def __init__(self, viewport_entity: str = "") -> None:
        self.enabled: bool = True
        self.viewport_entity: str = str(viewport_entity or "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "viewport_entity": self.viewport_entity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ViewportTexture":
        component = cls(
            viewport_entity=data.get("viewport_entity", ""),
        )
        component.enabled = data.get("enabled", True)
        return component
