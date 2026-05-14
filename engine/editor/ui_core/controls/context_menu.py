"""Pure context menu model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from engine.editor.ui_core.controls.popup import PopupModel


@dataclass
class ContextMenuItem:
    """Serializable context menu item, including optional submenu children."""

    id: str
    label: str
    enabled: bool = True
    separator: bool = False
    checked: bool = False
    shortcut: str = ""
    children: list["ContextMenuItem"] = field(default_factory=list)
    schema_version: int = 1

    @property
    def selectable(self) -> bool:
        return self.enabled and not self.separator and bool(self.id)

    @property
    def has_submenu(self) -> bool:
        return self.enabled and bool(self.children)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ContextMenuItem":
        """Build item from serialized menu data."""

        payload: dict[str, Any] = dict(data)
        payload["children"] = [cls.from_dict(child) for child in payload.get("children", [])]
        return cls(**payload)


@dataclass
class ContextMenuModel:
    """Serializable context menu state with pure navigation/activation logic."""

    items: list[ContextMenuItem] = field(default_factory=list)
    popup: PopupModel = field(default_factory=PopupModel)
    highlighted_index: int = -1
    item_height: float = 22.0
    min_width: float = 160.0
    selected_id: str | None = None
    child_menu: "ContextMenuModel | None" = None
    child_index: int = -1
    schema_version: int = 1

    def open_at(self, x: float, y: float) -> None:
        """Open menu at screen position and highlight first selectable item."""

        self.selected_id = None
        self.highlighted_index = self._first_selectable_index()
        self.popup.open((float(x), float(y), self.min_width, self.preferred_height()))

    def close(self) -> None:
        if self.child_menu is not None:
            self.child_menu.close()
        self.popup.close()
        self.highlighted_index = -1
        self.child_menu = None
        self.child_index = -1

    def preferred_height(self) -> float:
        return max(0.0, len(self.items) * self.item_height)

    def item_at(self, x: float, y: float) -> ContextMenuItem | None:
        if not self.popup.contains_point(x, y) or self.item_height <= 0:
            return None
        _, py, _, _ = self.popup.rect
        index = int((y - py) // self.item_height)
        if 0 <= index < len(self.items):
            return self.items[index]
        return None

    def highlight_at(self, x: float, y: float) -> int:
        item = self.item_at(x, y)
        if item is None:
            self.highlighted_index = -1
            return -1
        index = self.items.index(item)
        self.highlighted_index = index if item.selectable else -1
        if item.has_submenu:
            self.open_submenu(index)
        elif self.child_menu is not None and index != self.child_index:
            self.child_menu.close()
            self.child_menu = None
            self.child_index = -1
        return self.highlighted_index

    def move_highlight(self, delta: int) -> int:
        """Move keyboard highlight across selectable items."""

        selectable = [idx for idx, item in enumerate(self.items) if item.selectable]
        if not selectable:
            self.highlighted_index = -1
            return -1
        if self.highlighted_index not in selectable:
            self.highlighted_index = selectable[0]
            return self.highlighted_index
        pos = selectable.index(self.highlighted_index)
        self.highlighted_index = selectable[(pos + int(delta)) % len(selectable)]
        return self.highlighted_index

    def activate_highlighted(self) -> str | None:
        if not (0 <= self.highlighted_index < len(self.items)):
            return None
        item = self.items[self.highlighted_index]
        if not item.selectable:
            return None
        if item.has_submenu:
            self.open_submenu(self.highlighted_index)
            return None
        self.selected_id = item.id
        self.close()
        return item.id

    def activate_at(self, x: float, y: float) -> str | None:
        """Activate item under point, including open child menus."""

        if self.child_menu is not None and self.child_menu.popup.contains_point(x, y):
            action_id = self.child_menu.activate_at(x, y)
            if action_id is not None:
                self.selected_id = action_id
                self.close()
            return action_id
        self.highlight_at(x, y)
        return self.activate_highlighted()

    def open_submenu(self, index: int) -> "ContextMenuModel | None":
        """Open submenu for item index when children exist."""

        if not (0 <= index < len(self.items)):
            return None
        item = self.items[index]
        if not item.has_submenu:
            return None
        x, y, w, _ = self.popup.rect
        child = ContextMenuModel(items=list(item.children), item_height=self.item_height, min_width=self.min_width)
        child.open_at(x + w, y + index * self.item_height)
        self.child_menu = child
        self.child_index = index
        return child

    def to_dict(self) -> dict[str, object]:
        """Serialize menu state to JSON-compatible primitives."""

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ContextMenuModel":
        """Build menu state from a `to_dict()` payload."""

        payload: dict[str, Any] = dict(data)
        payload["items"] = [ContextMenuItem.from_dict(item) for item in payload.get("items", [])]
        popup = payload.get("popup")
        payload["popup"] = PopupModel.from_dict(popup) if isinstance(popup, dict) else PopupModel()
        child = payload.get("child_menu")
        payload["child_menu"] = cls.from_dict(child) if isinstance(child, dict) else None
        return cls(**payload)

    def _first_selectable_index(self) -> int:
        for idx, item in enumerate(self.items):
            if item.selectable:
                return idx
        return -1


def context_menu_from_tuples(items: list[tuple[str, str]]) -> ContextMenuModel:
    """Create menu from `(id, label)` pairs."""

    return ContextMenuModel([ContextMenuItem(id=item_id, label=label) for item_id, label in items])


@dataclass
class ContextMenuManager:
    """Lifecycle manager for one active root context menu."""

    root: ContextMenuModel | None = None

    def open(self, menu: ContextMenuModel, x: float, y: float) -> ContextMenuModel:
        if self.root is not None:
            self.root.close()
        self.root = menu
        self.root.open_at(x, y)
        return self.root

    def close(self) -> None:
        if self.root is not None:
            self.root.close()
        self.root = None

    def activate_at(self, x: float, y: float) -> str | None:
        if self.root is None:
            return None
        action_id = self.root.activate_at(x, y)
        if action_id is not None:
            self.root = None
        return action_id
