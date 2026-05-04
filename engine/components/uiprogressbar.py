"""
engine/components/uiprogressbar.py — ProgressBar (adaptado Godot ProgressBar).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


def _color_tuple(value: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    r, g, b, a = value
    return (int(r), int(g), int(b), int(a))


class ProgressBar(Component):
    """Barra de progreso visual (adaptado Godot ProgressBar)."""

    def __init__(
        self,
        enabled: bool = True,
        value: float = 0.0,
        min_value: float = 0.0,
        max_value: float = 100.0,
        percent_visible: bool = True,
        fill_color: tuple[int, int, int, int] = (0, 200, 0, 255),
        bg_color: tuple[int, int, int, int] = (60, 60, 60, 255),
        horizontal: bool = True,
    ) -> None:
        self.enabled = enabled
        self.value = float(value)
        self.min_value = float(min_value)
        self.max_value = float(max_value)
        self.percent_visible = bool(percent_visible)
        self.fill_color = _color_tuple(fill_color)
        self.bg_color = _color_tuple(bg_color)
        self.horizontal = bool(horizontal)

    @property
    def ratio(self) -> float:
        denom = self.max_value - self.min_value
        if denom == 0.0:
            return 0.0
        return max(0.0, min(1.0, (self.value - self.min_value) / denom))

    @property
    def percent(self) -> float:
        return self.ratio * 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "value": self.value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "percent_visible": self.percent_visible,
            "fill_color": list(self.fill_color),
            "bg_color": list(self.bg_color),
            "horizontal": self.horizontal,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProgressBar":
        return cls(
            enabled=data.get("enabled", True),
            value=data.get("value", 0.0),
            min_value=data.get("min_value", 0.0),
            max_value=data.get("max_value", 100.0),
            percent_visible=data.get("percent_visible", True),
            fill_color=tuple(data.get("fill_color", [0, 200, 0, 255])),  # type: ignore[arg-type]
            bg_color=tuple(data.get("bg_color", [60, 60, 60, 255])),  # type: ignore[arg-type]
            horizontal=data.get("horizontal", True),
        )
