"""
engine/components/uibutton.py - Boton UI serializable con accion declarativa.
"""

from __future__ import annotations

import copy
from typing import Any

from engine.ecs.component import Component


class UIButton(Component):
    """Boton UI con accion declarativa ejecutada al soltar dentro del control."""

    def __init__(
        self,
        enabled: bool = True,
        interactable: bool = True,
        label: str = "Button",
        normal_color: tuple[int, int, int, int] = (72, 72, 72, 255),
        hover_color: tuple[int, int, int, int] = (92, 92, 92, 255),
        pressed_color: tuple[int, int, int, int] = (56, 56, 56, 255),
        disabled_color: tuple[int, int, int, int] = (48, 48, 48, 200),
        transition_scale_pressed: float = 0.96,
        on_click: dict[str, Any] | None = None,
        focusable: bool = True,
        nav_up: str = "",
        nav_down: str = "",
        nav_left: str = "",
        nav_right: str = "",
    ) -> None:
        self.enabled = enabled
        self.interactable = bool(interactable)
        self.label = str(label)
        self.normal_color = tuple(int(v) for v in normal_color)
        self.hover_color = tuple(int(v) for v in hover_color)
        self.pressed_color = tuple(int(v) for v in pressed_color)
        self.disabled_color = tuple(int(v) for v in disabled_color)
        self.transition_scale_pressed = float(transition_scale_pressed)
        self.on_click = copy.deepcopy(on_click or {})
        self.focusable = bool(focusable)
        self.nav_up = str(nav_up or "").strip()
        self.nav_down = str(nav_down or "").strip()
        self.nav_left = str(nav_left or "").strip()
        self.nav_right = str(nav_right or "").strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "interactable": self.interactable,
            "label": self.label,
            "normal_color": list(self.normal_color),
            "hover_color": list(self.hover_color),
            "pressed_color": list(self.pressed_color),
            "disabled_color": list(self.disabled_color),
            "transition_scale_pressed": self.transition_scale_pressed,
            "on_click": copy.deepcopy(self.on_click),
            "focusable": self.focusable,
            "nav_up": self.nav_up,
            "nav_down": self.nav_down,
            "nav_left": self.nav_left,
            "nav_right": self.nav_right,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIButton":
        return cls(
            enabled=data.get("enabled", True),
            interactable=data.get("interactable", True),
            label=data.get("label", "Button"),
            normal_color=tuple(data.get("normal_color", [72, 72, 72, 255])),  # type: ignore[arg-type]
            hover_color=tuple(data.get("hover_color", [92, 92, 92, 255])),  # type: ignore[arg-type]
            pressed_color=tuple(data.get("pressed_color", [56, 56, 56, 255])),  # type: ignore[arg-type]
            disabled_color=tuple(data.get("disabled_color", [48, 48, 48, 200])),  # type: ignore[arg-type]
            transition_scale_pressed=data.get("transition_scale_pressed", 0.96),
            on_click=copy.deepcopy(data.get("on_click", {})),
            focusable=data.get("focusable", True),
            nav_up=data.get("nav_up", ""),
            nav_down=data.get("nav_down", ""),
            nav_left=data.get("nav_left", ""),
            nav_right=data.get("nav_right", ""),
        )
