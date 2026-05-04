"""
engine/components/uicheckbox.py — CheckBox UI (adaptado Godot CheckBox).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class CheckBox(Component):
    """Casilla de verificacion con etiqueta (adaptado Godot CheckBox)."""

    def __init__(
        self,
        enabled: bool = True,
        text: str = "",
        checked: bool = False,
        toggle_mode: bool = True,
    ) -> None:
        self.enabled = enabled
        self.text = str(text)
        self.checked = bool(checked)
        self.toggle_mode = bool(toggle_mode)

    def toggle(self) -> None:
        self.checked = not self.checked

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "text": self.text,
            "checked": self.checked,
            "toggle_mode": self.toggle_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckBox":
        return cls(
            enabled=data.get("enabled", True),
            text=data.get("text", ""),
            checked=data.get("checked", False),
            toggle_mode=data.get("toggle_mode", True),
        )
