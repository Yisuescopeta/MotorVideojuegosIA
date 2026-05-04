"""
engine/components/ui_splitcontainer.py — SplitContainer UI (adaptado Godot SplitContainer).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class UISplitContainer(Component):
    """Godot SplitContainer — resizable split between two children."""

    def __init__(
        self,
        enabled: bool = True,
        split_offset: float = 0.5,
        vertical: bool = False,
        dragger_visibility: str = "visible",
        collapsed: bool = False,
        drag_step: float = 1.0,
    ) -> None:
        self.enabled = enabled
        self.split_offset = max(0.0, min(1.0, float(split_offset)))
        self.vertical = bool(vertical)
        self.dragger_visibility = str(dragger_visibility or "visible").strip().lower() or "visible"
        self.collapsed = bool(collapsed)
        self.drag_step = max(1.0, float(drag_step))

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "split_offset": self.split_offset,
            "vertical": self.vertical,
            "dragger_visibility": self.dragger_visibility,
            "collapsed": self.collapsed,
            "drag_step": self.drag_step,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UISplitContainer":
        return cls(
            enabled=data.get("enabled", True),
            split_offset=data.get("split_offset", 0.5),
            vertical=data.get("vertical", False),
            dragger_visibility=data.get("dragger_visibility", "visible"),
            collapsed=data.get("collapsed", False),
            drag_step=data.get("drag_step", 1.0),
        )
