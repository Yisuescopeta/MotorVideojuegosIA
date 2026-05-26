"""Pure serializable docking model for editor panels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

DockDirection = Literal["horizontal", "vertical"]

MIN_SPLIT_RATIO = 0.1
MAX_SPLIT_RATIO = 0.9


def _clean_id(value: Any) -> str:
    return str(value or "").strip()


def normalize_ratio(value: Any, default: float = 0.5) -> float:
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        ratio = default
    return max(MIN_SPLIT_RATIO, min(MAX_SPLIT_RATIO, ratio))


@dataclass
class DockArea:
    id: str
    tabs: list[str] = field(default_factory=list)
    active_tab: str | None = None
    pinned: bool = True
    auto_hide: bool = False

    def __post_init__(self) -> None:
        self.id = _clean_id(self.id)
        self.tabs = [_clean_id(tab) for tab in self.tabs if _clean_id(tab)]
        if self.active_tab not in self.tabs:
            self.active_tab = self.tabs[0] if self.tabs else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "area",
            "id": self.id,
            "tabs": list(self.tabs),
            "active_tab": self.active_tab,
            "pinned": bool(self.pinned),
            "auto_hide": bool(self.auto_hide),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DockArea":
        if not isinstance(data, dict):
            raise ValueError("DockArea payload must be object")
        area_id = _clean_id(data.get("id"))
        raw_tabs = data.get("tabs", [])
        if not area_id or not isinstance(raw_tabs, list):
            raise ValueError("DockArea requires id and tabs")
        return cls(
            area_id,
            [_clean_id(tab) for tab in raw_tabs],
            _clean_id(data.get("active_tab")) or None,
            bool(data.get("pinned", True)),
            bool(data.get("auto_hide", False)),
        )


@dataclass
class FloatingDockWindow:
    tab_id: str
    x: float
    y: float
    width: float
    height: float
    is_open: bool = True

    def __post_init__(self) -> None:
        self.tab_id = _clean_id(self.tab_id)
        self.x = float(self.x)
        self.y = float(self.y)
        self.width = max(1.0, float(self.width))
        self.height = max(1.0, float(self.height))
        self.is_open = bool(self.is_open)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tab_id": self.tab_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "is_open": self.is_open,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FloatingDockWindow":
        if not isinstance(data, dict):
            raise ValueError("FloatingDockWindow payload must be object")
        tab_id = _clean_id(data.get("tab_id"))
        if not tab_id:
            raise ValueError("FloatingDockWindow requires tab_id")
        return cls(
            tab_id,
            data.get("x", 0.0),
            data.get("y", 0.0),
            data.get("width", 320.0),
            data.get("height", 240.0),
            bool(data.get("is_open", True)),
        )


@dataclass
class DockSplit:
    id: str
    direction: DockDirection
    ratio: float
    first: DockArea | DockSplit
    second: DockArea | DockSplit

    def __post_init__(self) -> None:
        self.id = _clean_id(self.id)
        if self.direction not in ("horizontal", "vertical"):
            self.direction = "horizontal"
        self.ratio = normalize_ratio(self.ratio)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "split",
            "id": self.id,
            "direction": self.direction,
            "ratio": self.ratio,
            "first": self.first.to_dict(),
            "second": self.second.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DockSplit":
        if not isinstance(data, dict):
            raise ValueError("DockSplit payload must be object")
        split_id = _clean_id(data.get("id"))
        if not split_id:
            raise ValueError("DockSplit requires id")
        return cls(
            split_id,
            data.get("direction", "horizontal"),
            normalize_ratio(data.get("ratio")),
            dock_node_from_dict(data.get("first")),
            dock_node_from_dict(data.get("second")),
        )


DockNode: TypeAlias = DockArea | DockSplit


def dock_node_from_dict(data: Any) -> DockNode:
    if not isinstance(data, dict):
        raise ValueError("Dock node must be object")
    node_type = data.get("type")
    if node_type == "area":
        return DockArea.from_dict(data)
    if node_type == "split":
        return DockSplit.from_dict(data)
    raise ValueError("Unknown dock node type")


@dataclass
class DockLayout:
    root: DockNode
    version: int = 1
    floating_windows: list[FloatingDockWindow] = field(default_factory=list)

    @classmethod
    def default(cls) -> "DockLayout":
        hierarchy = DockArea("hierarchy", ["HIERARCHY"], "HIERARCHY")
        center = DockArea("center", ["SCENE", "GAME", "FLOW", "ANIMATOR"], "SCENE")
        inspector = DockArea("inspector", ["INSPECTOR"], "INSPECTOR")
        bottom = DockArea("bottom", ["PROJECT", "FLOW_PANEL", "CONSOLE", "TERMINAL", "AGENT", "EXPORT", "ASSETS"], "PROJECT")
        center_and_inspector = DockSplit("main_right", "horizontal", 0.72, center, inspector)
        main = DockSplit("main", "horizontal", 0.18, hierarchy, center_and_inspector)
        root = DockSplit("root", "vertical", 0.74, main, bottom)
        return cls(root=root)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": int(self.version),
            "root": self.root.to_dict(),
            "floating_windows": [window.to_dict() for window in self.floating_windows],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "DockLayout":
        try:
            if not isinstance(data, dict):
                raise ValueError("DockLayout payload must be object")
            root = dock_node_from_dict(data.get("root"))
            raw_floating = data.get("floating_windows", [])
            floating_windows: list[FloatingDockWindow] = []
            if isinstance(raw_floating, list):
                for item in raw_floating:
                    try:
                        floating_windows.append(FloatingDockWindow.from_dict(item))
                    except Exception:
                        continue
            layout = cls(root=root, version=int(data.get("version", 1) or 1), floating_windows=floating_windows)
            if not layout.collect_areas():
                raise ValueError("DockLayout has no areas")
            return layout
        except Exception:
            return cls.default()

    def collect_areas(self) -> list[DockArea]:
        areas: list[DockArea] = []

        def visit(node: DockNode) -> None:
            if isinstance(node, DockArea):
                areas.append(node)
                return
            visit(node.first)
            visit(node.second)

        visit(self.root)
        return areas

    def find_area(self, area_id: str) -> DockArea | None:
        target = _clean_id(area_id)
        for area in self.collect_areas():
            if area.id == target:
                return area
        return None

    def find_tab_area(self, tab_id: str) -> DockArea | None:
        target = _clean_id(tab_id)
        for area in self.collect_areas():
            if target in area.tabs:
                return area
        return None

    def find_floating_window(self, tab_id: str) -> FloatingDockWindow | None:
        target = _clean_id(tab_id)
        for window in self.floating_windows:
            if window.tab_id == target:
                return window
        return None

    def active_tab(self, area_id: str) -> str | None:
        area = self.find_area(area_id)
        return area.active_tab if area is not None else None

    def set_active_tab(self, area_id: str, tab_id: str) -> bool:
        area = self.find_area(area_id)
        tab = _clean_id(tab_id)
        if area is None or tab not in area.tabs:
            return False
        area.active_tab = tab
        return True

    def move_tab(self, tab_id: str, target_area_id: str, index: int | None = None) -> bool:
        tab = _clean_id(tab_id)
        source = self.find_tab_area(tab)
        target = self.find_area(target_area_id)
        if not tab or source is None or target is None:
            return False
        if source is target:
            return self.reorder_tab(target.id, tab, 0 if index is None else index)
        source.tabs.remove(tab)
        if source.active_tab == tab:
            source.active_tab = source.tabs[0] if source.tabs else None
        insert_at = len(target.tabs) if index is None else max(0, min(int(index), len(target.tabs)))
        target.tabs.insert(insert_at, tab)
        target.active_tab = tab
        return True

    def float_tab(self, tab_id: str, from_area: str, rect: tuple[float, float, float, float]) -> bool:
        tab = _clean_id(tab_id)
        source = self.find_area(from_area)
        if not tab or source is None or tab not in source.tabs:
            return False
        try:
            x, y, width, height = rect
            window_rect = (float(x), float(y), max(1.0, float(width)), max(1.0, float(height)))
        except (TypeError, ValueError):
            return False
        source.tabs.remove(tab)
        if source.active_tab == tab:
            source.active_tab = source.tabs[0] if source.tabs else None
        window = self.find_floating_window(tab)
        if window is None:
            self.floating_windows.append(FloatingDockWindow(tab, *window_rect, True))
        else:
            window.x, window.y, window.width, window.height = window_rect
            window.is_open = True
        return True

    def dock_floating_tab(self, tab_id: str, to_area: str, position: int = -1) -> bool:
        tab = _clean_id(tab_id)
        window = self.find_floating_window(tab)
        target = self.find_area(to_area)
        if not tab or window is None or target is None:
            return False
        if tab not in target.tabs:
            insert_at = len(target.tabs) if position < 0 else max(0, min(int(position), len(target.tabs)))
            target.tabs.insert(insert_at, tab)
        target.active_tab = tab
        self.floating_windows.remove(window)
        return True

    def move_floating_window(self, tab_id: str, rect: tuple[float, float, float, float]) -> bool:
        window = self.find_floating_window(tab_id)
        if window is None:
            return False
        try:
            x, y, width, height = rect
            window.x = float(x)
            window.y = float(y)
            window.width = max(1.0, float(width))
            window.height = max(1.0, float(height))
        except (TypeError, ValueError):
            return False
        return True

    def close_floating_window(self, tab_id: str) -> bool:
        window = self.find_floating_window(tab_id)
        if window is None:
            return False
        window.is_open = False
        return True

    def set_area_pinned(self, area_id: str, pinned: bool) -> bool:
        area = self.find_area(area_id)
        if area is None:
            return False
        area.pinned = bool(pinned)
        return True

    def set_area_auto_hide(self, area_id: str, auto_hide: bool) -> bool:
        area = self.find_area(area_id)
        if area is None:
            return False
        area.auto_hide = bool(auto_hide)
        return True

    def reorder_tab(self, area_id: str, tab_id: str, index: int) -> bool:
        area = self.find_area(area_id)
        tab = _clean_id(tab_id)
        if area is None or tab not in area.tabs:
            return False
        area.tabs.remove(tab)
        insert_at = max(0, min(int(index), len(area.tabs)))
        area.tabs.insert(insert_at, tab)
        if area.active_tab not in area.tabs:
            area.active_tab = tab
        return True


__all__ = [
    "DockArea",
    "DockDirection",
    "DockLayout",
    "DockNode",
    "DockSplit",
    "FloatingDockWindow",
    "dock_node_from_dict",
    "normalize_ratio",
]
