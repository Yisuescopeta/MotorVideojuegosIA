"""Qt-native scene/game preview panel with editor camera and gizmo support."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from editor_qt.gizmo.gizmo_modes import GizmoManager, GizmoMode
from editor_qt.theme import editor_asset_path
from editor_qt.viewmodels import normalize_viewport_entity


class QtSceneViewportPanel(QWidget):
    """Authoring preview rendered by Qt only; no raylib and no game loop."""

    entity_selected = Signal(str)
    entity_moved = Signal(str, str, str, float, float)
    entity_rotated = Signal(str, str, str, float)  # entity, component, property, new_rotation
    entity_scaled = Signal(str, str, str, float, float)  # entity, component, property, new_scale_x, new_scale_y
    asset_dropped = Signal(str, float, float)  # file_path, world_x, world_y

    def __init__(self, mode: str = "Scene", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mode = mode
        self.setObjectName("ViewportPanel")
        self.setMinimumSize(420, 280)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
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
        self._hover_entity: str = ""
        self._gizmo_drag_preview: tuple[float, float] | None = None
        self._gizmo_entity_world_rect: QRectF | None = None

        # Drag state
        self._middle_dragging: bool = False
        self._drop_preview_world: tuple[float, float] | None = None
        self._theme_name = "frost_dark"
        self._chrome_mode = "Select"

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
        entity_names = {str(entity.get("name") or "") for entity in self._entities}
        if self._selected_entity and self._selected_entity not in entity_names:
            self._selected_entity = ""
            self._gizmo_entity_world_rect = None
        self.update()

    def set_gizmo_mode(self, mode_str: str) -> None:
        mapping: dict[str, GizmoMode] = {
            "Select": GizmoMode.SELECT,
            "Move": GizmoMode.TRANSLATE_FREE,
            "Rotate": GizmoMode.ROTATE_Z,
            "Scale": GizmoMode.SCALE_UNIFORM,
        }
        self._chrome_mode = mode_str
        self._gizmo.set_mode(mapping.get(mode_str, GizmoMode.SELECT))
        self.update()

    def set_selected_entity(self, entity_name: str) -> None:
        self._selected_entity = entity_name
        self._update_gizmo_rect()
        self.update()

    def set_theme_name(self, theme_name: str) -> None:
        self._theme_name = theme_name
        self.update()

    def reset_camera(self) -> None:
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._zoom = 1.0
        self._update_gizmo_rect()
        self.update()

    def set_zoom_percent(self, percent: int) -> None:
        self._zoom = max(0.1, min(5.0, float(percent) / 100.0))
        self._update_gizmo_rect()
        self.update()

    def zoom_percent(self) -> int:
        return int(round(self._zoom * 100))

    def frame_selected(self) -> None:
        entity = self._get_selected_entity_dict()
        if entity is None:
            return
        self._pan_x = -float(entity.get("x", 0.0)) * self._zoom
        self._pan_y = -float(entity.get("y", 0.0)) * self._zoom
        self._update_gizmo_rect()
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

        world_pos = self._screen_to_world(pos)
        hover_entity = self._entity_at_world(world_pos[0], world_pos[1])
        if hover_entity != self._hover_entity:
            self._hover_entity = hover_entity
            self.update()

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

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            pos = event.position()
            self._drop_preview_world = self._screen_to_world(QPointF(pos))
            self.update()
            event.acceptProposedAction()
        else:
            self._drop_preview_world = None
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        file_path = ""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
        elif event.mimeData().hasText():
            file_path = event.mimeData().text()

        if file_path:
            # Convert screen drop position to world coordinates
            drop_pos = event.position()
            world_x, world_y = self._screen_to_world(QPointF(drop_pos))
            self.asset_dropped.emit(file_path, world_x, world_y)

        self._drop_preview_world = None
        self.update()
        event.acceptProposedAction()

    # -- paint ----------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(self._color("viewport_bg")))
        self._draw_hero_background(painter)

        # Camera transform (world → screen)
        painter.save()
        painter.translate(
            QPointF(self.width() / 2.0 + self._pan_x,
                    self.height() / 2.0 + self._pan_y)
        )
        painter.scale(self._zoom, self._zoom)
        self._draw_grid(painter)
        self._draw_entities(painter)
        self._draw_drop_preview(painter)
        self._draw_gizmo(painter)
        painter.restore()

        self._draw_status(painter)
        self._draw_viewport_overlay(painter)

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

    def _draw_hero_background(self, painter: QPainter) -> None:
        hero = self._load_editor_pixmap("viewport/frozen_outpost_hero.png")
        if hero is None:
            return
        scaled = hero.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.fillRect(self.rect(), QColor(4, 17, 28, 92) if self._theme_name == "frost_dark" else QColor(216, 236, 251, 72))

    def _draw_grid(self, painter: QPainter) -> None:
        # Compute visible world area
        left = -self.width() / 2.0 / self._zoom - self._pan_x / self._zoom
        right = self.width() / 2.0 / self._zoom - self._pan_x / self._zoom
        top = -self.height() / 2.0 / self._zoom - self._pan_y / self._zoom
        bottom = self.height() / 2.0 / self._zoom - self._pan_y / self._zoom

        step = 32.0
        painter.setPen(QPen(QColor(self._color("grid")), 1.0 / self._zoom))

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
        painter.setPen(QPen(QColor(self._color("axis")), 1.0 / self._zoom))
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
                color = QColor(self._color("entity_a") if index % 2 == 0 else self._color("entity_b"))
                painter.fillRect(rect, color)
                painter.setPen(QPen(QColor(self._color("entity_border")), 1.0 / self._zoom))
                painter.drawRect(rect)

            if entity_name == self._selected_entity:
                painter.setPen(QPen(QColor(self._color("selection")), 2.0 / self._zoom))
                painter.drawRect(rect.adjusted(-2.0 / self._zoom, -2.0 / self._zoom, 2.0 / self._zoom, 2.0 / self._zoom))
            elif entity_name == self._hover_entity:
                painter.setPen(QPen(QColor(self._color("hover")), 1.5 / self._zoom))
                painter.drawRect(rect.adjusted(-1.0 / self._zoom, -1.0 / self._zoom, 1.0 / self._zoom, 1.0 / self._zoom))

            painter.setPen(QColor(self._color("text")))
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

    def _draw_drop_preview(self, painter: QPainter) -> None:
        if self._drop_preview_world is None:
            return
        wx, wy = self._drop_preview_world
        rect = QRectF(wx - 24.0, wy - 24.0, 48.0, 48.0)
        painter.fillRect(rect, QColor(self._color("ghost_fill")))
        painter.setPen(QPen(QColor(self._color("selection")), 1.5 / self._zoom, Qt.PenStyle.DashLine))
        painter.drawRect(rect)

    def _draw_status(self, painter: QPainter) -> None:
        return

    def _draw_viewport_overlay(self, painter: QPainter) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        top_left = QRectF(16, 16, 164, 34)
        self._draw_overlay_bar(painter, top_left)
        painter.setPen(QColor(self._color("text")))
        painter.drawText(QRectF(28, 16, 84, 34), Qt.AlignmentFlag.AlignVCenter, "Perspective")
        self._draw_overlay_pill(painter, QRectF(118, 21, 44, 24), "Lit", active=True)

        top_center = QRectF(self.width() / 2.0 - 110, 16, 220, 34)
        self._draw_overlay_bar(painter, top_center)
        painter.setPen(QColor(self._color("text")))
        painter.drawText(top_center, Qt.AlignmentFlag.AlignCenter, f"{self._chrome_mode}  |  Pan  |  Orbit  |  Reset")

        top_right = QRectF(self.width() - 210, 16, 194, 34)
        self._draw_overlay_bar(painter, top_right)
        painter.setPen(QColor(self._color("text")))
        painter.drawText(top_right.adjusted(12, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter, f"{self.zoom_percent()}%")
        painter.drawText(top_right.adjusted(78, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter, "Grid")
        painter.drawText(top_right.adjusted(128, 0, -12, 0), Qt.AlignmentFlag.AlignVCenter, "1x")

        axis_rect = QRectF(self.width() - 88, 82, 56, 56)
        painter.setPen(QPen(QColor(self._color("axis")), 2))
        painter.drawLine(axis_rect.center(), axis_rect.center() + QPointF(0, -18))
        painter.drawLine(axis_rect.center(), axis_rect.center() + QPointF(18, 0))
        painter.drawLine(axis_rect.center(), axis_rect.center() + QPointF(-13, 13))
        painter.setPen(QColor(self._color("text")))
        painter.drawText(axis_rect.adjusted(19, -10, 0, 0), "Y")
        painter.drawText(axis_rect.adjusted(21, 8, 0, 0), "X")
        painter.drawText(axis_rect.adjusted(-14, 16, 0, 0), "Z")

        bottom_left = QRectF(16, self.height() - 44, 218, 28)
        self._draw_overlay_bar(painter, bottom_left, bottom=True)
        painter.setPen(QColor(self._color("text")))
        painter.drawText(bottom_left, Qt.AlignmentFlag.AlignCenter, "Scene  |  Reset Camera  |  Frame Selected")

        name = str(self._scene_info.get("name") or self._scene_info.get("path") or "No scene")
        count = len(self._entities)
        dirty = "Unsaved" if self._scene_info.get("dirty") else "Saved"
        bottom_right = QRectF(self.width() - 250, self.height() - 44, 234, 28)
        self._draw_overlay_bar(painter, bottom_right, bottom=True)
        painter.setPen(QColor(self._color("muted")))
        painter.drawText(bottom_right, Qt.AlignmentFlag.AlignCenter, f"{name}  |  {count} entities  |  {dirty}")
        painter.restore()

    def _draw_overlay_pill(self, painter: QPainter, rect: QRectF, text: str, active: bool = False) -> None:
        painter.save()
        pill = self._load_editor_pixmap("chrome/active_pill.png")
        if pill is not None:
            scaled = pill.scaled(int(rect.width()), int(rect.height()), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(rect.toRect(), scaled)
        else:
            painter.setPen(QPen(QColor(self._color("chrome_border")), 1))
            painter.setBrush(QColor(self._color("selection") if active else self._color("chrome")) if active else QColor(self._color("chrome")))
            painter.drawRoundedRect(rect, 9, 9)
        painter.setPen(QColor("#ffffff" if active else self._color("text")))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def _draw_overlay_bar(self, painter: QPainter, rect: QRectF, bottom: bool = False) -> None:
        asset = "chrome/viewport_bottom_bar.png" if bottom else "chrome/viewport_top_pill.png"
        pixmap = self._load_editor_pixmap(asset)
        if pixmap is not None:
            scaled = pixmap.scaled(int(rect.width()), int(rect.height()), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(rect.toRect(), scaled)
            return
        painter.setPen(QPen(QColor(self._color("chrome_border")), 1))
        painter.setBrush(QColor(self._color("chrome")))
        painter.drawRoundedRect(rect, 10, 10)

    # -- helpers --------------------------------------------------------------

    def _get_selected_entity_dict(self) -> dict[str, Any] | None:
        for entity in self._entities:
            if entity.get("name") == self._selected_entity:
                return entity
        return None

    def _entity_at_world(self, world_x: float, world_y: float) -> str:
        point = QPointF(world_x, world_y)
        for entity in reversed(self._entities):
            if not entity.get("active", True):
                continue
            width = max(12.0, min(240.0, float(entity.get("width", 48.0))))
            height = max(12.0, min(240.0, float(entity.get("height", 48.0))))
            wx = float(entity.get("x", 0.0))
            wy = float(entity.get("y", 0.0))
            rect = QRectF(wx - width / 2.0, wy - height / 2.0, width, height)
            if rect.contains(point):
                return str(entity.get("name") or "")
        return ""

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

    def _load_editor_pixmap(self, relative_path: str) -> QPixmap | None:
        cache_key = f"editor::{relative_path}"
        if cache_key in self._pixmap_cache:
            cached = self._pixmap_cache[cache_key]
            return cached if not cached.isNull() else None
        path = editor_asset_path(*relative_path.split("/"))
        pixmap = QPixmap(path.as_posix()) if path.exists() else QPixmap()
        self._pixmap_cache[cache_key] = pixmap
        return pixmap if not pixmap.isNull() else None

    def _color(self, token: str) -> str:
        light = self._theme_name == "frost_light"
        palettes = {
            "frost_dark": {
                "viewport_bg": "#04111c",
                "grid": "#163149",
                "axis": "#2c6b96",
                "entity_a": "#315f91",
                "entity_b": "#4c6f58",
                "entity_border": "#a9c8ff",
                "selection": "#32c7ff",
                "hover": "#8fdcff",
                "text": "#d9ecff",
                "muted": "#6f8fa8",
                "chrome": "#071827",
                "chrome_border": "#2c6b96",
                "ghost_fill": "#0e4f7c",
            },
            "frost_light": {
                "viewport_bg": "#d8ecfb",
                "grid": "#b8d7eb",
                "axis": "#7db8dd",
                "entity_a": "#8ecaf0",
                "entity_b": "#a8d9c8",
                "entity_border": "#176fb7",
                "selection": "#176fb7",
                "hover": "#35bdf6",
                "text": "#17314d",
                "muted": "#486581",
                "chrome": "#eaf6ff",
                "chrome_border": "#9dc8e9",
                "ghost_fill": "#bce8ff",
            },
        }
        key = "frost_light" if light else "frost_dark"
        return palettes[key][token]
