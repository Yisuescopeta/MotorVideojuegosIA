"""Inspector panel for selected entity snapshots — component-based QTreeWidget."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from editor_qt.value_codec import encode_value

COMPONENT_ROLE = int(Qt.ItemDataRole.UserRole)
PROPERTY_ROLE = int(Qt.ItemDataRole.UserRole) + 1
VALUE_ROLE = int(Qt.ItemDataRole.UserRole) + 2

_UNREMOVABLE = {"Transform"}


class _CompatItem:
    """Backward‑compatible wrapper so ``table.item(row, col)`` still works."""

    __slots__ = ("_item", "_editor", "_component", "_property", "_orig_value", "_panel")

    def __init__(
        self,
        item: QTreeWidgetItem,
        editor: QWidget | None,
        component_name: str,
        property_name: str,
        original_value: Any,
        panel: InspectorPanel,
    ) -> None:
        self._item = item
        self._editor = editor
        self._component = component_name
        self._property = property_name
        self._orig_value = original_value
        self._panel = panel

    # ------------------------------------------------------------------
    # Backward‑compat surface (used by existing tests)
    # ------------------------------------------------------------------
    def setText(self, text: str) -> None:
        if self._editor is not None:
            self._editor.blockSignals(True)
            try:
                if isinstance(self._editor, QCheckBox):
                    lowered = str(text).strip().lower()
                    self._editor.setChecked(lowered in {"true", "1", "yes", "on"})
                elif isinstance(self._editor, QSpinBox):
                    try:
                        self._editor.setValue(int(text))
                    except (ValueError, TypeError):
                        pass
                elif isinstance(self._editor, QDoubleSpinBox):
                    try:
                        self._editor.setValue(float(text))
                    except (ValueError, TypeError):
                        pass
                elif isinstance(self._editor, QLineEdit):
                    self._editor.setText(str(text))
            finally:
                self._editor.blockSignals(False)
        self._panel.property_edit_requested.emit(
            self._panel._entity_name,
            self._component,
            self._property,
            str(text),
            self._orig_value,
        )

    def data(self, role: int) -> Any:
        return self._item.data(0, role)


class _TreeWithCompat(QTreeWidget):
    """QTreeWidget that exposes a flat ``item(row, col)`` for old tests."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._flat: list[_CompatItem] = []

    def item(self, row: int, col: int = 0) -> _CompatItem | None:  # type: ignore[override]
        if 0 <= row < len(self._flat):
            return self._flat[row]
        return None

    def _register_compat(self, w: _CompatItem) -> None:
        self._flat.append(w)

    def clear(self) -> None:
        super().clear()
        self._flat.clear()


class _CommittableSpinBox(QSpinBox):
    """SpinBox that only commits on Enter or focusOut, Escape restores."""
    commit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_value = 0
        self._committed = False

    def setValue(self, value):
        self._original_value = value
        super().setValue(value)

    def focusInEvent(self, event):
        self._original_value = self.value()
        self._committed = False
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        if not self._committed and self.value() != self._original_value:
            self.commit_requested.emit()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self._committed = True
            self.commit_requested.emit()
            self.clearFocus()
        elif event.key() == Qt.Key.Key_Escape:
            self._committed = True
            self.setValue(self._original_value)
            self.clearFocus()
        else:
            super().keyPressEvent(event)


class _CommittableDoubleSpinBox(QDoubleSpinBox):
    """DoubleSpinBox that only commits on Enter or focusOut, Escape restores."""
    commit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_value = 0.0
        self._committed = False

    def setValue(self, value):
        self._original_value = value
        super().setValue(value)

    def focusInEvent(self, event):
        self._original_value = self.value()
        self._committed = False
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        if not self._committed and self.value() != self._original_value:
            self.commit_requested.emit()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self._committed = True
            self.commit_requested.emit()
            self.clearFocus()
        elif event.key() == Qt.Key.Key_Escape:
            self._committed = True
            self.setValue(self._original_value)
            self.clearFocus()
        else:
            super().keyPressEvent(event)


