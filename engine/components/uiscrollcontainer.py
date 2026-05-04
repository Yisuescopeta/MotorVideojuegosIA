"""
engine/components/uiscrollcontainer.py - Contenedor con scroll (adaptado Godot ScrollContainer).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class UIScrollContainer(Component):
    """Contenedor con scroll vertical/horizontal."""

    def __init__(
        self,
        enabled: bool = True,
        scroll_horizontal: bool = False,
        scroll_vertical: bool = True,
        content_width: float = 200.0,
        content_height: float = 200.0,
    ) -> None:
        self.enabled = enabled
        self.scroll_horizontal = bool(scroll_horizontal)
        self.scroll_vertical = bool(scroll_vertical)
        self.content_width = float(content_width)
        self.content_height = float(content_height)
        # Runtime
        self._scroll_x: float = 0.0
        self._scroll_y: float = 0.0
        self._scroll_speed: float = 300.0

    def scroll(self, dx: float, dy: float) -> None:
        if self.scroll_horizontal:
            self._scroll_x = max(0.0, self._scroll_x + dx)
        if self.scroll_vertical:
            self._scroll_y = max(0.0, self._scroll_y + dy)

    @property
    def scroll_x(self) -> float:
        return self._scroll_x

    @property
    def scroll_y(self) -> float:
        return self._scroll_y

    @property
    def scroll_speed(self) -> float:
        return self._scroll_speed

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "scroll_horizontal": self.scroll_horizontal,
            "scroll_vertical": self.scroll_vertical,
            "content_width": self.content_width,
            "content_height": self.content_height,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIScrollContainer":
        return cls(
            enabled=data.get("enabled", True),
            scroll_horizontal=data.get("scroll_horizontal", False),
            scroll_vertical=data.get("scroll_vertical", True),
            content_width=data.get("content_width", 200.0),
            content_height=data.get("content_height", 200.0),
        )
