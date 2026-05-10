"""Read-only project panel for scenes and assets."""

from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import QMimeData, Qt, QUrl, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class _DraggableTreeWidget(QTreeWidget):
    """QTreeWidget that emits asset_drag_started and sets custom mimeData for
    interop with the viewport."""

    asset_drag_started = Signal(str, str)  # file_path, asset_type

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        items = self.selectedItems()
        if not items:
            return

        item = items[0]
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        asset_type = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if file_path:
            self.asset_drag_started.emit(str(file_path), str(asset_type or ""))

        drag = QDrag(self)
        mime = QMimeData()
        if file_path:
            mime.setUrls([QUrl.fromLocalFile(str(file_path))])
            mime.setText(str(file_path))
        drag.setMimeData(mime)
        drag.exec(supportedActions)


class ProjectPanel(QWidget):
    scene_requested = Signal(str)
    asset_drag_started = Signal(str, str)  # file_path, asset_type
    sprite_editor_requested = Signal(str)  # asset_path
    scene_open_requested = Signal(str)  # scene_path

    _ASSET_TYPE_IMAGE = "image"
    _ASSET_TYPE_SCENE = "scene"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # ---- state ----
        self._all_assets: list[dict[str, Any]] = []
        self._current_folder: str = ""  # relative folder path, "" = root
        self._current_filter: str = "All"
        self._breadcrumb_stack: list[str] = []  # folder segments from root

        # ---- row 1: search + refresh ----
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search assets")

        self._refresh_btn = QPushButton("Refresh Assets")

        row1 = QHBoxLayout()
        row1.setSpacing(6)
        row1.addWidget(self._search_input, stretch=1)
        row1.addWidget(self._refresh_btn)

        # ---- row 2: filter buttons ----
        self._filter_buttons: dict[str, QPushButton] = {}
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        for label in ("All", "Images", "Scenes", "Prefabs", "Scripts"):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFlat(True)
            btn.setProperty("filterGroup", True)
            if label == "All":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, lbl=label: self._on_filter_clicked(lbl))
            self._filter_buttons[label] = btn
            row2.addWidget(btn)
        row2.addStretch()

        # ---- row 3: breadcrumb ----
        self._breadcrumb_layout = QHBoxLayout()
        self._breadcrumb_layout.setSpacing(2)
        self._breadcrumb_layout.setContentsMargins(0, 0, 0, 0)
        self._build_breadcrumb()

        # ---- left sidebar: folder tree ----
        self._folder_tree = QTreeWidget()
        self._folder_tree.setHeaderLabels(["Folders"])
        self._folder_tree.setMaximumWidth(180)
        project_root = QTreeWidgetItem(["Project"])
        project_root.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._folder_tree.addTopLevelItem(project_root)
        self._folder_tree.itemDoubleClicked.connect(self._on_folder_tree_double_clicked)

        # ---- right content: tab widget with draggable trees ----
        self.assets_tree = _DraggableTreeWidget()
        self.assets_tree.setHeaderLabels(["Assets"])
        self.assets_tree.setDragEnabled(True)
        self.assets_tree.asset_drag_started.connect(self.asset_drag_started.emit)
        self.assets_tree.itemDoubleClicked.connect(self._on_asset_item_double_clicked)
        self.assets_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)

        self.scenes_tree = _DraggableTreeWidget()
        self.scenes_tree.setHeaderLabels(["Scenes"])
        self.scenes_tree.setDragEnabled(True)
        self.scenes_tree.asset_drag_started.connect(self.asset_drag_started.emit)
        self.scenes_tree.itemDoubleClicked.connect(self._on_scene_activated)

        self.prefabs_tree = _DraggableTreeWidget()
        self.prefabs_tree.setHeaderLabels(["Prefabs"])
        self.prefabs_tree.setDragEnabled(True)
        self.prefabs_tree.asset_drag_started.connect(self.asset_drag_started.emit)

        self.scripts_tree = _DraggableTreeWidget()
        self.scripts_tree.setHeaderLabels(["Scripts"])
        self.scripts_tree.setDragEnabled(True)
        self.scripts_tree.asset_drag_started.connect(self.asset_drag_started.emit)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.assets_tree, "Assets")
        self.tabs.addTab(self.scenes_tree, "Scenes")
        self.tabs.addTab(self.prefabs_tree, "Prefabs")
        self.tabs.addTab(self.scripts_tree, "Scripts")

        # ---- content splitter: folder tree | tabs ----
        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_splitter.addWidget(self._folder_tree)
        content_splitter.addWidget(self.tabs)
        content_splitter.setStretchFactor(0, 0)
        content_splitter.setStretchFactor(1, 1)

        # ---- bottom: asset detail panel ----
        self._detail_container = QWidget()
        self._detail_container.setVisible(False)
        detail_layout = QVBoxLayout(self._detail_container)
        detail_layout.setContentsMargins(4, 4, 4, 4)
        detail_layout.setSpacing(4)

        self._detail_label = QLabel()
        self._detail_label.setWordWrap(True)
        self._detail_label.setObjectName("AssetDetailLabel")

        detail_buttons = QHBoxLayout()
        detail_buttons.setSpacing(6)
        self._sprite_editor_btn = QPushButton("Open Sprite Editor")
        self._sprite_editor_btn.clicked.connect(self._on_open_sprite_editor)
        self._sprite_editor_btn.setVisible(False)
        self._open_scene_btn = QPushButton("Open Scene")
        self._open_scene_btn.clicked.connect(self._on_open_scene_from_detail)
        self._open_scene_btn.setVisible(False)
        detail_buttons.addWidget(self._sprite_editor_btn)
        detail_buttons.addWidget(self._open_scene_btn)
        detail_buttons.addStretch()

        detail_layout.addWidget(self._detail_label)
        detail_layout.addLayout(detail_buttons)

        # ---- main splitter: content | detail ----
        self._main_splitter = QSplitter(Qt.Orientation.Vertical)
        self._main_splitter.addWidget(content_splitter)
        self._main_splitter.addWidget(self._detail_container)
        self._main_splitter.setStretchFactor(0, 3)
        self._main_splitter.setStretchFactor(1, 1)

        # ---- root layout ----
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addLayout(self._breadcrumb_layout)
        layout.addWidget(self._main_splitter, stretch=1)

        # ---- signal wiring ----
        self._search_input.textChanged.connect(self._apply_filter)
        self._refresh_btn.clicked.connect(self._apply_filter)
        self.assets_tree.currentItemChanged.connect(self._on_asset_selection_changed)
        self._current_detail_asset: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # public api
    # ------------------------------------------------------------------

    def set_project_data(
        self,
        project: dict[str, Any],
        active_scene: dict[str, Any],
        scenes: list[dict[str, Any]],
        assets: list[dict[str, Any]],
        scripts: list[str] | None = None,
        prefabs: list[str] | None = None,
    ) -> None:
        self._all_assets = assets
        self._populate_scenes(scenes, str(active_scene.get("path") or ""))
        self._populate_assets(assets)
        self._populate_paths(self.scripts_tree, scripts or [], "No scripts", "script")
        self._populate_paths(self.prefabs_tree, prefabs or [], "No prefabs", "prefab")
        self._rebuild_folder_tree(assets)
        self._apply_filter()

    # ------------------------------------------------------------------
    # internal populate helpers (kept compatible)
    # ------------------------------------------------------------------

    def _populate_scenes(self, scenes: list[dict[str, Any]], active_path: str) -> None:
        self.scenes_tree.clear()
        if not scenes:
            empty = QTreeWidgetItem(["No scenes"])
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.scenes_tree.addTopLevelItem(empty)
            return

        for scene in scenes:
            path = str(scene.get("path") or "")
            name = str(scene.get("name") or path or "Scene")
            # extract short name for display
            short_name = os.path.splitext(os.path.basename(path))[0] if path else name
            suffix = " *" if active_path and path == active_path else ""
            item = QTreeWidgetItem([f"{short_name}{suffix}"])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, "scene")
            self.scenes_tree.addTopLevelItem(item)

    def _populate_assets(self, assets: list[dict[str, Any]]) -> None:
        self.assets_tree.clear()
        if not assets:
            empty = QTreeWidgetItem(["No assets"])
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.assets_tree.addTopLevelItem(empty)
            return

        for asset in assets:
            path = str(asset.get("path") or "")
            name = str(asset.get("name") or path or "Asset")
            asset_type = str(asset.get("type") or "asset")

            # display short name
            short_name = os.path.basename(path) if path else name
            item = QTreeWidgetItem([f"{short_name}  [{asset_type}]"])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, asset_type)

            # store extra metadata for detail panel
            for key in ("guid", "pipeline_status", "dimensions", "slice_count"):
                if key in asset:
                    item.setData(0, Qt.ItemDataRole.UserRole + 2 + list(asset.keys()).index(key), asset[key])

            self.assets_tree.addTopLevelItem(item)

    def _populate_paths(self, tree: QTreeWidget, paths: list[str], empty_label: str, asset_type: str = "script") -> None:
        tree.clear()
        if not paths:
            empty = QTreeWidgetItem([empty_label])
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            tree.addTopLevelItem(empty)
            return
        for path in paths:
            short = os.path.basename(path) if path else path
            item = QTreeWidgetItem([short])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, asset_type)
            tree.addTopLevelItem(item)

    # ------------------------------------------------------------------
    # folder navigation
    # ------------------------------------------------------------------

    def _rebuild_folder_tree(self, assets: list[dict[str, Any]]) -> None:
        """Extract unique parent folders from asset paths and populate folder tree."""
        self._folder_tree.clear()
        folders: set[str] = set()
        for asset in assets:
            path = str(asset.get("path") or "")
            if not path:
                continue
            parent = os.path.dirname(path).replace("\\", "/")
            if parent and parent != ".":
                folders.add(parent)

        root = QTreeWidgetItem(["Project"])
        root.setData(0, Qt.ItemDataRole.UserRole, "")
        root.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._folder_tree.addTopLevelItem(root)

        # build nested tree from folder paths
        for folder in sorted(folders):
            parts = folder.replace("\\", "/").strip("/").split("/")
            current = root
            for part in parts:
                child = self._find_child_item(current, part)
                if child is None:
                    child = QTreeWidgetItem([part])
                    child.setData(0, Qt.ItemDataRole.UserRole, "/".join(parts[: parts.index(part) + 1]))
                    child.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    current.addChild(child)
                current = child

    @staticmethod
    def _find_child_item(parent: QTreeWidgetItem, text: str) -> QTreeWidgetItem | None:
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.text(0) == text:
                return child
        return None

    def _on_folder_tree_double_clicked(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        folder = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
        self._navigate_to_folder(folder)

    def _navigate_to_folder(self, folder: str) -> None:
        self._current_folder = folder
        segments = folder.split("/") if folder else []
        segments = [s for s in segments if s]
        self._breadcrumb_stack = segments
        self._build_breadcrumb()
        self._apply_filter()

    def _build_breadcrumb(self) -> None:
        """Rebuild breadcrumb labels for current navigation."""
        # clear existing breadcrumb widgets
        while self._breadcrumb_layout.count():
            item = self._breadcrumb_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

        # always show "Project" as root
        root_label = QLabel('<a href="#" style="color: #4fc3f7;">Project</a>')
        root_label.setOpenExternalLinks(False)
        root_label.linkActivated.connect(lambda: self._navigate_to_folder(""))
        self._breadcrumb_layout.addWidget(root_label)

        for i, seg in enumerate(self._breadcrumb_stack):
            sep = QLabel("  &gt;  ")
            sep.setStyleSheet("color: #888;")
            self._breadcrumb_layout.addWidget(sep)

            partial = "/".join(self._breadcrumb_stack[: i + 1])
            link = QLabel(f'<a href="#" style="color: #4fc3f7;">{seg}</a>')
            link.setOpenExternalLinks(False)
            link.linkActivated.connect(lambda _checked=False, f=partial: self._navigate_to_folder(f))
            self._breadcrumb_layout.addWidget(link)

        self._breadcrumb_layout.addStretch()

    # ------------------------------------------------------------------
    # filter logic
    # ------------------------------------------------------------------

    def _on_filter_clicked(self, label: str) -> None:
        self._current_filter = label
        # toggle visual state
        for lbl, btn in self._filter_buttons.items():
            btn.setChecked(lbl == label)
        self._apply_filter()

    def _apply_filter(self) -> None:
        search_text = self._search_input.text().lower().strip()
        self._populate_assets_filtered(search_text)

    def _populate_assets_filtered(self, search_text: str) -> None:
        self.assets_tree.clear()
        filter_type = self._current_filter

        # map filter label to asset type
        type_map = {
            "All": None,
            "Images": "image",
            "Scenes": "scene",
            "Prefabs": "prefab",
            "Scripts": "script",
        }
        target_type = type_map.get(filter_type)

        visible: list[dict[str, Any]] = []
        for asset in self._all_assets:
            path = str(asset.get("path") or "")
            a_type = str(asset.get("type") or "asset")

            # type filter
            if target_type is not None and a_type != target_type:
                continue

            # folder filter: asset path must start with current folder
            norm_path = path.replace("\\", "/")
            if self._current_folder:
                prefix = self._current_folder.replace("\\", "/") + "/"
                if not norm_path.startswith(prefix):
                    continue

            # text search
            if search_text:
                name = str(asset.get("name") or "")
                if search_text not in name.lower() and search_text not in path.lower():
                    continue

            visible.append(asset)

        if not visible:
            empty = QTreeWidgetItem(["No matching assets"])
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.assets_tree.addTopLevelItem(empty)
            return

        # in subfolder mode, show ".." item
        if self._current_folder:
            up_item = QTreeWidgetItem([".."])
            up_item.setData(0, Qt.ItemDataRole.UserRole, "__up__")
            up_item.setData(0, Qt.ItemDataRole.UserRole + 1, "folder")
            self.assets_tree.addTopLevelItem(up_item)

        for asset in visible:
            path = str(asset.get("path") or "")
            name = str(asset.get("name") or path or "Asset")
            asset_type = str(asset.get("type") or "asset")
            short_name = os.path.basename(path) if path else name

            item = QTreeWidgetItem([f"{short_name}  [{asset_type}]"])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, asset_type)
            self.assets_tree.addTopLevelItem(item)

    # ------------------------------------------------------------------
    # asset item interaction
    # ------------------------------------------------------------------

    def _on_asset_item_double_clicked(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        asset_type = str(item.data(0, Qt.ItemDataRole.UserRole + 1) or "")

        if data == "__up__":
            # navigate up one level
            parent = os.path.dirname(self._current_folder) if self._current_folder else ""
            if parent == ".":
                parent = ""
            self._navigate_to_folder(parent)
            return

        if not data:
            return

        path = str(data)

        if asset_type == "folder":
            self._navigate_to_folder(path)
            return

        if asset_type == "scene":
            self.scene_open_requested.emit(path)

    def _on_asset_selection_changed(self, current: QTreeWidgetItem, _previous: QTreeWidgetItem) -> None:
        if current is None:
            self._detail_container.setVisible(False)
            self._current_detail_asset = None
            return

        data = current.data(0, Qt.ItemDataRole.UserRole)
        if not data or data == "__up__":
            self._detail_container.setVisible(False)
            self._current_detail_asset = None
            return

        path = str(data)

        # find full asset dict
        asset_dict: dict[str, Any] | None = None
        for a in self._all_assets:
            if str(a.get("path") or "") == path:
                asset_dict = a
                break

        if asset_dict is None:
            self._detail_container.setVisible(False)
            self._current_detail_asset = None
            return

        self._current_detail_asset = asset_dict
        self._show_asset_detail(asset_dict)

    def _show_asset_detail(self, asset: dict[str, Any]) -> None:
        path = str(asset.get("path") or "")
        name = str(asset.get("name") or path or "Asset")
        asset_type = str(asset.get("type") or "asset")
        guid = str(asset.get("guid") or "")
        guid_short = guid[:8] if len(guid) >= 8 else guid
        pipeline_status = str(asset.get("pipeline_status") or "unknown")
        dimensions = asset.get("dimensions")
        slice_count = asset.get("slice_count")

        lines = [
            f"<b>Name:</b> {name}",
            f"<b>Path:</b> {path}",
            f"<b>Type:</b> {asset_type}",
        ]
        if guid_short:
            lines.append(f"<b>GUID:</b> {guid_short}")
        lines.append(f"<b>Pipeline:</b> {pipeline_status}")

        if dimensions:
            if isinstance(dimensions, (list, tuple)) and len(dimensions) == 2:
                lines.append(f"<b>Dimensions:</b> {dimensions[0]} x {dimensions[1]}")
            else:
                lines.append(f"<b>Dimensions:</b> {dimensions}")
        if slice_count is not None:
            lines.append(f"<b>Slice Count:</b> {slice_count}")

        self._detail_label.setText("<br>".join(lines))
        self._detail_container.setVisible(True)

        # action buttons
        is_image = asset_type == self._ASSET_TYPE_IMAGE
        is_scene = asset_type == self._ASSET_TYPE_SCENE
        self._sprite_editor_btn.setVisible(is_image)
        self._open_scene_btn.setVisible(is_scene)
        self._sprite_editor_btn.setProperty("asset_path", path)

    def _on_open_sprite_editor(self) -> None:
        if self._current_detail_asset:
            path = str(self._current_detail_asset.get("path") or "")
            if path:
                self.sprite_editor_requested.emit(path)

    def _on_open_scene_from_detail(self) -> None:
        if self._current_detail_asset:
            path = str(self._current_detail_asset.get("path") or "")
            if path:
                self.scene_open_requested.emit(path)

    # ------------------------------------------------------------------
    # legacy compatibility: scene activation
    # ------------------------------------------------------------------

    def _on_scene_activated(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        scene_ref = item.data(0, Qt.ItemDataRole.UserRole)
        if scene_ref:
            self.scene_requested.emit(str(scene_ref))
