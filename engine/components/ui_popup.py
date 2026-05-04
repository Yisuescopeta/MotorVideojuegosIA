"""
engine/components/ui_popup.py - Popup, PopupMenu, Window UI components (adaptado Godot).
"""

from __future__ import annotations

import copy
from typing import Any, Union

from engine.ecs.component import Component


def _color_tuple(value: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    r, g, b, a = value
    return (int(r), int(g), int(b), int(a))


class UIPopup(Component):
    """Godot Popup — modal overlay that appears on top."""

    def __init__(
        self,
        visible: bool = False,
        popup_exclusive: bool = True,
        transparent_background: bool = False,
    ) -> None:
        self.visible = visible
        self.popup_exclusive = bool(popup_exclusive)
        self.transparent_background = bool(transparent_background)
        self._overlay_color: tuple[int, int, int, int] = (0, 0, 0, 160)

    def to_dict(self) -> dict[str, Any]:
        return {
            "visible": self.visible,
            "popup_exclusive": self.popup_exclusive,
            "transparent_background": self.transparent_background,
            "overlay_color": list(self._overlay_color),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIPopup":
        instance = cls(
            visible=data.get("visible", False),
            popup_exclusive=data.get("popup_exclusive", True),
            transparent_background=data.get("transparent_background", False),
        )
        instance._overlay_color = tuple(data.get("overlay_color", [0, 0, 0, 160]))  # type: ignore[arg-type]
        return instance


class UIPopupMenu(Component):
    """Godot PopupMenu — popup with menu items."""

    def __init__(
        self,
        visible: bool = False,
        items: list[dict[str, Any]] | None = None,
        popup_position_x: float = 0.0,
        popup_position_y: float = 0.0,
    ) -> None:
        self.visible = visible
        self.items: list[dict[str, Any]] = copy.deepcopy(items or [])
        self.popup_position_x = float(popup_position_x)
        self.popup_position_y = float(popup_position_y)
        # Runtime
        self._item_height: float = 28.0
        self._hovered_index: int = -1
        self._selected_id: int = -1

    def add_item(self, text: str, item_id: int = -1, separator: bool = False) -> None:
        rid = item_id if item_id >= 0 else len(self.items)
        self.items.append({"text": str(text), "id": rid, "separator": bool(separator)})

    def add_separator(self) -> None:
        self.items.append({"text": "", "id": -1, "separator": True})

    def clear(self) -> None:
        self.items.clear()
        self._hovered_index = -1
        self._selected_id = -1

    def to_dict(self) -> dict[str, Any]:
        return {
            "visible": self.visible,
            "items": copy.deepcopy(self.items),
            "popup_position_x": self.popup_position_x,
            "popup_position_y": self.popup_position_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIPopupMenu":
        return cls(
            visible=data.get("visible", False),
            items=copy.deepcopy(data.get("items", [])),
            popup_position_x=data.get("popup_position_x", 0.0),
            popup_position_y=data.get("popup_position_y", 0.0),
        )


class UIWindow(Component):
    """Godot Window — draggable window dialog."""

    def __init__(
        self,
        visible: bool = True,
        title: str = "Window",
        resizable: bool = False,
        wrap_controls: bool = False,
        transient: bool = False,
    ) -> None:
        self.visible = visible
        self.title = str(title)
        self.resizable = bool(resizable)
        self.wrap_controls = bool(wrap_controls)
        self.transient = bool(transient)
        self._title_bar_height: float = 28.0
        self._close_button_width: float = 26.0
        self._dragging: bool = False
        self._drag_offset_x: float = 0.0
        self._drag_offset_y: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "visible": self.visible,
            "title": self.title,
            "resizable": self.resizable,
            "wrap_controls": self.wrap_controls,
            "transient": self.transient,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UIWindow":
        return cls(
            visible=data.get("visible", True),
            title=data.get("title", "Window"),
            resizable=data.get("resizable", False),
            wrap_controls=data.get("wrap_controls", False),
            transient=data.get("transient", False),
        )
