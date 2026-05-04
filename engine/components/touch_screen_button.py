"""engine/components/touch_screen_button.py — TouchScreenButton component (Godot parity).
Button designed for touch screen interaction.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class TouchScreenButton(Component):
    """Button designed for touch screen interaction (Godot TouchScreenButton)."""

    def __init__(
        self,
        action: str = "action_1",
        visible: bool = True,
        shape: str = "rectangle",
        shape_width: float = 64.0,
        shape_height: float = 64.0,
        shape_radius: float = 32.0,
        passby_press: bool = False,
        release_on_exit: bool = True,
        bitmap_path: str = "",
    ) -> None:
        self.enabled: bool = True
        self.action: str = str(action)
        self.visible: bool = bool(visible)
        self.shape: str = str(shape) if str(shape) in ("rectangle", "circle") else "rectangle"
        self.shape_width: float = float(shape_width)
        self.shape_height: float = float(shape_height)
        self.shape_radius: float = float(shape_radius)
        self.passby_press: bool = bool(passby_press)
        self.release_on_exit: bool = bool(release_on_exit)
        self.bitmap_path: str = str(bitmap_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "action": self.action,
            "visible": self.visible,
            "shape": self.shape,
            "shape_width": self.shape_width,
            "shape_height": self.shape_height,
            "shape_radius": self.shape_radius,
            "passby_press": self.passby_press,
            "release_on_exit": self.release_on_exit,
            "bitmap_path": self.bitmap_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TouchScreenButton":
        component = cls(
            action=data.get("action", "action_1"),
            visible=data.get("visible", True),
            shape=data.get("shape", "rectangle"),
            shape_width=data.get("shape_width", 64.0),
            shape_height=data.get("shape_height", 64.0),
            shape_radius=data.get("shape_radius", 32.0),
            passby_press=data.get("passby_press", False),
            release_on_exit=data.get("release_on_exit", True),
            bitmap_path=data.get("bitmap_path", ""),
        )
        component.enabled = data.get("enabled", True)
        return component
