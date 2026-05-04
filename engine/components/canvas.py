"""
engine/components/canvas.py - Canvas UI overlay serializable.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class Canvas(Component):
    """Define un arbol UI overlay y su escalado base."""

    def __init__(
        self,
        enabled: bool = True,
        render_mode: str = "screen_space_overlay",
        reference_width: int = 800,
        reference_height: int = 600,
        match_mode: str = "stretch",
        sort_order: int = 0,
    ) -> None:
        self.enabled = enabled
        self.render_mode = str(render_mode or "screen_space_overlay")
        self.reference_width = max(1, int(reference_width))
        self.reference_height = max(1, int(reference_height))
        self.match_mode = str(match_mode or "stretch")
        self.sort_order = int(sort_order)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "render_mode": self.render_mode,
            "reference_width": self.reference_width,
            "reference_height": self.reference_height,
            "match_mode": self.match_mode,
            "sort_order": self.sort_order,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Canvas":
        return cls(
            enabled=data.get("enabled", True),
            render_mode=data.get("render_mode", "screen_space_overlay"),
            reference_width=data.get("reference_width", 800),
            reference_height=data.get("reference_height", 600),
            match_mode=data.get("match_mode", "stretch"),
            sort_order=data.get("sort_order", 0),
        )
