"""Qt-based gizmo rendering and interaction for the editor viewport."""

from __future__ import annotations

from enum import Enum, auto
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen


class GizmoMode(Enum):
    NONE = auto()
    TRANSLATE_X = auto()
    TRANSLATE_Y = auto()
    TRANSLATE_FREE = auto()


class GizmoHandle:
    """Single interactive gizmo handle with hit-test rect and behaviour mode."""

    def __init__(self, mode: GizmoMode, rect: QRectF) -> None:
        self.mode = mode
        self.rect = rect


class GizmoManager:
    """Lightweight Qt gizmo for entity translate / move operations.

    Designed to be rendered inside an existing QPainter transform (world coords).
    Handles are sized in world units so that they appear at constant screen size
    regardless of zoom.
    """

    AXIS_LENGTH = 50
    HANDLE_SIZE = 8
    ARROW_SIZE = 6

    def __init__(self) -> None:
        self._mode: GizmoMode = GizmoMode.NONE
        self._handles: dict[str, GizmoHandle] = {}
        self._dragging: bool = False
        self._drag_handle: str | None = None
        self._drag_start_screen: QPointF | None = None
        self._drag_start_world: tuple[float, float] = (0.0, 0.0)
        self._current_world: tuple[float, float] = (0.0, 0.0)

    # -- public API -----------------------------------------------------------

    def set_mode(self, mode: GizmoMode) -> None:
        self._mode = mode
        if mode == GizmoMode.NONE:
            self._handles.clear()

    def hit_test(self, screen_pos: QPointF) -> str | None:
        """Return handle id if *screen_pos* hits any handle, else None."""
        for handle_id, handle in self._handles.items():
            if handle.rect.contains(screen_pos):
                return handle_id
        return None

    def start_drag(
        self, handle_id: str, screen_pos: QPointF, world_x: float, world_y: float
    ) -> None:
        self._dragging = True
        self._drag_handle = handle_id
        self._drag_start_screen = QPointF(screen_pos)
        self._drag_start_world = (world_x, world_y)
        self._current_world = (world_x, world_y)

    def update_drag(self, screen_pos: QPointF, zoom: float) -> tuple[float, float]:
        """Return current world position based on screen delta."""
        if not self._dragging or self._drag_start_screen is None:
            return self._current_world
        safe_zoom = max(zoom, 0.1)
        dx = (screen_pos.x() - self._drag_start_screen.x()) / safe_zoom
        dy = (screen_pos.y() - self._drag_start_screen.y()) / safe_zoom

        handle = self._handles.get(self._drag_handle or "")
        if handle is not None:
            if handle.mode == GizmoMode.TRANSLATE_X:
                dy = 0.0
            elif handle.mode == GizmoMode.TRANSLATE_Y:
                dx = 0.0

        nx = self._drag_start_world[0] + dx
        ny = self._drag_start_world[1] + dy
        self._current_world = (nx, ny)
        return (nx, ny)

    def end_drag(self) -> dict[str, Any] | None:
        if not self._dragging:
            return None
        result: dict[str, Any] = {
            "handle": self._drag_handle,
            "world_x": self._current_world[0],
            "world_y": self._current_world[1],
        }
        self._dragging = False
        self._drag_handle = None
        self._drag_start_screen = None
        return result

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    # -- rendering ------------------------------------------------------------

    def render(
        self, painter: QPainter, entity_world_rect: QRectF, zoom: float
    ) -> None:
        """Draw gizmo handles in world coords (painter already transformed)."""
        if self._mode == GizmoMode.NONE:
            return

        safe_zoom = max(zoom, 0.1)
        center = entity_world_rect.center()
        center_screen = QPointF(center.x(), center.y())
        self._build_handles(center_screen, safe_zoom)

        axis_len = self.AXIS_LENGTH / safe_zoom
        arrow = self.ARROW_SIZE / safe_zoom
        pen_w = max(1.0, 2.0 / safe_zoom)
        cx, cy = center_screen.x(), center_screen.y()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # X axis (red → right)
        painter.setPen(QPen(QColor("#ff4444"), pen_w))
        painter.drawLine(QPointF(cx, cy), QPointF(cx + axis_len, cy))
        painter.drawLine(
            QPointF(cx + axis_len, cy),
            QPointF(cx + axis_len - arrow, cy - arrow),
        )
        painter.drawLine(
            QPointF(cx + axis_len, cy),
            QPointF(cx + axis_len - arrow, cy + arrow),
        )

        # Y axis (green → up = -Y in screen)
        painter.setPen(QPen(QColor("#44ff44"), pen_w))
        painter.drawLine(QPointF(cx, cy), QPointF(cx, cy - axis_len))
        painter.drawLine(
            QPointF(cx, cy - axis_len),
            QPointF(cx - arrow, cy - axis_len + arrow),
        )
        painter.drawLine(
            QPointF(cx, cy - axis_len),
            QPointF(cx + arrow, cy - axis_len + arrow),
        )

        # Center square
        handle_size = self.HANDLE_SIZE / safe_zoom
        half = handle_size / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(QRectF(cx - half, cy - half, handle_size, handle_size))

        painter.restore()

    # -- internals ------------------------------------------------------------

    def _build_handles(self, center: QPointF, zoom: float) -> None:
        self._handles.clear()
        if self._mode == GizmoMode.NONE:
            return
        handle_size = self.HANDLE_SIZE / zoom
        half = handle_size / 2.0
        axis_len = self.AXIS_LENGTH / zoom
        pick_pad = 4.0 / zoom

        cx, cy = center.x(), center.y()

        self._handles["center"] = GizmoHandle(
            GizmoMode.TRANSLATE_FREE,
            QRectF(cx - half - pick_pad, cy - half - pick_pad,
                   handle_size + pick_pad * 2, handle_size + pick_pad * 2),
        )
        self._handles["x_axis"] = GizmoHandle(
            GizmoMode.TRANSLATE_X,
            QRectF(cx + axis_len - handle_size, cy - handle_size,
                   handle_size * 2, handle_size * 2),
        )
        self._handles["y_axis"] = GizmoHandle(
            GizmoMode.TRANSLATE_Y,
            QRectF(cx - handle_size, cy - axis_len - handle_size,
                   handle_size * 2, handle_size * 2),
        )
