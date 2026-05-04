"""
engine/components/uislider.py — Slider horizontal/vertical (adaptado Godot Slider).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class Slider(Component):
    """Barra deslizante para seleccion de valor numerico (adaptado Godot Slider)."""

    def __init__(
        self,
        enabled: bool = True,
        value: float = 0.0,
        min_value: float = 0.0,
        max_value: float = 100.0,
        step: float = 1.0,
        horizontal: bool = True,
        editable: bool = True,
        tick_count: int = 0,
    ) -> None:
        self.enabled = enabled
        self.value = float(value)
        self.min_value = float(min_value)
        self.max_value = float(max_value)
        self.step = max(0.0, float(step))
        self.horizontal = bool(horizontal)
        self.editable = bool(editable)
        self.tick_count = int(tick_count)

    @property
    def ratio(self) -> float:
        denom = self.max_value - self.min_value
        if denom == 0.0:
            return 0.0
        return max(0.0, min(1.0, (self.value - self.min_value) / denom))

    def set_value(self, raw: float) -> None:
        clamped = max(self.min_value, min(self.max_value, float(raw)))
        if self.step > 0.0:
            clamped = round(clamped / self.step) * self.step
        self.value = max(self.min_value, min(self.max_value, clamped))

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "value": self.value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "step": self.step,
            "horizontal": self.horizontal,
            "editable": self.editable,
            "tick_count": self.tick_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Slider":
        return cls(
            enabled=data.get("enabled", True),
            value=data.get("value", 0.0),
            min_value=data.get("min_value", 0.0),
            max_value=data.get("max_value", 100.0),
            step=data.get("step", 1.0),
            horizontal=data.get("horizontal", True),
            editable=data.get("editable", True),
            tick_count=data.get("tick_count", 0),
        )
