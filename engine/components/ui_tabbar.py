"""
engine/components/ui_tabbar.py — TabBar y TabContainer UI (adaptado Godot TabBar / TabContainer).
"""

from __future__ import annotations

import copy
from typing import Any

from engine.ecs.component import Component


class UITabBar(Component):
    """Godot TabBar — row of clickable tabs."""

    def __init__(
        self,
        enabled: bool = True,
        tabs: list[dict[str, Any]] | None = None,
        current_tab: int = 0,
        tab_alignment: str = "left",
        scrollable: bool = False,
        tab_close_display_policy: str = "show_active_only",
    ) -> None:
        self.enabled = enabled
        self.tabs: list[dict[str, Any]] = copy.deepcopy(tabs or [])
        self.current_tab = int(current_tab)
        self.tab_alignment = str(tab_alignment or "left").strip().lower() or "left"
        self.scrollable = bool(scrollable)
        self.tab_close_display_policy = str(tab_close_display_policy or "show_active_only").strip().lower() or "show_active_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "tabs": copy.deepcopy(self.tabs),
            "current_tab": self.current_tab,
            "tab_alignment": self.tab_alignment,
            "scrollable": self.scrollable,
            "tab_close_display_policy": self.tab_close_display_policy,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UITabBar":
        return cls(
            enabled=data.get("enabled", True),
            tabs=data.get("tabs", []),
            current_tab=data.get("current_tab", 0),
            tab_alignment=data.get("tab_alignment", "left"),
            scrollable=data.get("scrollable", False),
            tab_close_display_policy=data.get("tab_close_display_policy", "show_active_only"),
        )


class UITabContainer(Component):
    """Godot TabContainer — container that shows one child at a time per tab."""

    def __init__(
        self,
        enabled: bool = True,
        current_tab: int = 0,
        tab_titles: list[dict[str, Any]] | None = None,
        use_hidden_tabs_for_min_size: bool = True,
        drag_to_rearrange_enabled: bool = False,
        all_tabs_in_front: bool = False,
    ) -> None:
        self.enabled = enabled
        self.current_tab = int(current_tab)
        self.tab_titles: list[dict[str, Any]] = copy.deepcopy(tab_titles or [])
        self.use_hidden_tabs_for_min_size = bool(use_hidden_tabs_for_min_size)
        self.drag_to_rearrange_enabled = bool(drag_to_rearrange_enabled)
        self.all_tabs_in_front = bool(all_tabs_in_front)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "current_tab": self.current_tab,
            "tab_titles": copy.deepcopy(self.tab_titles),
            "use_hidden_tabs_for_min_size": self.use_hidden_tabs_for_min_size,
            "drag_to_rearrange_enabled": self.drag_to_rearrange_enabled,
            "all_tabs_in_front": self.all_tabs_in_front,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UITabContainer":
        return cls(
            enabled=data.get("enabled", True),
            current_tab=data.get("current_tab", 0),
            tab_titles=data.get("tab_titles", []),
            use_hidden_tabs_for_min_size=data.get("use_hidden_tabs_for_min_size", True),
            drag_to_rearrange_enabled=data.get("drag_to_rearrange_enabled", False),
            all_tabs_in_front=data.get("all_tabs_in_front", False),
        )
