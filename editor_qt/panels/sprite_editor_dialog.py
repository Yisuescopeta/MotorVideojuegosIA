"""Qt Sprite Editor dialog for grid/auto/manual slicing."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class SpritePreviewWidget(QWidget):
    """Preview widget showing sprite sheet with slice overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap: QPixmap | None = None
        self.slices: list[dict[str, Any]] = []
        self.zoom: float = 1.0
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_image(self, path: str) -> None:
        self.pixmap = QPixmap(path) if path and Path(path).exists() else None
        self.update()

    def set_slices(self, slices: list[dict[str, Any]]) -> None:
        self.slices = list(slices) if slices else []
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        if self.pixmap is None or self.pixmap.isNull():
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No image loaded")
            return

        # Center image in widget
        img_w = self.pixmap.width() * self.zoom
        img_h = self.pixmap.height() * self.zoom
        ox = (self.width() - img_w) / 2
        oy = (self.height() - img_h) / 2
        painter.drawPixmap(QRectF(ox, oy, img_w, img_h), self.pixmap, self.pixmap.rect())

        # Draw slices
        painter.setPen(QPen(QColor(58, 121, 187), 1))
        for s in self.slices:
            sx = ox + float(s.get("x", 0)) * self.zoom
            sy = oy + float(s.get("y", 0)) * self.zoom
            sw = float(s.get("width", 16)) * self.zoom
            sh = float(s.get("height", 16)) * self.zoom
            painter.drawRect(QRectF(sx, sy, sw, sh))
            name = s.get("name", "")
            if name:
                painter.setPen(QColor(220, 220, 220))
                painter.drawText(QRectF(sx + 2, sy + 2, sw - 4, 12), Qt.AlignmentFlag.AlignLeft, name)
                painter.setPen(QPen(QColor(58, 121, 187), 1))


