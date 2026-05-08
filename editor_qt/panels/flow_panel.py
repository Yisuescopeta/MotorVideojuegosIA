"""Qt scene-flow panel with canvas and table views."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from editor_qt.panels.flow_canvas import FlowCanvasWidget


class FlowPanel(QWidget):
    """Editable view over active scene_flow connections with canvas + table."""

    connection_set_requested = Signal(str, str)
    refresh_requested = Signal()

    def __init__(self, title: str = "Scene Flow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("PanelTitle")
        self.status_label = QLabel("No scene flow loaded")
        self.status_label.setObjectName("PanelSubtitle")

        # Flow canvas
        self._canvas = FlowCanvasWidget()

        # Table (secondary view, kept for backward compat)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Key", "Target Scene"])
        self.table.horizontalHeader().setStretchLastSection(True)

        self.add_button = QPushButton("Add")
        self.apply_button = QPushButton("Apply")
        self.refresh_button = QPushButton("Refresh")

        buttons = QHBoxLayout()
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.title_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self._canvas, stretch=2)
        layout.addWidget(self.table, stretch=1)
        layout.addLayout(buttons)

        self.add_button.clicked.connect(self._add_row)
        self.apply_button.clicked.connect(self._apply_current)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)

        # Forward canvas signals
        self._canvas.node_position_changed.connect(self._on_node_moved)
        self._canvas.connection_created.connect(self._on_connection_created)
        self._canvas.refresh_requested.connect(self.refresh_requested.emit)

    def set_flow_data(
        self,
        connections: list[dict[str, str]],
        scenes: list[dict[str, Any]],
        flow_graph: dict[str, Any] | None = None,
    ) -> None:
        # Table (backward compat)
        self.table.setRowCount(0)
        for row_data in connections:
            self._append_row(str(row_data.get("key") or ""), str(row_data.get("target") or ""))
        self.status_label.setText(f"{len(connections)} connections | {len(scenes)} scenes")
        if self.table.rowCount() == 0:
            self._append_row("next_scene", "")

        # Canvas
        if flow_graph:
            self._canvas.set_flow_data(flow_graph, scenes)

    def _on_node_moved(self, node_key: str, x: float, y: float) -> None:
        """Handle node position changes from canvas (placeholder)."""

    def _on_connection_created(self, source_key: str, target: str) -> None:
        """Handle new SceneLink creation request from canvas."""
        if source_key:
            self.connection_set_requested.emit(source_key, target)

    def _add_row(self) -> None:
        self._append_row("", "")
        self.table.setCurrentCell(self.table.rowCount() - 1, 0)

    def _append_row(self, key: str, target: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        key_item = QTableWidgetItem(key)
        target_item = QTableWidgetItem(target)
        key_item.setFlags(key_item.flags() | Qt.ItemFlag.ItemIsEditable)
        target_item.setFlags(target_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 0, key_item)
        self.table.setItem(row, 1, target_item)

    def _apply_current(self) -> None:
        row = self.table.currentRow()
        if row < 0 and self.table.rowCount() > 0:
            row = 0
        if row < 0:
            return
        key_item = self.table.item(row, 0)
        target_item = self.table.item(row, 1)
        key = key_item.text().strip() if key_item is not None else ""
        target = target_item.text().strip() if target_item is not None else ""
        if key:
            self.connection_set_requested.emit(key, target)
