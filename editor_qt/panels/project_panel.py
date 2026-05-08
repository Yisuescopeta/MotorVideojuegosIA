"""Read-only project panel for scenes and assets."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


class ProjectPanel(QWidget):
    scene_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_label = QLabel("No project loaded")
        self.project_label.setObjectName("ProjectLabel")

        self.scenes_tree = QTreeWidget()
        self.scenes_tree.setHeaderLabels(["Scenes"])

        self.assets_tree = QTreeWidget()
        self.assets_tree.setHeaderLabels(["Assets"])

        self.prefabs_tree = QTreeWidget()
        self.prefabs_tree.setHeaderLabels(["Prefabs"])

        self.scripts_tree = QTreeWidget()
        self.scripts_tree.setHeaderLabels(["Scripts"])

        self.tabs = QTabWidget()
        self.tabs.addTab(self.assets_tree, "Assets")
        self.tabs.addTab(self.scenes_tree, "Scenes")
        self.tabs.addTab(self.prefabs_tree, "Prefabs")
        self.tabs.addTab(self.scripts_tree, "Scripts")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self.project_label)
        layout.addWidget(self.tabs, stretch=1)

        self.scenes_tree.itemDoubleClicked.connect(self._on_scene_activated)

    def set_project_data(
        self,
        project: dict[str, Any],
        active_scene: dict[str, Any],
        scenes: list[dict[str, Any]],
        assets: list[dict[str, Any]],
        scripts: list[str] | None = None,
        prefabs: list[str] | None = None,
    ) -> None:
        name = str(project.get("name") or "Untitled Project")
        root = str(project.get("root") or "")
        self.project_label.setText(f"{name}  {root}".strip())
        self._populate_scenes(scenes, str(active_scene.get("path") or ""))
        self._populate_assets(assets)
        self._populate_paths(self.scripts_tree, scripts or [], "No scripts")
        self._populate_paths(self.prefabs_tree, prefabs or [], "No prefabs")

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
            suffix = " *" if active_path and path == active_path else ""
            item = QTreeWidgetItem([f"{name}{suffix}"])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
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
            item = QTreeWidgetItem([f"{name}  [{asset_type}]"])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            self.assets_tree.addTopLevelItem(item)

    def _populate_paths(self, tree: QTreeWidget, paths: list[str], empty_label: str) -> None:
        tree.clear()
        if not paths:
            empty = QTreeWidgetItem([empty_label])
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            tree.addTopLevelItem(empty)
            return
        for path in paths:
            item = QTreeWidgetItem([path])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            tree.addTopLevelItem(item)

    def _on_scene_activated(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        scene_ref = item.data(0, Qt.ItemDataRole.UserRole)
        if scene_ref:
            self.scene_requested.emit(str(scene_ref))
