"""
engine/components/recttransform.py - Layout serializable para UI overlay.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component

LAYOUT_MODES = {"free", "vertical_stack", "horizontal_stack", "grid", "flow", "aspect_ratio", "center"}
SIZE_MODES = {"fixed", "stretch"}
LAYOUT_ALIGNS = {"start", "center", "end", "stretch"}


def _normalize_choice(value: Any, *, default: str, allowed: set[str]) -> str:
    normalized = str(value if value is not None else default).strip().lower()
    return normalized if normalized in allowed else default


def _coerce_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class RectTransform(Component):
    """Describe anclas, tamano y reglas de layout de un nodo UI."""

    def __init__(
        self,
        enabled: bool = True,
        anchor_min_x: float = 0.5,
        anchor_min_y: float = 0.5,
        anchor_max_x: float = 0.5,
        anchor_max_y: float = 0.5,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        anchored_x: float = 0.0,
        anchored_y: float = 0.0,
        width: float = 100.0,
        height: float = 40.0,
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        layout_mode: str = "free",
        layout_order: int = 0,
        layout_ignore: bool = False,
        size_mode_x: str = "fixed",
        size_mode_y: str = "fixed",
        layout_align: str = "start",
        padding_left: float = 0.0,
        padding_top: float = 0.0,
        padding_right: float = 0.0,
        padding_bottom: float = 0.0,
        spacing: float = 0.0,
        focus_mode: str = "none",
        mouse_filter: str = "pass",
        focusable: bool = False,
        # Grid layout
        grid_columns: int = 2,
        grid_rows: int = 1,
        # Flow layout
        flow_direction: str = "horizontal",
        # Aspect ratio layout
        aspect_ratio: float = 1.0,
        aspect_stretch_mode: str = "fit",
    ) -> None:
        self.enabled = enabled
        self.anchor_min_x = float(anchor_min_x)
        self.anchor_min_y = float(anchor_min_y)
        self.anchor_max_x = float(anchor_max_x)
        self.anchor_max_y = float(anchor_max_y)
        self.pivot_x = float(pivot_x)
        self.pivot_y = float(pivot_y)
        self.anchored_x = float(anchored_x)
        self.anchored_y = float(anchored_y)
        self.width = float(width)
        self.height = float(height)
        self.rotation = float(rotation)
        self.scale_x = float(scale_x)
        self.scale_y = float(scale_y)
        self.layout_mode = _normalize_choice(layout_mode, default="free", allowed=LAYOUT_MODES)
        self.layout_order = _coerce_int(layout_order, default=0)
        self.layout_ignore = bool(layout_ignore)
        self.size_mode_x = _normalize_choice(size_mode_x, default="fixed", allowed=SIZE_MODES)
        self.size_mode_y = _normalize_choice(size_mode_y, default="fixed", allowed=SIZE_MODES)
        self.layout_align = _normalize_choice(layout_align, default="start", allowed=LAYOUT_ALIGNS)
        self.padding_left = float(padding_left)
        self.padding_top = float(padding_top)
        self.padding_right = float(padding_right)
        self.padding_bottom = float(padding_bottom)
        self.spacing = float(spacing)
        self.focus_mode = _normalize_choice(focus_mode, default="none", allowed={"none", "click", "all"})
        self.mouse_filter = _normalize_choice(mouse_filter, default="pass", allowed={"pass", "stop", "ignore"})
        self.focusable = bool(focusable)
        self.grid_columns = _coerce_int(grid_columns, default=2)
        self.grid_rows = _coerce_int(grid_rows, default=1)
        self.flow_direction = _normalize_choice(flow_direction, default="horizontal", allowed={"horizontal", "vertical"})
        self.aspect_ratio = max(0.1, float(aspect_ratio))
        self.aspect_stretch_mode = _normalize_choice(aspect_stretch_mode, default="fit", allowed={"fit", "fill", "width_control_height"})

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "anchor_min_x": self.anchor_min_x,
            "anchor_min_y": self.anchor_min_y,
            "anchor_max_x": self.anchor_max_x,
            "anchor_max_y": self.anchor_max_y,
            "pivot_x": self.pivot_x,
            "pivot_y": self.pivot_y,
            "anchored_x": self.anchored_x,
            "anchored_y": self.anchored_y,
            "width": self.width,
            "height": self.height,
            "rotation": self.rotation,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "layout_mode": self.layout_mode,
            "layout_order": self.layout_order,
            "layout_ignore": self.layout_ignore,
            "size_mode_x": self.size_mode_x,
            "size_mode_y": self.size_mode_y,
            "layout_align": self.layout_align,
            "padding_left": self.padding_left,
            "padding_top": self.padding_top,
            "padding_right": self.padding_right,
            "padding_bottom": self.padding_bottom,
            "spacing": self.spacing,
            "focus_mode": self.focus_mode,
            "mouse_filter": self.mouse_filter,
            "focusable": self.focusable,
            "grid_columns": self.grid_columns,
            "grid_rows": self.grid_rows,
            "flow_direction": self.flow_direction,
            "aspect_ratio": self.aspect_ratio,
            "aspect_stretch_mode": self.aspect_stretch_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RectTransform":
        return cls(
            enabled=data.get("enabled", True),
            anchor_min_x=data.get("anchor_min_x", 0.5),
            anchor_min_y=data.get("anchor_min_y", 0.5),
            anchor_max_x=data.get("anchor_max_x", data.get("anchor_min_x", 0.5)),
            anchor_max_y=data.get("anchor_max_y", data.get("anchor_min_y", 0.5)),
            pivot_x=data.get("pivot_x", 0.5),
            pivot_y=data.get("pivot_y", 0.5),
            anchored_x=data.get("anchored_x", 0.0),
            anchored_y=data.get("anchored_y", 0.0),
            width=data.get("width", 100.0),
            height=data.get("height", 40.0),
            rotation=data.get("rotation", 0.0),
            scale_x=data.get("scale_x", 1.0),
            scale_y=data.get("scale_y", 1.0),
            layout_mode=data.get("layout_mode", "free"),
            layout_order=data.get("layout_order", 0),
            layout_ignore=data.get("layout_ignore", False),
            size_mode_x=data.get("size_mode_x", "fixed"),
            size_mode_y=data.get("size_mode_y", "fixed"),
            layout_align=data.get("layout_align", "start"),
            padding_left=data.get("padding_left", 0.0),
            padding_top=data.get("padding_top", 0.0),
            padding_right=data.get("padding_right", 0.0),
            padding_bottom=data.get("padding_bottom", 0.0),
            spacing=data.get("spacing", 0.0),
            focus_mode=data.get("focus_mode", "none"),
            mouse_filter=data.get("mouse_filter", "pass"),
            focusable=data.get("focusable", False),
            grid_columns=data.get("grid_columns", 2),
            grid_rows=data.get("grid_rows", 1),
            flow_direction=data.get("flow_direction", "horizontal"),
            aspect_ratio=data.get("aspect_ratio", 1.0),
            aspect_stretch_mode=data.get("aspect_stretch_mode", "fit"),
        )
