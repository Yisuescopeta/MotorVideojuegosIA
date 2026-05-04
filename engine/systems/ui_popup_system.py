"""
engine/systems/ui_popup_system.py - Popup/PopupMenu/Window interaction and layout.
"""

from __future__ import annotations

from typing import Any, Optional

import pyray as rl
from engine.components.ui_popup import UIPopup, UIPopupMenu, UIWindow
from engine.ecs.entity import Entity
from engine.ecs.world import World


class UIPopupSystem:
    """Processes UIPopup, UIPopupMenu, and UIWindow interactions."""

    def __init__(self) -> None:
        self._popup_blocking: bool = False
        self._visible_popups: list[Entity] = []
        self._visible_menus: list[Entity] = []
        self._visible_windows: list[Entity] = []
        self._interaction_enabled_resolver: Any = None

    def set_interaction_enabled_resolver(self, callback: Any) -> None:
        self._interaction_enabled_resolver = callback

    def get_popup_blocking(self) -> bool:
        return self._popup_blocking

    def get_visible_popups(self) -> list[Entity]:
        return list(self._visible_popups)

    def get_visible_menus(self) -> list[Entity]:
        return list(self._visible_menus)

    def get_visible_windows(self) -> list[Entity]:
        return list(self._visible_windows)

    def update(self, world: World, layouts: dict[str, dict[str, Any]]) -> None:
        self._visible_popups.clear()
        self._visible_menus.clear()
        self._visible_windows.clear()
        self._popup_blocking = False

        for entity in world.get_entities_with(UIPopup):
            popup = entity.get_component(UIPopup)
            if popup is None or not popup.visible:
                continue
            self._visible_popups.append(entity)
            if popup.popup_exclusive:
                self._popup_blocking = True

        for entity in world.get_entities_with(UIPopupMenu):
            menu = entity.get_component(UIPopupMenu)
            if menu is None or not menu.visible:
                continue
            self._visible_menus.append(entity)

        for entity in world.get_entities_with(UIWindow):
            window = entity.get_component(UIWindow)
            if window is None or not window.visible:
                continue
            self._visible_windows.append(entity)

        self._process_menus(layouts)
        self._process_windows(layouts)

    def handle_click(
        self,
        world: World,
        x: float,
        y: float,
        layouts: dict[str, dict[str, Any]],
        pressed: bool,
        released: bool,
        down: bool,
    ) -> bool:
        """Returns True if click was consumed by a popup/menu/window."""
        consumed = False

        # Windows: handle dragging and close button
        for entity in self._visible_windows:
            window = entity.get_component(UIWindow)
            layout = layouts.get(entity.name)
            if window is None or layout is None:
                continue

            lx = float(layout["x"])
            ly = float(layout["y"])
            lw = float(layout["width"])
            lh = float(layout["height"])

            # Close button hit
            close_x = lx + lw - window._close_button_width
            if pressed and x >= close_x and x <= lx + lw and y >= ly and y <= ly + window._title_bar_height:
                window.visible = False
                return True

            # Title bar dragging
            if pressed and x >= lx and x <= lx + lw and y >= ly and y <= ly + window._title_bar_height:
                window._dragging = True
                window._drag_offset_x = x - lx
                window._drag_offset_y = y - ly
                consumed = True

            if window._dragging and down:
                new_x = x - window._drag_offset_x
                new_y = y - window._drag_offset_y
                layout["x"] = new_x
                layout["y"] = new_y
                consumed = True

            if released:
                window._dragging = False

            # Any click inside window consumes
            if pressed and self._point_in_layout(x, y, layout):
                consumed = True

        # PopupMenu item clicks
        for entity in self._visible_menus:
            menu = entity.get_component(UIPopupMenu)
            if menu is None:
                continue
            if pressed and menu._hovered_index >= 0 and menu._hovered_index < len(menu.items):
                item = menu.items[menu._hovered_index]
                if not item.get("separator", False):
                    menu._selected_id = item.get("id", -1)
                    menu.visible = False
                    return True

            if pressed and self._is_inside_menu(x, y, menu):
                consumed = True

        # Popup exclusive: click outside closes
        if pressed and self._popup_blocking:
            inside_popup = False
            for entity in self._visible_popups:
                layout = layouts.get(entity.name)
                if layout and self._point_in_layout(x, y, layout):
                    inside_popup = True
                    break
            if not inside_popup:
                for entity in self._visible_popups:
                    popup = entity.get_component(UIPopup)
                    if popup and popup.popup_exclusive:
                        popup.visible = False
            consumed = True

        return consumed

    def get_selected_menu_id(self, entity: Entity) -> int:
        menu = entity.get_component(UIPopupMenu)
        if menu is None:
            return -1
        sid = menu._selected_id
        menu._selected_id = -1
        return sid

    def _process_menus(self, layouts: dict[str, dict[str, Any]]) -> None:
        for entity in self._visible_menus:
            menu = entity.get_component(UIPopupMenu)
            layout = layouts.get(entity.name)
            if menu is None or layout is None:
                continue
            px = float(layout["x"]) + menu.popup_position_x
            py = float(layout["y"]) + menu.popup_position_y
            w = float(layout["width"])
            menu._hovered_index = -1
            mouse = rl.get_mouse_position()
            item_y = py
            for i, item in enumerate(menu.items):
                ih = 4.0 if item.get("separator") else menu._item_height
                if (
                    mouse.x >= px
                    and mouse.x <= px + w
                    and mouse.y >= item_y
                    and mouse.y <= item_y + ih
                ):
                    menu._hovered_index = i
                item_y += ih

    def _process_windows(self, layouts: dict[str, dict[str, Any]]) -> None:
        pass

    def _is_inside_menu(self, x: float, y: float, menu: UIPopupMenu) -> bool:
        # menu position is stored in layout + popup offset
        return False  # handled by handle_click checking layout rect

    def _point_in_layout(self, x: float, y: float, layout: dict[str, Any]) -> bool:
        return (
            x >= float(layout["x"])
            and x <= float(layout["x"]) + float(layout["width"])
            and y >= float(layout["y"])
            and y <= float(layout["y"]) + float(layout["height"])
        )
