"""Hierarchy panel for the Qt editor."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

_logger = logging.getLogger(__name__)


class HierarchyTreeWidget(QTreeWidget):
    """QTreeWidget with drag-drop reparenting support."""

    reparent_requested = Signal(str, str)  # child_name, new_parent_name

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dropEvent(self, event: QDropEvent) -> None:
        target_item = self.itemAt(event.position().toPoint())
        dragged_items = self.selectedItems()

        if not dragged_items or target_item is None:
            event.ignore()
            return

        dragged_item = dragged_items[0]
        dragged_name = str(dragged_item.data(0, Qt.ItemDataRole.UserRole) or "")
        target_name = str(target_item.data(0, Qt.ItemDataRole.UserRole) or "")

        if not dragged_name or not target_name:
            event.ignore()
            return
        if dragged_item is target_item:
            event.ignore()
            return
        if self._is_descendant(dragged_item, target_item):
            event.ignore()
            return

        current_parent = dragged_item.parent()
        current_parent_name = ""
        if current_parent is not None:
            current_parent_name = str(
                current_parent.data(0, Qt.ItemDataRole.UserRole) or ""
            )
        if current_parent_name == target_name:
            event.ignore()
            return

        super().dropEvent(event)
        if event.isAccepted():
            self.reparent_requested.emit(dragged_name, target_name)

    def _is_descendant(
        self, ancestor: QTreeWidgetItem, item: QTreeWidgetItem
    ) -> bool:
        """Return True if *item* exists anywhere in the subtree of *ancestor*."""
        for i in range(ancestor.childCount()):
            child = ancestor.child(i)
            if child is item:
                return True
            if self._is_descendant(child, item):
                return True
        return False


class HierarchyPanel(QWidget):
    """Panel showing the entity hierarchy with drag-drop reparenting."""

    entity_selected = Signal(str)
    entity_create_requested = Signal(str)
    entity_delete_requested = Signal(str)
    entity_create_child_requested = Signal(str, str)  # parent_name, child_name
    entity_duplicate_requested = Signal(str)  # entity_name
    entity_reparent_requested = Signal(str, str)  # child_name, new_parent_name
    entity_active_set_requested = Signal(str, bool)  # entity_name, active

    def __init__(
        self, facade: Any | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("HierarchyPanel")
        self.facade = facade
        self._entities: list[dict[str, Any]] = []
        self._loading = False
        self._expanded_names: set[str] = set()

        self.title_label = QLabel("HIERARCHY")
        self.title_label.setObjectName("PanelTitle")
        self.header_button = QPushButton("...")
        self.header_button.setObjectName("PanelMenuButton")
        self.header_button.setEnabled(False)
        self.header_button.setToolTip("Panel menu is not wired in the Qt editor yet.")
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchField")
        self.search_input.setPlaceholderText("Search...")
        self.create_button = QPushButton("+")
        self.create_button.setObjectName("HierarchyAddButton")
        self.create_button.setFixedWidth(30)
        self.delete_button = QPushButton("Delete")
        self.refresh_button = QPushButton("Refresh")
        self.tree = HierarchyTreeWidget()
        self.tree.setObjectName("HierarchyTree")
        self.tree.setHeaderLabels(["Entity", "Visible"])
        self.tree.setHeaderHidden(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.header_button)
        layout.addWidget(header)

        search_row = QWidget()
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(6)
        search_layout.addWidget(self.search_input, stretch=1)
        search_layout.addWidget(self.create_button)
        layout.addWidget(search_row)
        toolbar_widget = QWidget()
        toolbar_widget.setObjectName("PanelToolbar")
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)
        toolbar.addWidget(self.delete_button)
        toolbar.addWidget(self.refresh_button)
        toolbar_widget.setLayout(toolbar)
        layout.addWidget(toolbar_widget)
        layout.addWidget(self.tree)

        self.search_input.textChanged.connect(self._apply_filter)
        self.create_button.clicked.connect(self._request_create_entity)
        self.delete_button.clicked.connect(self._request_delete_entity)
        self.refresh_button.clicked.connect(self.refresh)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemExpanded.connect(self._remember_expanded_item)
        self.tree.itemCollapsed.connect(self._forget_expanded_item)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.reparent_requested.connect(self.entity_reparent_requested.emit)

    # ── refresh ────────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        selected_name = self.selected_entity_name()
        expanded_names = self._collect_expanded_names() or set(self._expanded_names)
        self._loading = True
        self.tree.clear()
        entities = self._entities
        if not entities and self.facade is not None:
            entities = self.facade.list_entities()
        if not entities:
            empty = QTreeWidgetItem(["No entities"])
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.tree.addTopLevelItem(empty)
            self._loading = False
            return

        items: dict[str, QTreeWidgetItem] = {}
        entity_by_name: dict[str, dict[str, Any]] = {}
        for entity in entities:
            name = str(entity.get("name", "")).strip()
            if not name:
                continue
            item = QTreeWidgetItem([name])
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsDropEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setData(0, Qt.ItemDataRole.UserRole, name)
            item.setData(1, Qt.ItemDataRole.UserRole, name)
            item.setCheckState(
                1,
                Qt.CheckState.Checked if bool(entity.get("active", True)) else Qt.CheckState.Unchecked,
            )
            items[name] = item
            entity_by_name[name] = entity

        for name, item in items.items():
            parent_name = str(entity_by_name[name].get("parent") or "")
            parent_item = items.get(parent_name)
            if parent_item is not None:
                parent_item.addChild(item)
            else:
                self.tree.addTopLevelItem(item)

        if expanded_names:
            for name, item in items.items():
                item.setExpanded(name in expanded_names)
        else:
            self.tree.expandAll()
        if selected_name and selected_name in items:
            self.tree.setCurrentItem(items[selected_name])
        self._loading = False
        self._apply_filter()

    def set_entities(self, entities: list[dict[str, Any]]) -> None:
        self._entities = [dict(entity) for entity in entities if isinstance(entity, dict)]
        self.refresh()

    # ── selection ──────────────────────────────────────────────────────────────

    def _on_selection_changed(self) -> None:
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return
        entity_name = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
        if entity_name:
            self.entity_selected.emit(str(entity_name))

    def selected_entity_name(self) -> str:
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return ""
        entity_name = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
        return str(entity_name or "")

    def set_search_text(self, text: str) -> None:
        self.search_input.setText(text)

    def _apply_filter(self) -> None:
        needle = self.search_input.text().strip().lower()
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item is not None:
                self._filter_item(item, needle)

    def _filter_item(self, item: QTreeWidgetItem, needle: str) -> bool:
        entity_name = str(item.data(0, Qt.ItemDataRole.UserRole) or item.text(0))
        self_match = not needle or needle in entity_name.lower()
        child_match = False
        for index in range(item.childCount()):
            child_match = self._filter_item(item.child(index), needle) or child_match
        visible = self_match or child_match
        item.setHidden(not visible)
        return visible

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._loading or column != 1:
            return
        entity_name = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
        if entity_name:
            self.entity_active_set_requested.emit(
                entity_name,
                item.checkState(1) == Qt.CheckState.Checked,
            )

    def _remember_expanded_item(self, item: QTreeWidgetItem) -> None:
        entity_name = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
        if entity_name:
            self._expanded_names.add(entity_name)

    def _forget_expanded_item(self, item: QTreeWidgetItem) -> None:
        entity_name = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
        if entity_name:
            self._expanded_names.discard(entity_name)

    def _collect_expanded_names(self) -> set[str]:
        names: set[str] = set()

        def visit(item: QTreeWidgetItem) -> None:
            entity_name = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
            if entity_name and item.isExpanded():
                names.add(entity_name)
            for child_index in range(item.childCount()):
                visit(item.child(child_index))

        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item is not None:
                visit(item)
        return names

    # ── button handlers ────────────────────────────────────────────────────────

    def _request_create_entity(self) -> None:
        name, accepted = QInputDialog.getText(self, "Create Entity", "Entity name:")
        entity_name = str(name).strip()
        if accepted and entity_name:
            self.entity_create_requested.emit(entity_name)

    def _request_delete_entity(self) -> None:
        entity_name = self.selected_entity_name()
        if entity_name:
            self.entity_delete_requested.emit(entity_name)

    # ── context menu ───────────────────────────────────────────────────────────

    def _on_context_menu(self, point: Any) -> None:
        item = self.tree.itemAt(point)
        menu = QMenu(self)

        create_action = menu.addAction("Create Entity")
        create_action.triggered.connect(self._request_create_entity)

        if item is not None:
            entity_name = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
            if entity_name:
                create_child_action = menu.addAction("Create Child Entity")
                create_child_action.triggered.connect(
                    lambda n=entity_name: self._request_create_child(n)
                )

                menu.addSeparator()

                delete_action = menu.addAction("Delete Entity")
                delete_action.triggered.connect(
                    lambda n=entity_name: self.entity_delete_requested.emit(n)
                )

                duplicate_action = menu.addAction("Duplicate Entity")
                duplicate_action.triggered.connect(
                    lambda n=entity_name: self.entity_duplicate_requested.emit(n)
                )

                if item.parent() is not None:
                    unparent_action = menu.addAction("Unparent")
                    unparent_action.triggered.connect(
                        lambda n=entity_name: self.entity_reparent_requested.emit(n, "")
                    )

                menu.addSeparator()

                prefab_action = menu.addAction("Save as Prefab")
                prefab_action.triggered.connect(
                    lambda n=entity_name: self._save_as_prefab(n)
                )

        menu.exec(self.tree.viewport().mapToGlobal(point))

    def _request_create_child(self, parent_name: str) -> None:
        name, accepted = QInputDialog.getText(
            self, "Create Child Entity", f"Child entity name under '{parent_name}':"
        )
        child_name = str(name).strip()
        if accepted and child_name:
            self.entity_create_child_requested.emit(parent_name, child_name)

    def _save_as_prefab(self, entity_name: str) -> None:
        _logger.info("Save as Prefab requested for: %s (stub)", entity_name)
