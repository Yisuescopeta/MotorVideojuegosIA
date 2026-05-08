"""Qt Animator authoring panel."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class AnimatorPanel(QWidget):
    """Thin Qt panel over public Animator EngineAPI methods."""

    ensure_requested = Signal(str)
    sprite_sheet_set_requested = Signal(str, str)
    speed_set_requested = Signal(str, float)
    flip_set_requested = Signal(str, bool, bool)
    state_upsert_requested = Signal(str, str, list, float, bool, object, bool)
    state_remove_requested = Signal(str, str)
    sprite_editor_requested = Signal(str)  # entity_name

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entity_name = ""

        self.entity_label = QLabel("No entity selected")
        self.status_label = QLabel("Animator not loaded")
        self.sprite_sheet_edit = QLineEdit()
        self.sprite_sheet_edit.setPlaceholderText("assets/sheet.png")
        self.sprite_editor_button = QPushButton("Open Sprite Editor")
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.01, 100.0)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setValue(1.0)
        self.flip_x_check = QCheckBox("Flip X")
        self.flip_y_check = QCheckBox("Flip Y")

        self.ensure_button = QPushButton("Ensure Animator")
        self.apply_sheet_button = QPushButton("Set Sheet")
        self.apply_speed_button = QPushButton("Set Speed/Flip")

        self.states_tree = QTreeWidget()
        self.states_tree.setHeaderLabels(["State", "Frames", "FPS", "Loop", "Default"])
        self.state_name_edit = QLineEdit()
        self.state_name_edit.setPlaceholderText("state")
        self.slice_names_edit = QLineEdit()
        self.slice_names_edit.setPlaceholderText("slice_0,slice_1")
        self.state_fps_spin = QDoubleSpinBox()
        self.state_fps_spin.setRange(0.01, 120.0)
        self.state_fps_spin.setValue(8.0)
        self.state_loop_check = QCheckBox("Loop")
        self.state_loop_check.setChecked(True)
        self.state_default_check = QCheckBox("Default")
        self.upsert_state_button = QPushButton("Upsert State")
        self.remove_state_button = QPushButton("Remove State")

        header = QHBoxLayout()
        header.addWidget(self.ensure_button)
        header.addWidget(self.apply_sheet_button)
        header.addWidget(self.apply_speed_button)
        header.addStretch(1)

        state_controls = QHBoxLayout()
        state_controls.addWidget(self.state_name_edit)
        state_controls.addWidget(self.slice_names_edit)
        state_controls.addWidget(self.state_fps_spin)
        state_controls.addWidget(self.state_loop_check)
        state_controls.addWidget(self.state_default_check)
        state_controls.addWidget(self.upsert_state_button)
        state_controls.addWidget(self.remove_state_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(self.entity_label)
        layout.addWidget(self.status_label)
        sprite_row = QHBoxLayout()
        sprite_row.addWidget(self.sprite_sheet_edit, stretch=1)
        sprite_row.addWidget(self.sprite_editor_button)
        layout.addLayout(sprite_row)
        layout.addWidget(self.speed_spin)
        layout.addWidget(self.flip_x_check)
        layout.addWidget(self.flip_y_check)
        layout.addLayout(header)
        layout.addWidget(self.states_tree, stretch=1)
        layout.addLayout(state_controls)

        self.ensure_button.clicked.connect(self._emit_ensure)
        self.apply_sheet_button.clicked.connect(self._emit_sheet)
        self.sprite_editor_button.clicked.connect(self._emit_sprite_editor)
        self.apply_speed_button.clicked.connect(self._emit_speed_flip)
        self.upsert_state_button.clicked.connect(self._emit_upsert_state)
        self.remove_state_button.clicked.connect(self._emit_remove_state)
        self.states_tree.itemSelectionChanged.connect(self._sync_selected_state)

    def _emit_sprite_editor(self) -> None:
        if self._entity_name:
            self.sprite_editor_requested.emit(self._entity_name)

    def set_entity(
        self,
        entity: dict[str, Any] | None,
        animator_info: dict[str, Any] | None = None,
        states: list[dict[str, Any]] | None = None,
    ) -> None:
        self._entity_name = str((entity or {}).get("name") or "")
        self.entity_label.setText(self._entity_name or "No entity selected")
        info = animator_info or {"exists": False, "states": []}
        exists = bool(info.get("exists"))
        self.status_label.setText("Animator ready" if exists else "Animator missing")
        self.sprite_sheet_edit.setText(str(info.get("sprite_sheet") or ""))
        self.speed_spin.setValue(float(info.get("speed") or 1.0))
        self.flip_x_check.setChecked(bool(info.get("flip_x", False)))
        self.flip_y_check.setChecked(bool(info.get("flip_y", False)))
        self._populate_states(states if states is not None else list(info.get("states") or []))

    def _populate_states(self, states: list[dict[str, Any]]) -> None:
        self.states_tree.clear()
        for state in states:
            name = str(state.get("state_name") or state.get("name") or "")
            frame_count = str(state.get("frame_count") or len(state.get("slice_names", []) or state.get("frames", [])))
            item = QTreeWidgetItem(
                [
                    name,
                    frame_count,
                    str(state.get("fps") or ""),
                    "yes" if state.get("loop", True) else "no",
                    "yes" if state.get("is_default", False) else "no",
                ]
            )
            self.states_tree.addTopLevelItem(item)

    def _sync_selected_state(self) -> None:
        item = self.states_tree.currentItem()
        if item is not None:
            self.state_name_edit.setText(item.text(0))

    def _emit_ensure(self) -> None:
        if self._entity_name:
            self.ensure_requested.emit(self._entity_name)

    def _emit_sheet(self) -> None:
        if self._entity_name:
            self.sprite_sheet_set_requested.emit(self._entity_name, self.sprite_sheet_edit.text().strip())

    def _emit_speed_flip(self) -> None:
        if self._entity_name:
            speed = float(self.speed_spin.value())
            flip_x = self.flip_x_check.isChecked()
            flip_y = self.flip_y_check.isChecked()
            self.speed_set_requested.emit(self._entity_name, speed)
            self.flip_set_requested.emit(self._entity_name, flip_x, flip_y)

    def _emit_upsert_state(self) -> None:
        state_name = self.state_name_edit.text().strip()
        if not self._entity_name or not state_name:
            return
        slices = [item.strip() for item in self.slice_names_edit.text().split(",") if item.strip()]
        self.state_upsert_requested.emit(
            self._entity_name,
            state_name,
            slices,
            float(self.state_fps_spin.value()),
            self.state_loop_check.isChecked(),
            None,
            self.state_default_check.isChecked(),
        )

    def _emit_remove_state(self) -> None:
        state_name = self.state_name_edit.text().strip()
        if self._entity_name and state_name:
            self.state_remove_requested.emit(self._entity_name, state_name)
