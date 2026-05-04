"""
engine/components/uispinbox.py — SpinBox para entrada numerica (adaptado Godot SpinBox).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class SpinBox(Component):
    """Control de entrada numerica con flechas de incremento/decremento (adaptado Godot SpinBox)."""

    def __init__(
        self,
        enabled: bool = True,
        value: float = 0.0,
        min_value: float = 0.0,
        max_value: float = 100.0,
        step: float = 1.0,
        prefix: str = "",
        suffix: str = "",
        editable: bool = True,
    ) -> None:
        self.enabled = enabled
        self.value = float(value)
        self.min_value = float(min_value)
        self.max_value = float(max_value)
        self.step = max(0.0, float(step))
        self.prefix = str(prefix)
        self.suffix = str(suffix)
        self.editable = bool(editable)

    def increment(self) -> None:
        self.value = min(self.max_value, self.value + self.step)

    def decrement(self) -> None:
        self.value = max(self.min_value, self.value - self.step)

    @property
    def display_text(self) -> str:
        return f"{self.prefix}{self.value}{self.suffix}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "value": self.value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "step": self.step,
            "prefix": self.prefix,
            "suffix": self.suffix,
            "editable": self.editable,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpinBox":
        return cls(
            enabled=data.get("enabled", True),
            value=data.get("value", 0.0),
            min_value=data.get("min_value", 0.0),
            max_value=data.get("max_value", 100.0),
            step=data.get("step", 1.0),
            prefix=data.get("prefix", ""),
            suffix=data.get("suffix", ""),
            editable=data.get("editable", True),
        )
