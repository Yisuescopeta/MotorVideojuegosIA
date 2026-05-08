"""Qt-native scene/game preview panel with editor camera and gizmo support."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from editor_qt.gizmo.gizmo_modes import GizmoManager, GizmoMode
from editor_qt.viewmodels import normalize_viewport_entity


class QtSceneViewportPanel(QWidget):
    """Authoring preview rendered by Qt only; no raylib and no game loop."""

    entity_selected = Signal(str)
    entity_moved = Signal(str, str, str, float, float)
    entity_rotated = Signal(str, str, str, float)  # entity, component, property, new_rotation
    entity_scaled = Signal(str, str, str, float, float)  # entity, component, property, new_scale_x, new_scale_y

    def __init__(self, mode: str = "Scene", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mode = mode
        self.setObjectName("ViewportPanel")
        self.setMinimumSize(420, 280)
        self.setMouseTracking(True)
        self._scene_info: dict[str, Any] = {}
        self._entities: list[dict[str, Any]] = []
        self._project_root = Path.cwd()
        self._drawn_rects: list[tuple[str, QRectF]] = []
        self._pixmap_cache: dict[str, QPixmap] = {}

        # Editor camera
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._zoom: float = 1.0
        self._pan_start: QPointF | None = None
        self._pan_origin: tuple[float, float] = (0.0, 0.0)

        # Gizmo
        self._gizmo = GizmoManager()
        self._selected_entity: str = ""
        self._gizmo_drag_preview: tuple[float, float] | None = None
        self._gizmo_entity_world_rect: QRectF | None = None

        # Drag state
        self._middle_dragging: bool = False

    # -- public API -----------------------------------------------------------

    def set_snapshot(
        self,
        *,
        scene_info: dict[str, Any],
        entities: list[dict[str, Any]],
        project_root: str | Path = "",
    ) -> None:
        self._scene_info = dict(scene_info)
        self._entities = [normalize_viewport_entity(entity) for entity in entities]
        if project_root:
            self._project_root = Path(project_root).expanduser().resolve()
        self.update()

    def set_gizmo_mode(self, mode_str: str) -> None:
        mapping: dict[str, GizmoMode] = {
            "Select": GizmoMode.SELECT,
            "Move": GizmoMode.TRANSLATE_FREE,
            "Rotate": GizmoMode.ROTATE_Z,
            "Scale": GizmoMode.SCALE_UNIFORM,
        }
        self._gizmo.set_mode(mapping.get(mode_str, GizmoMode.SELECT))
        self.update()

    # -- mouse events ---------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802
        pos = event.position()

        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = True
            self._pan_start = QPointF(pos)
            self._pan_origin = (self._pan_x, self._pan_y)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            # Try gizmo hit-test first
            if self._selected_entity and self._gizmo_entity_world_rect is not None:
                # Build gizmo handles in screen space for hit testing
                center_screen = self._world_to_screen(
                    self._gizmo_entity_world_rect.center().x(),
                    self._gizmo_entity_world_rect.center().y(),
                )
                self._gizmo.build_handles(
                    QPointF(center_screen[0], center_screen[1]), self._zoom
                )
                handle = self._gizmo.hit_test(pos)
                if handle is not None:
                    entity = self._get_selected_entity_dict()
                    if entity:
                        wx = float(entity.get("x", 0.0))
                        wy = float(entity.get("y", 0.0))
                        self._gizmo.start_drag(handle, pos, wx, wy)
                        self._gizmo_drag_preview = (wx, wy)
                    return

            # Fall through to entity selection
            world_pos = self._screen_to_world(pos)
            wp = QPointF(world_pos[0], world_pos[1])
            for entity_name, rect in reversed(self._drawn_rects):
                if rect.contains(wp):
                    self.entity_selected.emit(entity_name)
                    self._selected_entity = entity_name
                    self._update_gizmo_rect()
                    self.update()
                    return

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position()

        if self._middle_dragging and self._pan_start is not None:
            dx = pos.x() - self._pan_start.x()
            dy = pos.y() - self._pan_start.y()
            self._pan_x = self._pan_origin[0] + dx
            self._pan_y = self._pan_origin[1] + dy
            self.update()
            return

        if self._gizmo.is_dragging:
            new_pos = self._gizmo.update_drag(pos, self._zoom)
            self._gizmo_drag_preview = (new_pos[0], new_pos[1])
            self.update()
            return

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = False
            self._pan_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton and self._gizmo.is_dragging:
            result = self._gizmo.end_drag()
            if result is not None and self._selected_entity:
                after = result.get("after_state", {})
                mode = self._gizmo.mode
                if mode == GizmoMode.ROTATE_Z:
                    self.entity_rotated.emit(
                        self._selected_entity, "Transform", "rotation",
                        float(after.get("rotation", 0.0)),
                    )
                elif mode in (GizmoMode.SCALE_X, GizmoMode.SCALE_Y, GizmoMode.SCALE_UNIFORM):
                    self.entity_scaled.emit(
                        self._selected_entity, "Transform", "scale",
                        float(after.get("scale_x", 1.0)),
                        float(after.get("scale_y", 1.0)),
                    )
                else:
                    self.entity_moved.emit(
                        self._selected_entity, "Transform", "position",
                        float(after.get("x", 0.0)),
                        float(after.get("y", 0.0)),
                    )
            self._gizmo_drag_preview = None
            self._update_gizmo_rect()
            self.update()
            return

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            return
        step = 0.1 if delta > 0 else -0.1
        new_zoom = self._zoom + step
        new_zoom = max(0.1, min(5.0, new_zoom))

        # Zoom toward cursor position
        cursor_pos = event.position()
        world_before = self._screen_to_world(cursor_pos)
        self._zoom = new_zoom
        world_after = self._screen_to_world(cursor_pos)

        self._pan_x += (world_after[0] - world_before[0]) * self._zoom
        self._pan_y += (world_after[1] - world_before[1]) * self._zoom

        self._update_gizmo_rect()
        self.update()

    # -- paint ----------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#171a1f"))

        # Camera transform (world → screen)
        painter.save()
        painter.translate(
            QPointF(self.width() / 2.0 + self._pan_x,
                    self.height() / 2.0 + self._pan_y)
        )
        painter.scale(self._zoom, self._zoom)
        self._draw_grid(painter)
        self._draw_entities(painter)
        self._draw_gizmo(painter)
        painter.restore()

        self._draw_status(painter)

    # -- coordinate helpers ---------------------------------------------------

    def _screen_to_world(self, screen_pos: QPointF) -> tuple[float, float]:
        """Convert widget pixel coords to world coords accounting for pan/zoom."""
        sx = float(screen_pos.x())
        sy = float(screen_pos.y())
        hw = self.width() / 2.0
        hh = self.height() / 2.0
        safe_zoom = max(self._zoom, 0.01)
        wx = (sx - hw - self._pan_x) / safe_zoom
        wy = (sy - hh - self._pan_y) / safe_zoom
        return (wx, wy)

    def _world_to_screen(self, world_x: float, world_y: float) -> tuple[float, float]:
        """Convert world coords to widget pixel coords."""
        hw = self.width() / 2.0
        hh = self.height() / 2.0
        sx = world_x * self._zoom + hw + self._pan_x
        sy = world_y * self._zoom + hh + self._pan_y
        return (sx, sy)

    # -- drawing --------------------------------------------------------------

    def _draw_grid(self, painter: QPainter) -> None:
        # Compute visible world area
        left = -self.width() / 2.0 / self._zoom - self._pan_x / self._zoom
        right = self.width() / 2.0 / self._zoom - self._pan_x / self._zoom
        top = -self.height() / 2.0 / self._zoom - self._pan_y / self._zoom
        bottom = self.height() / 2.0 / self._zoom - self._pan_y / self._zoom

        step = 32.0
        painter.setPen(QPen(QColor("#292d34"), 1.0 / self._zoom))

        start_x = int(left // step) * step
        x = start_x
        while x <= right:
            painter.drawLine(QPointF(x, top), QPointF(x, bottom))
            x += step

        start_y = int(top // step) * step
        y = start_y
        while y <= bottom:
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            y += step

        # Axes at world origin
        painter.setPen(QPen(QColor("#3b4655"), 1.0 / self._zoom))
        painter.drawLine(QPointF(0.0, top), QPointF(0.0, bottom))
        painter.drawLine(QPointF(left, 0.0), QPointF(right, 0.0))

    def _draw_entities(self, painter: QPainter) -> None:
        self._drawn_rects = []
        for index, entity in enumerate(self._entities):
            if not entity.get("active", True):
                continue
            width = max(12.0, min(240.0, float(entity.get("width", 48.0))))
            height = max(12.0, min(240.0, float(entity.get("height", 48.0))))
            wx = float(entity.get("x", 0.0))
            wy = float(entity.get("y", 0.0))
            rect = QRectF(wx - width / 2.0, wy - height / 2.0, width, height)
            entity_name = str(entity.get("name") or "")
            self._drawn_rects.append((entity_name, rect))

            # If dragging gizmo for this entity, use preview position
            if (self._gizmo.is_dragging and self._selected_entity == entity_name
                    and self._gizmo_drag_preview is not None):
                px, py = self._gizmo_drag_preview
                rect = QRectF(px - width / 2.0, py - height / 2.0, width, height)

            painter.save()
            if self._gizmo.is_dragging and self._selected_entity == entity_name:
                mode = self._gizmo.mode
                if mode == GizmoMode.ROTATE_Z:
                    cx = rect.center().x()
                    cy = rect.center().y()
                    painter.translate(cx, cy)
                    painter.rotate(float(self._gizmo.current_angle or 0))
                    painter.translate(-cx, -cy)
                elif mode in (GizmoMode.SCALE_X, GizmoMode.SCALE_Y, GizmoMode.SCALE_UNIFORM):
                    cx = rect.center().x()
                    cy = rect.center().y()
                    painter.translate(cx, cy)
                    sx = float(self._gizmo.current_scale[0] if self._gizmo.current_scale else 1.0)
                    sy = float(self._gizmo.current_scale[1] if self._gizmo.current_scale else 1.0)
                    painter.scale(sx, sy)
                    painter.translate(-cx, -cy)

            pixmap = self._load_pixmap(str(entity.get("sprite") or ""))
            if pixmap is not None:
                scaled = pixmap.scaled(
                    int(width * self._zoom),
                    int(height * self._zoom),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                painter.drawPixmap(rect.toRect(), scaled)
            else:
                color = QColor("#315f91") if index % 2 == 0 else QColor("#5d7f4f")
                painter.fillRect(rect, color)
                painter.setPen(QPen(QColor("#a9c8ff"), 1.0 / self._zoom))
                painter.drawRect(rect)

            painter.setPen(QColor("#e4e7eb"))
            font = painter.font()
            font.setPixelSize(max(8, int(12.0 / self._zoom)))
            painter.setFont(font)
            painter.drawText(
                rect.adjusted(3.0 / self._zoom, 2.0 / self._zoom, 160.0 / self._zoom, 18.0 / self._zoom),
                Qt.AlignmentFlag.AlignLeft,
                entity_name or "Entity",
            )
            painter.restore()

    def _draw_gizmo(self, painter: QPainter) -> None:
        if not self._selected_entity:
            return
        entity = self._get_selected_entity_dict()
        if entity is None:
            return
        width = max(12.0, min(240.0, float(entity.get("width", 48.0))))
        height = max(12.0, min(240.0, float(entity.get("height", 48.0))))
        wx = float(entity.get("x", 0.0))
        wy = float(entity.get("y", 0.0))
        if self._gizmo_drag_preview is not None:
            wx, wy = self._gizmo_drag_preview
        entity_rect = QRectF(wx - width / 2.0, wy - height / 2.0, width, height)
        self._gizmo_entity_world_rect = entity_rect
        self._gizmo.render(painter, entity_rect, self._zoom)

    def _draw_status(self, painter: QPainter) -> None:
        painter.setPen(QColor("#9aa3ad"))
        name = str(self._scene_info.get("name") or self._scene_info.get("path") or "No scene")
        count = len(self._entities)
        dirty = "Unsaved" if self._scene_info.get("dirty") else "Saved"
        painter.drawText(16, 26, f"{self.mode} preview - {name} - Entities: {count} - {dirty}")

    # -- helpers --------------------------------------------------------------

    def _get_selected_entity_dict(self) -> dict[str, Any] | None:
        for entity in self._entities:
            if entity.get("name") == self._selected_entity:
                return entity
        return None

    def _update_gizmo_rect(self) -> None:
        entity = self._get_selected_entity_dict()
        if entity is None:
            self._gizmo_entity_world_rect = None
            return
        width = max(12.0, min(240.0, float(entity.get("width", 48.0))))
        height = max(12.0, min(240.0, float(entity.get("height", 48.0))))
        wx = float(entity.get("x", 0.0))
        wy = float(entity.get("y", 0.0))
        self._gizmo_entity_world_rect = QRectF(
            wx - width / 2.0, wy - height / 2.0, width, height
        )

    def _load_pixmap(self, asset_path: str) -> QPixmap | None:
        if not asset_path:
            return None
        if asset_path in self._pixmap_cache:
            cached = self._pixmap_cache[asset_path]
            return cached if not cached.isNull() else None
        path = Path(asset_path)
        if not path.is_absolute():
            path = self._project_root / path
        pixmap = QPixmap(path.as_posix())
        self._pixmap_cache[asset_path] = pixmap
        return pixmap if not pixmap.isNull() else None
