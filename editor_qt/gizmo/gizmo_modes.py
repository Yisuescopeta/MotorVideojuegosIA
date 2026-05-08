"""Qt-based gizmo rendering and interaction for the editor viewport."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from math import atan2, cos, degrees, hypot, radians, sin
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication


class GizmoMode(Enum):
    NONE = auto()
    SELECT = auto()
    TRANSLATE_X = auto()
    TRANSLATE_Y = auto()
    TRANSLATE_FREE = auto()
    ROTATE_Z = auto()
    SCALE_X = auto()
    SCALE_Y = auto()
    SCALE_UNIFORM = auto()
    RECT = auto()


@dataclass
class CompletedGizmoDrag:
    entity_name: str
    component_name: str
    before_state: dict[str, float]
    after_state: dict[str, float]
    label: str


class GizmoHandle:
    """Single interactive gizmo handle with hit-test rect and behaviour mode."""

    def __init__(self, mode: GizmoMode, rect: QRectF) -> None:
        self.mode = mode
        self.rect = rect


class GizmoManager:
    """Lightweight Qt gizmo for entity transform operations.

    Designed to be rendered inside an existing QPainter transform (world coords).
    Handles are sized in world units so that they appear at constant screen size
    regardless of zoom.
    """

    AXIS_LENGTH = 50
    HANDLE_SIZE = 8
    ARROW_SIZE = 6
    SNAP_STEP = 16.0
    ROTATE_RING_RADIUS = 40
    SCALE_HANDLE_SIZE = 8
    RECT_HANDLE_SIZE = 6

    def __init__(self) -> None:
        self._mode: GizmoMode = GizmoMode.NONE
        self._handles: dict[str, GizmoHandle] = {}
        self._dragging: bool = False
        self._drag_handle: str | None = None
        self._drag_start_screen: QPointF | None = None
        self._drag_start_world: tuple[float, float] = (0.0, 0.0)
        self._current_world: tuple[float, float] = (0.0, 0.0)
        self._before_state: dict[str, float] = {}
        self._center_world: tuple[float, float] = (0.0, 0.0)
        self._drag_start_angle: float = 0.0
        self._current_angle: float = 0.0
        self._drag_start_scale: tuple[float, float] = (1.0, 1.0)
        self._current_scale: tuple[float, float] = (1.0, 1.0)
        self._drag_start_distance: float = 0.0
        self._angle_offset: float = 0.0
        self._entity_rect: QRectF | None = None
        self._entity_name: str = ""
        self._component_name: str = ""

    # -- public API -----------------------------------------------------------

    def set_mode(self, mode: GizmoMode) -> None:
        self._mode = mode
        if mode in (GizmoMode.NONE, GizmoMode.SELECT):
            self._handles.clear()

    def hit_test(self, screen_pos: QPointF) -> str | None:
        """Return handle id if *screen_pos* hits any handle, else None."""
        for handle_id, handle in self._handles.items():
            if handle.rect.contains(screen_pos):
                return handle_id
        if self._mode == GizmoMode.ROTATE_Z:
            if self._check_rotate_intersection(screen_pos):
                return "rotate_ring"
        return None

    def start_drag(
        self,
        handle_id: str,
        screen_pos: QPointF,
        world_x: float,
        world_y: float,
        *,
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        entity_name: str = "",
        component_name: str = "",
    ) -> None:
        self._dragging = True
        self._drag_handle = handle_id
        self._drag_start_screen = QPointF(screen_pos)
        self._drag_start_world = (world_x, world_y)
        self._current_world = (world_x, world_y)
        self._entity_name = entity_name
        self._component_name = component_name

        self._before_state = {
            "x": world_x,
            "y": world_y,
            "rotation": rotation,
            "scale_x": scale_x,
            "scale_y": scale_y,
        }

        self._drag_start_angle = rotation
        self._current_angle = rotation
        self._drag_start_scale = (scale_x, scale_y)
        self._current_scale = (scale_x, scale_y)

        # For rotate/scale: record initial cursor distance/angle from center
        cx, cy = self._center_world
        if self._mode == GizmoMode.ROTATE_Z:
            angle = self._angle_from_center(screen_pos)
            self._drag_start_angle = rotation
            self._angle_offset = angle - rotation
        elif self._mode in (GizmoMode.SCALE_X, GizmoMode.SCALE_Y, GizmoMode.SCALE_UNIFORM):
            self._drag_start_distance = self._distance_from_center(screen_pos)

    def update_drag(self, screen_pos: QPointF, zoom: float) -> tuple[float, float]:
        """Return current world position based on screen delta."""
        if not self._dragging or self._drag_start_screen is None:
            return self._current_world

        # Translate modes
        if self._mode in (
            GizmoMode.TRANSLATE_FREE,
            GizmoMode.TRANSLATE_X,
            GizmoMode.TRANSLATE_Y,
            GizmoMode.SELECT,
        ):
            return self._update_translate_drag(screen_pos, zoom)

        # Rotate mode
        if self._mode == GizmoMode.ROTATE_Z:
            return self._update_rotate_drag(screen_pos)

        # Scale modes
        if self._mode in (GizmoMode.SCALE_X, GizmoMode.SCALE_Y, GizmoMode.SCALE_UNIFORM):
            return self._update_scale_drag(screen_pos, zoom)

        # Rect mode
        if self._mode == GizmoMode.RECT:
            return self._update_rect_drag(screen_pos)

        return self._current_world

    def end_drag(self) -> dict[str, Any] | None:
        if not self._dragging:
            return None

        handle = self._drag_handle
        after_x = self._current_world[0]
        after_y = self._current_world[1]
        after_rotation = self._current_angle
        after_sx = self._current_scale[0]
        after_sy = self._current_scale[1]

        after_state: dict[str, float] = {
            "x": after_x,
            "y": after_y,
            "rotation": after_rotation,
            "scale_x": after_sx,
            "scale_y": after_sy,
        }

        label = self._mode_label()

        result: dict[str, Any] = {
            "handle": handle,
            "world_x": after_x,
            "world_y": after_y,
            "rotation": after_rotation,
            "scale_x": after_sx,
            "scale_y": after_sy,
            "before_state": dict(self._before_state),
            "after_state": after_state,
            "label": label,
        }

        self._dragging = False
        self._drag_handle = None
        self._drag_start_screen = None
        self._entity_name = ""
        self._component_name = ""
        self._before_state = {}

        return result

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    # -- rendering ------------------------------------------------------------

    def render(
        self, painter: QPainter, entity_world_rect: QRectF, zoom: float
    ) -> None:
        """Draw gizmo handles in world coords (painter already transformed)."""
        if self._mode in (GizmoMode.NONE, GizmoMode.SELECT):
            return

        safe_zoom = max(zoom, 0.1)
        center = entity_world_rect.center()
        center_screen = QPointF(center.x(), center.y())
        self._entity_rect = entity_world_rect

        if self._mode == GizmoMode.RECT:
            cx, cy = center.x(), center.y()
            w = entity_world_rect.width()
            h = entity_world_rect.height()
            self._center_world = (cx, cy)
            self._build_handles(center_screen, safe_zoom, rect_w=w, rect_h=h)
            self._draw_rect_gizmo(painter, center_screen, safe_zoom, w, h)
            return

        self._build_handles(center_screen, safe_zoom)

        if self._mode == GizmoMode.ROTATE_Z:
            self._draw_rotate_gizmo(painter, center_screen, safe_zoom)
            return

        if self._mode in (GizmoMode.SCALE_X, GizmoMode.SCALE_Y, GizmoMode.SCALE_UNIFORM):
            self._draw_scale_gizmo(painter, center_screen, safe_zoom)
            return

        # Default: translate gizmo (existing behaviour)
        self._draw_translate_gizmo(painter, center_screen, safe_zoom)

    # -- helper: modifier keys ------------------------------------------------

    def _is_snap_modifier(self) -> bool:
        mods = QApplication.keyboardModifiers()
        return bool(mods & Qt.KeyboardModifier.ControlModifier)

    def _is_constrain_modifier(self) -> bool:
        mods = QApplication.keyboardModifiers()
        return bool(mods & Qt.KeyboardModifier.ShiftModifier)

    # -- helper: snap ---------------------------------------------------------

    def _snap_value(self, value: float, step: float | None = None) -> float:
        step = step or self.SNAP_STEP
        if step <= 0:
            return value
        return round(value / step) * step

    # -- geometry helpers -----------------------------------------------------

    @staticmethod
    def _point_on_segment(p: QPointF, a: QPointF, b: QPointF) -> bool:
        """Check if point p lies on segment a→b within a small tolerance."""
        d = GizmoManager._distance_to_line(p, a, b)
        if d > 6.0:
            return False
        ab = hypot(b.x() - a.x(), b.y() - a.y())
        ap = hypot(p.x() - a.x(), p.y() - a.y())
        bp = hypot(p.x() - b.x(), p.y() - b.y())
        return ap <= ab and bp <= ab

    @staticmethod
    def _distance_to_line(p: QPointF, a: QPointF, b: QPointF) -> float:
        """Perpendicular distance from point p to infinite line a→b."""
        dx = b.x() - a.x()
        dy = b.y() - a.y()
        line_len_sq = dx * dx + dy * dy
        if line_len_sq == 0:
            return hypot(p.x() - a.x(), p.y() - a.y())
        t = ((p.x() - a.x()) * dx + (p.y() - a.y()) * dy) / line_len_sq
        px = a.x() + t * dx
        py = a.y() + t * dy
        return hypot(p.x() - px, p.y() - py)

    # -- angle / distance from center ----------------------------------------

    def _angle_from_center(self, screen_pos: QPointF) -> float:
        cx, cy = self._center_world
        dx = screen_pos.x() - cx
        dy = screen_pos.y() - cy
        return degrees(atan2(-dy, dx))

    def _distance_from_center(self, screen_pos: QPointF) -> float:
        cx, cy = self._center_world
        return hypot(screen_pos.x() - cx, screen_pos.y() - cy)

    # -- internal update helpers ---------------------------------------------

    def _update_translate_drag(self, screen_pos: QPointF, zoom: float) -> tuple[float, float]:
        assert self._drag_start_screen is not None
        safe_zoom = max(zoom, 0.1)
        dx = (screen_pos.x() - self._drag_start_screen.x()) / safe_zoom
        dy = (screen_pos.y() - self._drag_start_screen.y()) / safe_zoom

        handle = self._handles.get(self._drag_handle or "")
        constrained = self._is_constrain_modifier()
        if handle is not None:
            if handle.mode == GizmoMode.TRANSLATE_X:
                dy = 0.0
            elif handle.mode == GizmoMode.TRANSLATE_Y:
                dx = 0.0
            elif handle.mode == GizmoMode.TRANSLATE_FREE and constrained:
                if abs(dx) > abs(dy):
                    dy = 0.0
                else:
                    dx = 0.0

        nx = self._drag_start_world[0] + dx
        ny = self._drag_start_world[1] + dy

        if self._is_snap_modifier():
            nx = self._snap_value(nx)
            ny = self._snap_value(ny)

        self._current_world = (nx, ny)
        return (nx, ny)

    def _update_rotate_drag(self, screen_pos: QPointF) -> tuple[float, float]:
        angle = self._angle_from_center(screen_pos)
        rotation = angle - self._angle_offset

        if self._is_snap_modifier():
            rotation = self._snap_value(rotation, 15.0)

        self._current_angle = rotation
        return self._current_world

    def _update_scale_drag(self, screen_pos: QPointF, zoom: float) -> tuple[float, float]:
        cx, cy = self._center_world
        dist = self._distance_from_center(screen_pos)
        if self._drag_start_distance < 0.001:
            factor = 1.0
        else:
            factor = dist / self._drag_start_distance

        if self._is_snap_modifier():
            factor = self._snap_value(factor, 0.25)

        sx, sy = self._drag_start_scale

        if self._mode == GizmoMode.SCALE_X:
            sx = factor * sx
        elif self._mode == GizmoMode.SCALE_Y:
            sy = factor * sy
        elif self._mode == GizmoMode.SCALE_UNIFORM:
            sx = factor * sx
            sy = factor * sy

        self._current_scale = (sx, sy)
        return (cx, cy)

    def _update_rect_drag(self, screen_pos: QPointF) -> tuple[float, float]:
        assert self._drag_start_screen is not None
        safe_zoom = max(0.1, 1.0)
        dx = (screen_pos.x() - self._drag_start_screen.x()) / safe_zoom
        dy = (screen_pos.y() - self._drag_start_screen.y()) / safe_zoom

        if self._is_snap_modifier():
            dx = self._snap_value(dx)
            dy = self._snap_value(dy)

        nx = self._drag_start_world[0] + dx
        ny = self._drag_start_world[1] + dy
        self._current_world = (nx, ny)
        return (nx, ny)

    # -- mode label ----------------------------------------------------------

    def _mode_label(self) -> str:
        labels = {
            GizmoMode.TRANSLATE_FREE: "move_free",
            GizmoMode.TRANSLATE_X: "move_x",
            GizmoMode.TRANSLATE_Y: "move_y",
            GizmoMode.ROTATE_Z: "rotate_z",
            GizmoMode.SCALE_X: "scale_x",
            GizmoMode.SCALE_Y: "scale_y",
            GizmoMode.SCALE_UNIFORM: "scale_uniform",
            GizmoMode.RECT: "rect_edit",
        }
        return labels.get(self._mode, "none")

    # -- hit-test helpers -----------------------------------------------------

    def _check_rotate_intersection(self, screen_pos: QPointF) -> bool:
        cx, cy = self._center_world
        dist = hypot(screen_pos.x() - cx, screen_pos.y() - cy)
        radius = self.ROTATE_RING_RADIUS
        return abs(dist - radius) <= 6.0

    def _check_scale_intersection(self, screen_pos: QPointF, handle_point: QPointF) -> bool:
        half = self.SCALE_HANDLE_SIZE / 2.0
        return QRectF(
            handle_point.x() - half,
            handle_point.y() - half,
            self.SCALE_HANDLE_SIZE,
            self.SCALE_HANDLE_SIZE,
        ).contains(screen_pos)

    def _check_rect_intersection(self, screen_pos: QPointF) -> str | None:
        # Check handles built in _build_handles first (via hit_test),
        # but also check if point is near rect edges.
        if self._entity_rect is None:
            return None
        r = self._entity_rect
        edges = [
            (QPointF(r.left(), r.top()), QPointF(r.right(), r.top())),
            (QPointF(r.right(), r.top()), QPointF(r.right(), r.bottom())),
            (QPointF(r.right(), r.bottom()), QPointF(r.left(), r.bottom())),
            (QPointF(r.left(), r.bottom()), QPointF(r.left(), r.top())),
        ]
        for i, (a, b) in enumerate(edges):
            if self._point_on_segment(screen_pos, a, b):
                return f"rect_edge_{i}"
        return None

    # -- draw helpers ---------------------------------------------------------

    def _draw_translate_gizmo(
        self, painter: QPainter, center: QPointF, zoom: float
    ) -> None:
        axis_len = self.AXIS_LENGTH / zoom
        arrow = self.ARROW_SIZE / zoom
        pen_w = max(1.0, 2.0 / zoom)
        cx, cy = center.x(), center.y()

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
        handle_size = self.HANDLE_SIZE / zoom
        half = handle_size / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(QRectF(cx - half, cy - half, handle_size, handle_size))

        painter.restore()

    def _draw_rotate_gizmo(
        self, painter: QPainter, center: QPointF, zoom: float
    ) -> None:
        cx, cy = center.x(), center.y()
        radius = self.ROTATE_RING_RADIUS / zoom
        pen_w = max(1.0, 2.0 / zoom)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Ring
        painter.setPen(QPen(QColor("#44aaff"), pen_w))
        ring_rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
        painter.drawEllipse(ring_rect)

        # Angle indicator line (show current angle if known, else 0)
        ang = self._current_angle if self._dragging else self._drag_start_angle
        rad = radians(ang)
        end_x = cx + radius * cos(rad)
        end_y = cy - radius * sin(rad)
        painter.setPen(QPen(QColor("#ffaa44"), pen_w))
        painter.drawLine(QPointF(cx, cy), QPointF(end_x, end_y))

        # Small dot at end
        dot_r = 3.0 / zoom
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffaa44"))
        painter.drawEllipse(QPointF(end_x, end_y), dot_r, dot_r)

        painter.restore()

    def _draw_scale_gizmo(
        self, painter: QPainter, center: QPointF, zoom: float
    ) -> None:
        axis_len = self.AXIS_LENGTH / zoom
        pen_w = max(1.0, 2.0 / zoom)
        handle_half = self.SCALE_HANDLE_SIZE / zoom / 2.0
        cx, cy = center.x(), center.y()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._mode in (GizmoMode.SCALE_X, GizmoMode.SCALE_UNIFORM):
            painter.setPen(QPen(QColor("#ff4444"), pen_w))
            painter.drawLine(QPointF(cx, cy), QPointF(cx + axis_len, cy))
            painter.setPen(QPen(QColor("#ff8888"), pen_w))
            painter.setBrush(QColor("#ff4444"))
            painter.drawRect(QRectF(
                cx + axis_len - handle_half,
                cy - handle_half,
                self.SCALE_HANDLE_SIZE / zoom,
                self.SCALE_HANDLE_SIZE / zoom,
            ))
            # Negative X handle for uniform
            if self._mode == GizmoMode.SCALE_UNIFORM:
                painter.setPen(QPen(QColor("#ff8888"), pen_w))
                painter.setBrush(QColor("#ff4444"))
                painter.drawRect(QRectF(
                    cx - axis_len - handle_half,
                    cy - handle_half,
                    self.SCALE_HANDLE_SIZE / zoom,
                    self.SCALE_HANDLE_SIZE / zoom,
                ))

        if self._mode in (GizmoMode.SCALE_Y, GizmoMode.SCALE_UNIFORM):
            painter.setPen(QPen(QColor("#44ff44"), pen_w))
            painter.drawLine(QPointF(cx, cy), QPointF(cx, cy - axis_len))
            painter.setPen(QPen(QColor("#88ff88"), pen_w))
            painter.setBrush(QColor("#44ff44"))
            painter.drawRect(QRectF(
                cx - handle_half,
                cy - axis_len - handle_half,
                self.SCALE_HANDLE_SIZE / zoom,
                self.SCALE_HANDLE_SIZE / zoom,
            ))
            if self._mode == GizmoMode.SCALE_UNIFORM:
                painter.setPen(QPen(QColor("#88ff88"), pen_w))
                painter.setBrush(QColor("#44ff44"))
                painter.drawRect(QRectF(
                    cx - handle_half,
                    cy + axis_len - handle_half,
                    self.SCALE_HANDLE_SIZE / zoom,
                    self.SCALE_HANDLE_SIZE / zoom,
                ))

        # Center square
        half = self.HANDLE_SIZE / zoom / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(QRectF(cx - half, cy - half, self.HANDLE_SIZE / zoom, self.HANDLE_SIZE / zoom))

        painter.restore()

    def _draw_rect_gizmo(
        self, painter: QPainter, center: QPointF, zoom: float,
        w: float, h: float
    ) -> None:
        pen_w = max(1.0, 2.0 / zoom)
        hs = self.RECT_HANDLE_SIZE / zoom
        half = hs / 2.0
        cx, cy = center.x(), center.y()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Outline
        painter.setPen(QPen(QColor("#44aaff"), pen_w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(cx - w / 2, cy - h / 2, w, h))

        # 8 handles
        corners_and_midpoints = [
            (cx - w / 2, cy - h / 2),  # top-left
            (cx, cy - h / 2),           # top-center
            (cx + w / 2, cy - h / 2),  # top-right
            (cx + w / 2, cy),           # middle-right
            (cx + w / 2, cy + h / 2),  # bottom-right
            (cx, cy + h / 2),           # bottom-center
            (cx - w / 2, cy + h / 2),  # bottom-left
            (cx - w / 2, cy),           # middle-left
        ]

        painter.setPen(QPen(QColor("#44aaff"), 1.0))
        painter.setBrush(QColor("#ffffff"))
        for hx, hy in corners_and_midpoints:
            painter.drawRect(QRectF(hx - half, hy - half, hs, hs))

        painter.restore()

    # -- internals ------------------------------------------------------------

    def _build_handles(
        self, center: QPointF, zoom: float,
        *, rect_w: float = 0.0, rect_h: float = 0.0
    ) -> None:
        self._handles.clear()
        cx, cy = center.x(), center.y()
        self._center_world = (cx, cy)

        if self._mode in (GizmoMode.NONE, GizmoMode.SELECT):
            return

        # Translate modes: center handle + axis end handles
        if self._mode in (
            GizmoMode.TRANSLATE_FREE,
            GizmoMode.TRANSLATE_X,
            GizmoMode.TRANSLATE_Y,
        ):
            self._build_translate_handles(cx, cy, zoom)
            return

        # Rotate mode: no rect handles needed (ring is hit-tested separately)
        if self._mode == GizmoMode.ROTATE_Z:
            return

        # Scale modes: axis end handles
        if self._mode in (GizmoMode.SCALE_X, GizmoMode.SCALE_Y, GizmoMode.SCALE_UNIFORM):
            self._build_scale_handles(cx, cy, zoom)
            return

        # Rect mode: 8 corner/midpoint handles
        if self._mode == GizmoMode.RECT:
            self._build_rect_handles(cx, cy, zoom, rect_w, rect_h)
            return

    def _build_translate_handles(self, cx: float, cy: float, zoom: float) -> None:
        handle_size = self.HANDLE_SIZE / zoom
        half = handle_size / 2.0
        axis_len = self.AXIS_LENGTH / zoom
        pick_pad = 4.0 / zoom

        self._handles["center"] = GizmoHandle(
            GizmoMode.TRANSLATE_FREE,
            QRectF(
                cx - half - pick_pad,
                cy - half - pick_pad,
                handle_size + pick_pad * 2,
                handle_size + pick_pad * 2,
            ),
        )
        self._handles["x_axis"] = GizmoHandle(
            GizmoMode.TRANSLATE_X,
            QRectF(
                cx + axis_len - handle_size,
                cy - handle_size,
                handle_size * 2,
                handle_size * 2,
            ),
        )
        self._handles["y_axis"] = GizmoHandle(
            GizmoMode.TRANSLATE_Y,
            QRectF(
                cx - handle_size,
                cy - axis_len - handle_size,
                handle_size * 2,
                handle_size * 2,
            ),
        )

    def _build_scale_handles(self, cx: float, cy: float, zoom: float) -> None:
        handle_size = self.SCALE_HANDLE_SIZE / zoom
        half = handle_size / 2.0
        axis_len = self.AXIS_LENGTH / zoom
        pick_pad = 4.0 / zoom

        if self._mode in (GizmoMode.SCALE_X, GizmoMode.SCALE_UNIFORM):
            self._handles["scale_x_pos"] = GizmoHandle(
                GizmoMode.SCALE_X,
                QRectF(
                    cx + axis_len - half - pick_pad,
                    cy - half - pick_pad,
                    handle_size + pick_pad * 2,
                    handle_size + pick_pad * 2,
                ),
            )
            if self._mode == GizmoMode.SCALE_UNIFORM:
                self._handles["scale_x_neg"] = GizmoHandle(
                    GizmoMode.SCALE_X,
                    QRectF(
                        cx - axis_len - half - pick_pad,
                        cy - half - pick_pad,
                        handle_size + pick_pad * 2,
                        handle_size + pick_pad * 2,
                    ),
                )

        if self._mode in (GizmoMode.SCALE_Y, GizmoMode.SCALE_UNIFORM):
            self._handles["scale_y_pos"] = GizmoHandle(
                GizmoMode.SCALE_Y,
                QRectF(
                    cx - half - pick_pad,
                    cy - axis_len - half - pick_pad,
                    handle_size + pick_pad * 2,
                    handle_size + pick_pad * 2,
                ),
            )
            if self._mode == GizmoMode.SCALE_UNIFORM:
                self._handles["scale_y_neg"] = GizmoHandle(
                    GizmoMode.SCALE_Y,
                    QRectF(
                        cx - half - pick_pad,
                        cy + axis_len - half - pick_pad,
                        handle_size + pick_pad * 2,
                        handle_size + pick_pad * 2,
                    ),
                )

    def _build_rect_handles(
        self, cx: float, cy: float, zoom: float, w: float, h: float
    ) -> None:
        handle_size = self.RECT_HANDLE_SIZE / zoom
        half = handle_size / 2.0
        pick_pad = 4.0 / zoom

        half_w = w / 2.0
        half_h = h / 2.0

        positions: dict[str, tuple[float, float]] = {
            "rect_tl": (cx - half_w, cy - half_h),
            "rect_tc": (cx, cy - half_h),
            "rect_tr": (cx + half_w, cy - half_h),
            "rect_mr": (cx + half_w, cy),
            "rect_br": (cx + half_w, cy + half_h),
            "rect_bc": (cx, cy + half_h),
            "rect_bl": (cx - half_w, cy + half_h),
            "rect_ml": (cx - half_w, cy),
        }

        for key, (hx, hy) in positions.items():
            self._handles[key] = GizmoHandle(
                GizmoMode.RECT,
                QRectF(
                    hx - half - pick_pad,
                    hy - half - pick_pad,
                    handle_size + pick_pad * 2,
                    handle_size + pick_pad * 2,
                ),
            )