class InspectorPanel(QWidget):
    property_edit_requested = Signal(str, str, str, str, object)
    component_add_requested = Signal(str, str)
    component_remove_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entity_name = ""
        self._loading = False
        self._facade: Any = None

        # Header
        self.title = QLabel("No entity selected")

        # Tree
        self.tree = _TreeWithCompat(self)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Property", "Value"])
        self.tree.header().setStretchLastSection(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)

        # Backward‑compat alias
        self.table = self.tree

        # Add Component button
        self._add_btn = QPushButton("Add Component")
        self._add_btn.clicked.connect(self._on_add_component)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self.title)
        layout.addWidget(self.tree)
        layout.addWidget(self._add_btn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_entity(self, entity_data: dict[str, Any] | None, facade: Any = None) -> None:
        self._loading = True
        self._facade = facade
        self.tree.clear()

        if not entity_data:
            self._entity_name = ""
            self.title.setText("No entity selected")
            self._loading = False
            return

        name = str(entity_data.get("name", "Entity"))
        self._entity_name = name
        self.title.setText(name)

        components = entity_data.get("components") or {}
        if isinstance(components, dict):
            for comp_name, comp_data in sorted(components.items()):
                self._append_component(str(comp_name), comp_data)

        self.tree.expandAll()
        self._loading = False

    # ------------------------------------------------------------------
    # Tree building
    # ------------------------------------------------------------------
    def _append_component(self, component_name: str, component_data: Any) -> None:
        root = QTreeWidgetItem(self.tree)
        root.setText(0, component_name)
        root.setData(0, COMPONENT_ROLE, component_name)
        root.setFlags(root.flags() & ~Qt.ItemFlag.ItemIsEditable)
        root.setExpanded(True)

        # Remove button (except unremovable components)
        if component_name not in _UNREMOVABLE:
            self._attach_remove_button(root, component_name)

        if not isinstance(component_data, dict):
            return

        for prop_name, value in sorted(component_data.items()):
            child = QTreeWidgetItem(root)
            child.setText(0, str(prop_name))
            child.setData(0, COMPONENT_ROLE, component_name)
            child.setData(0, PROPERTY_ROLE, str(prop_name))
            child.setData(0, VALUE_ROLE, value)
            child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsEditable)

            editor = self._create_editor(value, component_name, str(prop_name))
            self.tree.setItemWidget(child, 1, editor)

            self.tree._register_compat(
                _CompatItem(child, editor, component_name, str(prop_name), value, self)
            )

    def _attach_remove_button(self, root: QTreeWidgetItem, component_name: str) -> None:
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        btn = QPushButton("\u2715")  # ✕
        btn.setFixedSize(20, 20)
        btn.setToolTip(f"Remove {component_name}")
        btn.clicked.connect(
            lambda checked=False, cn=component_name: self._on_remove_component(cn)
        )
        layout.addWidget(btn)
        layout.addStretch()
        self.tree.setItemWidget(root, 1, widget)

    # ------------------------------------------------------------------
    # Typed inline editors
    # ------------------------------------------------------------------
    def _create_editor(
        self, value: Any, component_name: str, property_name: str
    ) -> QWidget:
        if isinstance(value, bool):
            cb = QCheckBox()
            cb.setChecked(value)
            cb.toggled.connect(
                lambda checked, cn=component_name, pn=property_name, ov=value: (
                    self._emit_edit(cn, pn, checked, ov)
                )
            )
            return cb

        if isinstance(value, int):
            spin = _CommittableSpinBox()
            spin.setRange(-999_999, 999_999)
            spin.setValue(value)
            spin.commit_requested.connect(
                lambda cn=component_name, pn=property_name, ov=value, w=spin: (
                    self._emit_edit(cn, pn, w.value(), ov)
                )
            )
            return spin

        if isinstance(value, float):
            dspin = _CommittableDoubleSpinBox()
            dspin.setDecimals(3)
            dspin.setRange(-999_999.0, 999_999.0)
            dspin.setValue(value)
            dspin.commit_requested.connect(
                lambda cn=component_name, pn=property_name, ov=value, w=dspin: (
                    self._emit_edit(cn, pn, w.value(), ov)
                )
            )
            return dspin

        # str, None, list, dict → QLineEdit
        le = QLineEdit()
        le.setText(encode_value(value))
        le.editingFinished.connect(
            lambda cn=component_name, pn=property_name, ov=value, w=le: (
                self._emit_edit(cn, pn, w.text(), ov)
            )
        )
        return le

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------
    def _emit_edit(
        self,
        component_name: str,
        property_name: str,
        new_value: Any,
        original_value: Any,
    ) -> None:
        if self._loading or not self._entity_name:
            return
        self.property_edit_requested.emit(
            self._entity_name,
            component_name,
            property_name,
            str(new_value),
            original_value,
        )

    def _on_add_component(self) -> None:
        if not self._entity_name:
            return
        text, ok = QInputDialog.getText(self, "Add Component", "Component name:")
        if ok and text.strip():
            self.component_add_requested.emit(self._entity_name, text.strip())

    def _on_remove_component(self, component_name: str) -> None:
        if not self._entity_name:
            return
        self.component_remove_requested.emit(self._entity_name, component_name)
