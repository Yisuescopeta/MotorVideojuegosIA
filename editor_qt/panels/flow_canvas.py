"""QGraphicsView-based scene flow canvas with nodes and edges."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


class FlowNodeItem(QGraphicsRectItem):
    """A node in the flow graph representing a scene entity or target."""

    def __init__(self, node_key: str, label: str, x: float, y: float, w: float = 160, h: float = 56):
        super().__init__(0, 0, w, h)
        self.node_key = node_key
        self.node_label = label
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setBrush(QBrush(QColor(46, 46, 46)))
        self.setPen(QPen(QColor(80, 80, 80), 1))
        self.setZValue(10)

        # Label
        self._text = QGraphicsTextItem(self.truncate(label, 20), self)
        self._text.setDefaultTextColor(QColor(220, 220, 220))
        self._text.setPos(8, 18)
        font = QFont()
        font.setPixelSize(11)
        self._text.setFont(font)

        # Connector circles
        r = 6
        self._conn_left = QGraphicsEllipseItem(-r, h / 2 - r, r * 2, r * 2, self)
        self._conn_left.setBrush(QBrush(QColor(58, 121, 187)))
        self._conn_left.setPen(QPen(QColor(100, 160, 220)))

        self._conn_right = QGraphicsEllipseItem(w - r, h / 2 - r, r * 2, r * 2, self)
        self._conn_right.setBrush(QBrush(QColor(58, 121, 187)))
        self._conn_right.setPen(QPen(QColor(100, 160, 220)))

    @staticmethod
    def truncate(text: str, max_len: int) -> str:
        return text if len(text) <= max_len else text[:max_len - 3] + "..."

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self.scene() and hasattr(self.scene(), 'node_moved'):
                self.scene().node_moved.emit(self.node_key, value.x(), value.y())
        return super().itemChange(change, value)


class FlowEdgeItem(QGraphicsLineItem):
    """A directed edge between two flow nodes."""

    def __init__(self, source_key: str, target_key: str, x1: float, y1: float, x2: float, y2: float):
        super().__init__(x1, y1, x2, y2)
        self.source_key = source_key
        self.target_key = target_key
        self.setPen(QPen(QColor(255, 109, 18), 2))
        self.setZValue(5)

        self.setOpacity(0.85)


class FlowScene(QGraphicsScene):
    """Scene that holds flow nodes and edges, emits signals for interaction."""

    node_moved = Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-2000, -2000, 4000, 4000)
        self._nodes: dict[str, FlowNodeItem] = {}
        self._edges: list[FlowEdgeItem] = []

    def add_flow_node(self, node_key: str, label: str, x: float, y: float) -> FlowNodeItem:
        if node_key in self._nodes:
            return self._nodes[node_key]
        node = FlowNodeItem(node_key, label, x, y)
        self.addItem(node)
        self._nodes[node_key] = node
        return node

    def add_flow_edge(self, source_key: str, target_key: str) -> FlowEdgeItem | None:
        src = self._nodes.get(source_key)
        tgt = self._nodes.get(target_key)
        if not src or not tgt:
            return None
        src_center = src.sceneBoundingRect().center()
        tgt_center = tgt.sceneBoundingRect().center()
        edge = FlowEdgeItem(source_key, target_key,
                            src_center.x(), src_center.y(),
                            tgt_center.x(), tgt_center.y())
        self.addItem(edge)
        self._edges.append(edge)
        return edge

    def clear_flow(self) -> None:
        for edge in self._edges:
            self.removeItem(edge)
        self._edges.clear()
        for node in list(self._nodes.values()):
            self.removeItem(node)
        self._nodes.clear()


class FlowCanvasWidget(QWidget):
    """Top-level flow panel: sidebar + canvas + toolbar."""

    connection_created = Signal(str, str)  # source_key, target_key
    node_position_changed = Signal(str, float, float)  # node_key, x, y
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)

        # Toolbar
        self.title_label = QLabel("Scene Flow")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["One-way", "Two-way"])
        self.filter_check = QPushButton("Current Scene")
        self.filter_check.setCheckable(True)
        self.filter_check.setChecked(True)
        self.refresh_btn = QPushButton("Refresh")

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.title_label)
        toolbar.addStretch()
        toolbar.addWidget(self.mode_combo)
        toolbar.addWidget(self.filter_check)
        toolbar.addWidget(self.refresh_btn)
        toolbar.setContentsMargins(0, 0, 0, 0)

        # Scene
        self.scene = FlowScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.view.setBackgroundBrush(QBrush(QColor(32, 32, 32)))

        # Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setMaximumWidth(240)
        self.sidebar.setMinimumWidth(180)
        self.sidebar_label = QLabel("SceneLink Objects")

        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addWidget(self.sidebar_label)
        sidebar_layout.addWidget(self.sidebar)

        self.add_btn = QPushButton("Add SceneLink...")

        # Layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(sidebar_widget)
        splitter.addWidget(self.view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(toolbar)
        layout.addWidget(splitter, stretch=1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(self.add_btn)
        layout.addLayout(bottom)

        # Connections
        self.scene.node_moved.connect(self._on_node_moved)
        self.add_btn.clicked.connect(self._on_add_scene_link_clicked)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)

        self._scene_link_data: list[dict[str, Any]] = []
        self._scenes: list[dict[str, Any]] = []

    def set_flow_data(self, flow_graph: dict[str, Any], scenes: list[dict[str, Any]]) -> None:
        """flow_graph = dict with: sidebar_items, canvas_nodes, canvas_edges"""
        self._scenes = scenes
        self._scene_link_data = flow_graph.get("sidebar_items", [])

        # Populate sidebar
        self.sidebar.clear()
        for item in self._scene_link_data:
            entity = item.get("source_entity_name", "")
            scene = item.get("source_scene_name", "")
            label = f"{entity}\n{scene}" if scene else entity
            list_item = QListWidgetItem(label)
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.sidebar.addItem(list_item)

        # Populate canvas
        self.scene.clear_flow()
        for node in flow_graph.get("canvas_nodes", []):
            key = node.get("node_key", "")
            label = node.get("label", key)
            x = float(node.get("x", 0))
            y = float(node.get("y", 0))
            self.scene.add_flow_node(key, label, x, y)

        for edge in flow_graph.get("canvas_edges", []):
            src = edge.get("source_node_key", "")
            tgt = edge.get("target_node_key", "")
            if src and tgt:
                self.scene.add_flow_edge(src, tgt)

    def _on_node_moved(self, node_key: str, x: float, y: float) -> None:
        self.node_position_changed.emit(node_key, x, y)

    def _on_add_scene_link_clicked(self) -> None:
        """Simple add: create a new SceneLink entry via signal."""
        import uuid
        source_key = f"link_{uuid.uuid4().hex[:8]}"
        if self._scenes:
            self.connection_created.emit(source_key, self._scenes[0].get("path", ""))
        else:
            self.connection_created.emit(source_key, "")
