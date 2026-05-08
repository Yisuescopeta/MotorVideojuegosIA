"""Project launcher for the Qt editor."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from editor_qt.bridge.engine_facade import EditorEngineFacade


class LauncherWindow(QWidget):
    """Initial Qt surface for choosing a project before opening the editor."""

    project_open_requested = Signal(str)

    def __init__(self, facade: EditorEngineFacade | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.facade = facade or EditorEngineFacade()
        self._projects: list[dict[str, Any]] = []

        self.setWindowTitle("MotorVideojuegosIA Projects")
        self.resize(900, 620)

        title = QLabel("Projects")
        title.setObjectName("LauncherTitle")
        subtitle = QLabel("Busca, registra o crea proyectos para entrar al editor.")
        subtitle.setObjectName("LauncherSubtitle")

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search")
        self.add_button = QPushButton("Add")
        self.import_legacy_button = QPushButton("Import Legacy")
        self.new_project_button = QPushButton("+ New project")

        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_box, stretch=1)
        search_layout.addWidget(self.add_button)
        search_layout.addWidget(self.import_legacy_button)
        search_layout.addWidget(self.new_project_button)

        self.projects_table = QTableWidget(0, 4)
        self.projects_table.setObjectName("ProjectsTable")
        self.projects_table.setHorizontalHeaderLabels(["Name", "Path", "Activity", "Editor version"])
        self.projects_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.projects_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.projects_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.projects_table.verticalHeader().setVisible(False)
        self.projects_table.horizontalHeader().setStretchLastSection(True)

        self.status_label = QLabel("")
        self.status_label.setObjectName("LauncherStatus")
        self.exit_button = QPushButton("Exit")

        footer = QHBoxLayout()
        footer.addWidget(self.exit_button)
        footer.addStretch(1)
        footer.addWidget(self.status_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 12)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(search_layout)
        layout.addWidget(self.projects_table, stretch=1)
        layout.addLayout(footer)

        self.search_box.textChanged.connect(self._populate)
        self.add_button.clicked.connect(self._add_project)
        self.import_legacy_button.clicked.connect(self._import_legacy_project)
        self.new_project_button.clicked.connect(self._new_project)
        self.exit_button.clicked.connect(self.close)
        self.projects_table.itemDoubleClicked.connect(self._open_row_for_item)

        self.refresh()

    def refresh(self) -> None:
        self._projects = self.facade.list_recent_projects()
        self._populate()

    def _populate(self) -> None:
        query = self.search_box.text().strip().casefold()
        rows = [
            project
            for project in self._projects
            if not query
            or query in str(project.get("name") or "").casefold()
            or query in str(project.get("root") or "").casefold()
        ]
        self.projects_table.setRowCount(len(rows))
        for row, project in enumerate(rows):
            self._set_item(row, 0, str(project.get("name") or "Untitled Project"), project)
            self._set_item(row, 1, str(project.get("root") or ""), project)
            self._set_item(row, 2, str(project.get("activity") or ""), project)
            self._set_item(row, 3, str(project.get("engine_version") or ""), project)
        self.projects_table.resizeColumnsToContents()

    def _set_item(self, row: int, column: int, text: str, project: dict[str, Any]) -> None:
        item = QTableWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, project)
        self.projects_table.setItem(row, column, item)

    def _add_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open Project")
        if path:
            self._open_project(path)

    def _new_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "New Project Location")
        if not path:
            return
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok:
            return
        project_name = name.strip() or "Untitled Project"
        result = self.facade.create_project(path, project_name)
        if not result.get("success"):
            creator = EditorEngineFacade(project_root=Path.cwd())
            try:
                result = creator.create_project(path, project_name)
            finally:
                creator.shutdown()
        if result.get("success"):
            self.project_open_requested.emit(path)
            return
        self.status_label.setText(str(result.get("message") or "Project creation failed."))

    def _import_legacy_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Import Legacy Project")
        if not path:
            return
        target = Path(path)
        levels_dir = target / "levels"
        has_levels = levels_dir.exists() and any(levels_dir.rglob("*.json"))
        has_scene_files = list(target.glob("*.json"))
        if not has_levels and not has_scene_files:
            self.status_label.setText("No scene files found. Not a valid legacy project folder.")
            return
        result = self.facade.migrate_legacy_project(path)
        if result.get("success"):
            self.project_open_requested.emit(path)
        else:
            self.status_label.setText(str(result.get("message") or "Migration failed."))

    def _open_row_for_item(self, item: QTableWidgetItem) -> None:
        project = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(project, dict):
            root = str(project.get("root") or "")
            if root:
                self._open_project(root)

    def _open_project(self, path: str) -> None:
        target = Path(path).expanduser().resolve()
        manifest_path = target / "project.json"

        if not manifest_path.exists():
            # Detect legacy project
            levels_dir = target / "levels"
            has_levels = levels_dir.exists() and any(levels_dir.rglob("*.json"))
            has_scene_files = list(target.glob("*.json"))
            if has_levels or has_scene_files:
                reply = QMessageBox.question(
                    self,
                    "Import Legacy Project",
                    "This folder does not have a project.json. Do you want to create a Motor project in this folder?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    migrate_result = self.facade.migrate_legacy_project(str(target))
                    if not migrate_result.get("success"):
                        self.status_label.setText(str(migrate_result.get("message") or "Migration failed."))
                        return
                else:
                    self.status_label.setText("Operation cancelled. Not a valid Motor project.")
                    return

        result = self.facade.open_project(path)
        if not result.get("success"):
            validator = EditorEngineFacade(project_root=path, auto_ensure_project=False)
            try:
                result = validator.open_project(path)
            finally:
                validator.shutdown()
        if result.get("success"):
            self.project_open_requested.emit(path)
            return
        self.status_label.setText(str(result.get("message") or "Project open failed."))