class SpriteEditorDialog(QDialog):
    """Modal dialog for editing sprite slice metadata."""

    slices_saved = Signal(str, list)

    def __init__(self, asset_path: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sprite Editor")
        self.setMinimumSize(800, 600)
        self.resize(960, 680)

        self._asset_path = asset_path
        self._image_path = ""
        self._slices: list[dict[str, Any]] = []

        # Grid settings
        self._cell_width = 32
        self._cell_height = 32
        self._margin = 0
        self._spacing = 0
        self._pivot_x = 0.5
        self._pivot_y = 0.5
        self._naming_prefix = ""
        self._import_mode = "grid"

        # ---- Main layout (single QVBoxLayout wrapping everything) ----
        main_layout = QVBoxLayout(self)

        # Content row: left panel + preview
        content = QHBoxLayout()

        # --- Left panel: controls ---
        left = QWidget()
        left.setMaximumWidth(320)
        left_layout = QVBoxLayout(left)

        # Image info
        self.info_label = QLabel("No asset selected")
        self.info_label.setWordWrap(True)
        left_layout.addWidget(self.info_label)

        # Import button
        self.import_btn = QPushButton("Import Image...")
        self.import_btn.clicked.connect(self._on_import)
        left_layout.addWidget(self.import_btn)

        # Mode tabs
        self.mode_tabs = QTabWidget()

        # Grid tab
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.addWidget(QLabel("Cell Width:"), 0, 0)
        self.cell_width_spin = QSpinBox()
        self.cell_width_spin.setRange(1, 2048)
        self.cell_width_spin.setValue(32)
        grid_layout.addWidget(self.cell_width_spin, 0, 1)

        grid_layout.addWidget(QLabel("Cell Height:"), 1, 0)
        self.cell_height_spin = QSpinBox()
        self.cell_height_spin.setRange(1, 2048)
        self.cell_height_spin.setValue(32)
        grid_layout.addWidget(self.cell_height_spin, 1, 1)

        grid_layout.addWidget(QLabel("Margin:"), 2, 0)
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 256)
        grid_layout.addWidget(self.margin_spin, 2, 1)

        grid_layout.addWidget(QLabel("Spacing:"), 3, 0)
        self.spacing_spin = QSpinBox()
        self.spacing_spin.setRange(0, 256)
        grid_layout.addWidget(self.spacing_spin, 3, 1)

        self.mode_tabs.addTab(grid_widget, "Grid")

        # Auto tab
        auto_widget = QWidget()
        auto_layout = QVBoxLayout(auto_widget)
        auto_layout.addWidget(QLabel("Automatic detection:"))
        auto_layout.addWidget(QLabel("Detects opaque regions in the image\nand creates slices automatically."))
        auto_layout.addStretch()
        self.mode_tabs.addTab(auto_widget, "Auto")

        # Manual tab
        manual_widget = QWidget()
        manual_layout = QVBoxLayout(manual_widget)
        manual_layout.addWidget(QLabel("Manual slices:"))
        manual_layout.addWidget(QLabel("Draw rectangles over the preview."))
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self._on_clear_manual)
        manual_layout.addWidget(self.clear_btn)
        manual_layout.addStretch()
        self.mode_tabs.addTab(manual_widget, "Manual")

        left_layout.addWidget(self.mode_tabs)

        # Pivot
        pivot_group = QGroupBox("Pivot")
        pivot_layout = QGridLayout(pivot_group)
        pivot_layout.addWidget(QLabel("Pivot X:"), 0, 0)
        self.pivot_x_spin = QDoubleSpinBox()
        self.pivot_x_spin.setRange(0.0, 1.0)
        self.pivot_x_spin.setSingleStep(0.05)
        self.pivot_x_spin.setValue(0.5)
        pivot_layout.addWidget(self.pivot_x_spin, 0, 1)

        pivot_layout.addWidget(QLabel("Pivot Y:"), 1, 0)
        self.pivot_y_spin = QDoubleSpinBox()
        self.pivot_y_spin.setRange(0.0, 1.0)
        self.pivot_y_spin.setSingleStep(0.05)
        self.pivot_y_spin.setValue(0.5)
        pivot_layout.addWidget(self.pivot_y_spin, 1, 1)
        left_layout.addWidget(pivot_group)

        # Naming
        name_group = QGroupBox("Naming")
        name_layout = QVBoxLayout(name_group)
        name_layout.addWidget(QLabel("Prefix:"))
        self.naming_edit = QLabel("<auto>")
        name_layout.addWidget(self.naming_edit)
        left_layout.addWidget(name_group)

        # Buttons
        self.generate_btn = QPushButton("Generate Slices")
        self.generate_btn.clicked.connect(self._on_generate)
        left_layout.addWidget(self.generate_btn)

        self.save_btn = QPushButton("Save Slices")
        self.save_btn.clicked.connect(self._on_save)
        self.save_btn.setEnabled(False)
        left_layout.addWidget(self.save_btn)

        left_layout.addStretch()

        content.addWidget(left)

        # --- Right panel: preview ---
        self.preview = SpritePreviewWidget()
        content.addWidget(self.preview, stretch=1)

        main_layout.addLayout(content)

        # --- Bottom bar ---
        bottom = QHBoxLayout()
        self.status_label = QLabel("")
        bottom.addWidget(self.status_label)
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)

        main_layout.addLayout(bottom)

        # Reload legacy data if available
        self._reload_legacy_data()

    def _reload_legacy_data(self) -> None:
        """Open metadata from asset_path if available."""
        if not self._asset_path:
            return
        # In a real setup this would call AssetService
        # For now, set the image preview from derived path
        if self._asset_path.endswith(".json"):
            self._image_path = self._asset_path.replace(".json", ".png")
        else:
            self._image_path = self._asset_path
        self._load_image()

    def _load_image(self) -> None:
        self.preview.set_image(self._image_path)
        if self.preview.pixmap and not self.preview.pixmap.isNull():
            pw = max(self.preview.pixmap.width(), 1)
            ph = max(self.preview.pixmap.height(), 1)
            self.preview.zoom = min(
                max(self.preview.width(), 1) / pw,
                max(self.preview.height(), 1) / ph,
                2.0,
            )
        else:
            self.preview.zoom = 1.0

        if self.preview.pixmap and not self.preview.pixmap.isNull():
            w = self.preview.pixmap.width()
            h = self.preview.pixmap.height()
            self.info_label.setText(f"{self._image_path}\n{w}x{h} px")
        else:
            self.info_label.setText("No image")

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Sprite Sheet", "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self._image_path = path
            self._load_image()
            self._on_generate()

    def _on_generate(self) -> None:
        mode = self.mode_tabs.currentIndex()
        self._import_mode = ["grid", "auto", "manual"][mode]

        if self._import_mode == "grid":
            cw = self.cell_width_spin.value()
            ch = self.cell_height_spin.value()
            mg = self.margin_spin.value()
            sp = self.spacing_spin.value()
            self._slices = self._generate_grid_slices(cw, ch, mg, sp)
        elif self._import_mode == "auto":
            # Simplified auto-detection placeholder
            self._slices = [{"name": "slice_0", "x": 0, "y": 0, "width": 32, "height": 32}]
        else:
            # Manual: keep existing slices if any, or empty
            pass

        self.preview.set_slices(self._slices)
        self.save_btn.setEnabled(bool(self._slices))
        self.status_label.setText(f"{len(self._slices)} slices generated")

    def _generate_grid_slices(
        self, cell_w: int, cell_h: int, margin: int, spacing: int
    ) -> list[dict[str, Any]]:
        slices: list[dict[str, Any]] = []
        if not self.preview.pixmap or self.preview.pixmap.isNull():
            return slices
        img_w = self.preview.pixmap.width()
        img_h = self.preview.pixmap.height()

        prefix = Path(self._image_path).stem

        x = margin
        y = margin
        index = 0
        while y + cell_h <= img_h - margin:
            while x + cell_w <= img_w - margin:
                slices.append({
                    "name": f"{prefix}_{index}",
                    "x": x,
                    "y": y,
                    "width": cell_w,
                    "height": cell_h,
                    "pivot_x": self.pivot_x_spin.value(),
                    "pivot_y": self.pivot_y_spin.value(),
                })
                x += cell_w + spacing
                index += 1
            x = margin
            y += cell_h + spacing

        return slices

    def _on_clear_manual(self) -> None:
        self._slices = []
        self.preview.set_slices([])
        self.save_btn.setEnabled(False)
        self.status_label.setText("Slices cleared")

    def _on_save(self) -> None:
        if not self._slices:
            return
        # Save slices - emit signal for facade to handle persistence
        self.slices_saved.emit(self._image_path, self._slices)
        self.status_label.setText(f"Saved {len(self._slices)} slices to metadata")
        self.accept()


def open_sprite_editor(
    asset_path: str, parent=None
) -> tuple[bool, str, list[dict[str, Any]]]:
    """Convenience: open sprite editor dialog, return (accepted, image_path, slices)."""
    dlg = SpriteEditorDialog(asset_path=asset_path, parent=parent)
    result = dlg.exec()
    if result == QDialog.DialogCode.Accepted:
        return True, dlg._image_path, dlg._slices
    return False, "", []
