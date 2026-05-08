"""Qt Animator authoring panel."""

from __future__ import annotations

import re
from typing import Any, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

_SLICE_SEQUENCE_PATTERN = re.compile(r"^(.*?)(\d+)$")
_TRAILING_STATE_NUMBER_PATTERN = re.compile(r"_(\d+)$")


def detect_slice_sequences(slice_names: list[str]) -> list[list[str]]:
    """Detect consecutive numbered sequences (e.g. player_0..player_5)."""
    grouped: dict[str, list[tuple[int, int, str]]] = {}
    for position, name in enumerate(slice_names):
        match = _SLICE_SEQUENCE_PATTERN.match(str(name))
        if match is None:
            continue
        prefix = match.group(1)
        grouped.setdefault(prefix, []).append(
            (int(match.group(2)), position, str(name))
        )

    sequences: list[tuple[int, int, list[str]]] = []
    for items in grouped.values():
        ordered = sorted(items, key=lambda item: (item[0], item[1]))
        current: list[tuple[int, int, str]] = []
        previous_number: Optional[int] = None
        for number, position, name in ordered:
            if current and previous_number is not None and number != previous_number + 1:
                if len(current) > 1:
                    sequences.append(
                        (
                            len(current),
                            min(entry[1] for entry in current),
                            [entry[2] for entry in current],
                        )
                    )
                current = []
            current.append((number, position, name))
            previous_number = number
        if len(current) > 1:
            sequences.append(
                (
                    len(current),
                    min(entry[1] for entry in current),
                    [entry[2] for entry in current],
                )
            )

    sequences.sort(key=lambda item: (-item[0], item[1], item[2][0]))
    return [list(names) for _, _, names in sequences]


def detect_slice_groups(slice_names: list[str]) -> list[dict[str, Any]]:
    """Group slices by common prefix (e.g. player_0..player_5 -> group 'player')."""
    grouped: dict[str, list[tuple[int, int, str]]] = {}
    for position, name in enumerate(slice_names):
        match = _SLICE_SEQUENCE_PATTERN.match(str(name))
        if match is None:
            continue
        group_name = match.group(1).rstrip("_").strip()
        if not group_name:
            continue
        grouped.setdefault(group_name, []).append(
            (int(match.group(2)), position, str(name))
        )

    groups: list[dict[str, Any]] = []
    for group_name, items in grouped.items():
        ordered = sorted(items, key=lambda item: (item[0], item[1]))
        if len(ordered) < 2:
            continue
        slice_group = [item[2] for item in ordered]
        groups.append(
            {
                "group_name": group_name,
                "slice_names": slice_group,
                "count": len(slice_group),
            }
        )

    groups.sort(key=lambda item: (-int(item["count"]), str(item["group_name"])))
    return groups


def normalize_group_match_name(name: str) -> str:
    """Strip trailing state number for fuzzy matching against group names."""
    normalized = str(name or "").strip().lower()
    if not normalized:
        return ""
    return _TRAILING_STATE_NUMBER_PATTERN.sub("", normalized)


def get_recommended_slice_group(
    selected_state_name: str, groups: list[dict[str, Any]]
) -> Optional[dict[str, Any]]:
    """Find the detected group whose name fuzzy-matches the selected state."""
    target = normalize_group_match_name(selected_state_name)
    if not target:
        return None
    for group in groups:
        if normalize_group_match_name(str(group.get("group_name", ""))) == target:
            return dict(group)
    return None


