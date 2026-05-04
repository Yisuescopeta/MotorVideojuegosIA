"""
engine/components/ui_tree.py - UI Tree widget (Godot Tree).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class UITreeItem:
    """A single item in a UI Tree."""

    def __init__(
        self,
        text: str = "",
        icon_path: str = "",
        expandable: bool = False,
        expanded: bool = False,
        selected: bool = False,
        disabled: bool = False,
        checked: bool = False,
        checkable: bool = False,
    ) -> None:
        self.text: str = text
        self.icon_path: str = icon_path
        self.expandable: bool = expandable
        self.expanded: bool = expanded
        self.selected: bool = selected
        self.children: list[UITreeItem] = []
        self.metadata: dict[str, Any] = {}
        self.disabled: bool = disabled
        self.checked: bool = checked
        self.checkable: bool = checkable

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "icon_path": self.icon_path,
            "expandable": self.expandable,
            "expanded": self.expanded,
            "selected": self.selected,
            "children": [child.to_dict() for child in self.children],
            "metadata": self.metadata,
            "disabled": self.disabled,
            "checked": self.checked,
            "checkable": self.checkable,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UITreeItem:
        item = cls(
            text=str(data.get("text", "")),
            icon_path=str(data.get("icon_path", "")),
            expandable=bool(data.get("expandable", False)),
        )
        item.expanded = bool(data.get("expanded", False))
        item.selected = bool(data.get("selected", False))
        item.metadata = dict(data.get("metadata", {}))
        item.disabled = bool(data.get("disabled", False))
        item.checked = bool(data.get("checked", False))
        item.checkable = bool(data.get("checkable", False))
        item.children = [UITreeItem.from_dict(child) for child in data.get("children", [])]
        return item


class UITree(Component):
    """Godot Tree — hierarchical list widget."""

    VALID_SELECT_MODES = ("single", "multi", "row")

    def __init__(
        self,
        allow_reselect: bool = False,
        allow_rmb_select: bool = False,
        hide_root: bool = True,
        select_mode: str = "single",
        drop_mode_flags: int = 0,
        columns: int = 1,
        column_titles: list[str] | None = None,
        scroll_horizontal: bool = True,
        scroll_vertical: bool = True,
    ) -> None:
        self.enabled: bool = True
        self._root: UITreeItem = UITreeItem(text="root")
        self.allow_reselect: bool = bool(allow_reselect)
        self.allow_rmb_select: bool = bool(allow_rmb_select)
        self.hide_root: bool = bool(hide_root)
        self.select_mode: str = select_mode if select_mode in self.VALID_SELECT_MODES else "single"
        self.drop_mode_flags: int = int(drop_mode_flags)
        self.columns: int = max(1, int(columns))
        self.column_titles: list[str] = list(column_titles or [])
        self.scroll_horizontal: bool = bool(scroll_horizontal)
        self.scroll_vertical: bool = bool(scroll_vertical)
        self._selected_item: UITreeItem | None = None
        self._scroll_x: float = 0.0
        self._scroll_y: float = 0.0

    @property
    def root(self) -> UITreeItem:
        return self._root

    def create_item(self, parent: UITreeItem | None = None, index: int = -1) -> UITreeItem:
        item = UITreeItem()
        target = parent if parent is not None else self._root
        if index < 0 or index >= len(target.children):
            target.children.append(item)
        else:
            target.children.insert(index, item)
        return item

    def get_selected(self) -> UITreeItem | None:
        return self._selected_item

    def clear(self) -> None:
        self._root.children.clear()
        self._selected_item = None
        self._scroll_x = 0.0
        self._scroll_y = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "root": self._root.to_dict(),
            "allow_reselect": self.allow_reselect,
            "allow_rmb_select": self.allow_rmb_select,
            "hide_root": self.hide_root,
            "select_mode": self.select_mode,
            "drop_mode_flags": self.drop_mode_flags,
            "columns": self.columns,
            "column_titles": list(self.column_titles),
            "scroll_horizontal": self.scroll_horizontal,
            "scroll_vertical": self.scroll_vertical,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UITree:
        tree = cls(
            allow_reselect=bool(data.get("allow_reselect", False)),
            allow_rmb_select=bool(data.get("allow_rmb_select", False)),
            hide_root=bool(data.get("hide_root", True)),
            select_mode=str(data.get("select_mode", "single")),
            drop_mode_flags=int(data.get("drop_mode_flags", 0)),
            columns=int(data.get("columns", 1)),
            column_titles=list(data.get("column_titles", [])),
            scroll_horizontal=bool(data.get("scroll_horizontal", True)),
            scroll_vertical=bool(data.get("scroll_vertical", True)),
        )
        tree.enabled = bool(data.get("enabled", True))
        root_data = data.get("root", None)
        if isinstance(root_data, dict):
            tree._root = UITreeItem.from_dict(root_data)
        return tree
