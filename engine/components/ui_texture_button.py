"""
engine/components/ui_texture_button.py - Boton basado en texturas (adaptado Godot TextureButton).
"""

from __future__ import annotations

import copy
from typing import Any

from engine.ecs.component import Component


class UITextureButton(Component):
    """Boton basado en texturas (adaptado Godot TextureButton).

    Similar a UIButton pero usa texturas para cada estado en vez de colores.
    """

    def __init__(
        self,
        enabled: bool = True,
        interactable: bool = True,
        texture_normal_path: str = "",
        texture_hover_path: str = "",
        texture_pressed_path: str = "",
        texture_disabled_path: str = "",
        expand_icon: bool = False,
        stretch_mode: str = "scale",
        on_click: dict[str, Any] | None = None,
    ) -> None:
        self.enabled = enabled
        self.interactable = bool(interactable)
        self.texture_normal_path = str(texture_normal_path or "")
        self.texture_hover_path = str(texture_hover_path or "")
        self.texture_pressed_path = str(texture_pressed_path or "")
        self.texture_disabled_path = str(texture_disabled_path or "")
        self.expand_icon = bool(expand_icon)
        self.stretch_mode = str(stretch_mode or "scale")
        self.on_click = copy.deepcopy(on_click or {})
        # Runtime state (not serialized)
        self._is_hovered = False
        self._is_pressed = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "interactable": self.interactable,
            "texture_normal_path": self.texture_normal_path,
            "texture_hover_path": self.texture_hover_path,
            "texture_pressed_path": self.texture_pressed_path,
            "texture_disabled_path": self.texture_disabled_path,
            "expand_icon": self.expand_icon,
            "stretch_mode": self.stretch_mode,
            "on_click": copy.deepcopy(self.on_click),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UITextureButton":
        return cls(
            enabled=data.get("enabled", True),
            interactable=data.get("interactable", True),
            texture_normal_path=data.get("texture_normal_path", ""),
            texture_hover_path=data.get("texture_hover_path", ""),
            texture_pressed_path=data.get("texture_pressed_path", ""),
            texture_disabled_path=data.get("texture_disabled_path", ""),
            expand_icon=data.get("expand_icon", False),
            stretch_mode=data.get("stretch_mode", "scale"),
            on_click=copy.deepcopy(data.get("on_click", {})),
        )