class AnimatorPanel(QWidget):
    """Thin Qt panel over public Animator EngineAPI methods."""

    ensure_requested = Signal(str)
    sprite_sheet_set_requested = Signal(str, str)
    speed_set_requested = Signal(str, float)
    flip_set_requested = Signal(str, bool, bool)
    state_upsert_requested = Signal(str, str, list, float, bool, object, bool)
    state_remove_requested = Signal(str, str)
    sprite_editor_requested = Signal(str)
    slice_names_requested = Signal(str)  # entity_name

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entity_name = ""
        self._current_frame: int = 0
        self._selected_state_slices: list[str] = []
        self._current_states: dict[str, dict[str, Any]] = {}
        self._available_slice_names: list[str] = []
        self._detected_groups: list[dict[str, Any]] = []

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

        # --- Frame editor widgets ---
        self.frame_label = QLabel("Frame: 0/0")
        self.prev_frame_button = QPushButton("Prev Frame")
        self.next_frame_button = QPushButton("Next Frame")
        self.current_slice_label = QLabel("")

        # --- Group detection widgets ---
        self.detect_groups_button = QPushButton("Detect Groups")
        self.groups_list = QListWidget()
        self.recommended_label = QLabel("")

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

        frame_row = QHBoxLayout()
        frame_row.addWidget(self.frame_label)
        frame_row.addWidget(self.prev_frame_button)
        frame_row.addWidget(self.next_frame_button)
        frame_row.addWidget(self.current_slice_label)
        frame_row.addStretch(1)

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
        layout.addLayout(frame_row)
        layout.addWidget(self.detect_groups_button)
        layout.addWidget(self.groups_list)
        layout.addWidget(self.recommended_label)
        layout.addLayout(state_controls)

        self.ensure_button.clicked.connect(self._emit_ensure)
        self.apply_sheet_button.clicked.connect(self._emit_sheet)
        self.sprite_editor_button.clicked.connect(self._emit_sprite_editor)
        self.apply_speed_button.clicked.connect(self._emit_speed_flip)
        self.upsert_state_button.clicked.connect(self._emit_upsert_state)
        self.remove_state_button.clicked.connect(self._emit_remove_state)
        self.states_tree.itemSelectionChanged.connect(self._sync_selected_state)
        self.prev_frame_button.clicked.connect(self._prev_frame)
        self.next_frame_button.clicked.connect(self._next_frame)
        self.detect_groups_button.clicked.connect(self._emit_detect_groups)
        self.groups_list.itemClicked.connect(self._on_group_clicked)

    # ------------------------------------------------------------------
    # public helpers (called by controller / facade)
    # ------------------------------------------------------------------

    def set_available_slice_names(self, names: list[str]) -> None:
        """Receive slice names from sprite sheet metadata and run detection."""
        self._available_slice_names = list(names)
        self._run_detection()

    # ------------------------------------------------------------------
    # signals > external
    # ------------------------------------------------------------------

    def _emit_sprite_editor(self) -> None:
        if self._entity_name:
            self.sprite_editor_requested.emit(self._entity_name)

    def _emit_detect_groups(self) -> None:
        if self._entity_name:
            self.slice_names_requested.emit(self._entity_name)

    # ------------------------------------------------------------------
    # entity / state loading
    # ------------------------------------------------------------------

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
        state_list = states if states is not None else list(info.get("states") or [])
        self._populate_states(state_list)
        self._rebuild_current_states(state_list)

    def _populate_states(self, states: list[dict[str, Any]]) -> None:
        self.states_tree.clear()
        for state in states:
            name = str(state.get("state_name") or state.get("name") or "")
            frame_count = str(
                state.get("frame_count")
                or len(state.get("slice_names", []) or state.get("frames", []))
            )
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

    def _rebuild_current_states(self, states: list[dict[str, Any]]) -> None:
        self._current_states.clear()
        for state in states:
            name = str(state.get("state_name") or state.get("name") or "")
            if name:
                self._current_states[name] = state

    # ------------------------------------------------------------------
    # state tree selection -> sync fields + frame editor
    # ------------------------------------------------------------------

    def _sync_selected_state(self) -> None:
        item = self.states_tree.currentItem()
        if item is None:
            self._selected_state_slices = []
            self._current_frame = 0
            self._update_frame_display()
            self._update_recommended_label()
            return

        state_name = item.text(0)
        self.state_name_edit.setText(state_name)

        state_data = self._current_states.get(state_name, {})
        self._selected_state_slices = [
            str(s) for s in state_data.get("slice_names", []) if str(s)
        ]
        self._current_frame = 0
        self._update_frame_display()
        self._update_recommended_label()

    # ------------------------------------------------------------------
    # frame editor
    # ------------------------------------------------------------------

    def _prev_frame(self) -> None:
        if not self._selected_state_slices:
            return
        self._current_frame = max(0, self._current_frame - 1)
        self._update_frame_display()

    def _next_frame(self) -> None:
        if not self._selected_state_slices:
            return
        self._current_frame = min(
            len(self._selected_state_slices) - 1, self._current_frame + 1
        )
        self._update_frame_display()

    def _update_frame_display(self) -> None:
        total = len(self._selected_state_slices)
        if total == 0:
            self.frame_label.setText("Frame: 0/0")
            self.current_slice_label.setText("")
            return
        frame_idx = min(self._current_frame, total - 1)
        self.frame_label.setText(f"Frame: {frame_idx}/{total}")
        self.current_slice_label.setText(self._selected_state_slices[frame_idx])

    # ------------------------------------------------------------------
    # group detection
    # ------------------------------------------------------------------

    def _run_detection(self) -> None:
        if not self._available_slice_names:
            self._detected_groups = []
            self.groups_list.clear()
            self._update_recommended_label()
            return

        self._detected_groups = detect_slice_groups(self._available_slice_names)
        self.groups_list.clear()
        for group in self._detected_groups:
            label = f"{group['group_name']} ({group['count']} frames)"
            self.groups_list.addItem(label)
        self._update_recommended_label()

    def _on_group_clicked(self, item: QListWidgetItem) -> None:
        idx = self.groups_list.row(item)
        if 0 <= idx < len(self._detected_groups):
            group = self._detected_groups[idx]
            self.slice_names_edit.setText(",".join(group["slice_names"]))

    # ------------------------------------------------------------------
    # recommended group
    # ------------------------------------------------------------------

    def _update_recommended_label(self) -> None:
        state_name = self.state_name_edit.text().strip()
        if not state_name or not self._detected_groups:
            self.recommended_label.setText("")
            return

        recommended = get_recommended_slice_group(
            state_name, self._detected_groups
        )
        if recommended is None:
            self.recommended_label.setText("")
            return

        self.recommended_label.setText(
            f"Recommended: {recommended['group_name']} ({recommended['count']} frames)"
        )

    # ------------------------------------------------------------------
    # emit helpers
    # ------------------------------------------------------------------

    def _emit_ensure(self) -> None:
        if self._entity_name:
            self.ensure_requested.emit(self._entity_name)

    def _emit_sheet(self) -> None:
        if self._entity_name:
            self.sprite_sheet_set_requested.emit(
                self._entity_name, self.sprite_sheet_edit.text().strip()
            )

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
        slices = [
            item.strip()
            for item in self.slice_names_edit.text().split(",")
            if item.strip()
        ]
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
