"""
engine/editor/gizmo_system.py - Sistema de herramientas de escena y UI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional, Tuple

import pyray as rl

from engine.components.animator import Animator
from engine.components.canvas import Canvas
from engine.components.collider import Collider
from engine.components.recttransform import RectTransform
from engine.components.sprite import Sprite
from engine.components.transform import Transform
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.editor.editor_tools import EditorTool, PivotMode, SnapSettings, TransformSpace


class GizmoMode(Enum):
    NONE = auto()
    TRANSLATE_X = auto()
    TRANSLATE_Y = auto()
    TRANSLATE_FREE = auto()
    ROTATE_Z = auto()
    SCALE_X = auto()
    SCALE_Y = auto()
    SCALE_UNIFORM = auto()
    RECT_LEFT = auto()
    RECT_RIGHT = auto()
    RECT_TOP = auto()
    RECT_BOTTOM = auto()
    RECT_TOP_LEFT = auto()
    RECT_TOP_RIGHT = auto()
    RECT_BOTTOM_LEFT = auto()
    RECT_BOTTOM_RIGHT = auto()


@dataclass(frozen=True)
class CompletedGizmoDrag:
    entity_name: str
    component_name: str
    before_state: dict[str, float]
    after_state: dict[str, float]
    label: str


class GizmoSystem:
    """Dibuja y manipula gizmos de Transform y RectTransform."""

    AXIS_LENGTH: int = 50
    AXIS_THICKNESS: int = 3
    ARROW_HEAD_SIZE: int = 10
    AXIS_X_COLOR = rl.Color(220, 60, 60, 255)
    AXIS_Y_COLOR = rl.Color(60, 220, 60, 255)
    ROTATE_COLOR = rl.Color(80, 150, 255, 255)
    RECT_COLOR = rl.Color(80, 150, 255, 255)
    HOVER_COLOR = rl.Color(255, 255, 100, 255)
    CENTER_SIZE: int = 8
    ROTATE_RING_RADIUS: int = 40
    SCALE_HANDLE_SIZE: int = 8
    RECT_HANDLE_SIZE: int = 10
    PICK_TOLERANCE: float = 10.0
    MIN_SCALE: float = 0.05
    MIN_RECT_SIZE: float = 1.0
    SCALE_SENSITIVITY: float = 0.02

    def __init__(self) -> None:
        self.active_mode: GizmoMode = GizmoMode.NONE
        self.hover_mode: GizmoMode = GizmoMode.NONE
        self.is_dragging: bool = False
        self.current_tool: EditorTool = EditorTool.MOVE
        self.transform_space: TransformSpace = TransformSpace.WORLD
        self.pivot_mode: PivotMode = PivotMode.PIVOT
        self.snap_settings: SnapSettings = SnapSettings()
        self.drag_start_mouse: Tuple[float, float] = (0.0, 0.0)
        self.drag_start_pos: Tuple[float, float] = (0.0, 0.0)
        self.drag_start_rot: float = 0.0
        self.drag_start_scale: Tuple[float, float] = (1.0, 1.0)
        self.drag_origin: Tuple[float, float] = (0.0, 0.0)
        self.drag_entity_name: str = ""
        self.drag_component_name: str = ""
        self.drag_before_state: dict[str, float] | None = None
        self.drag_start_rect: dict[str, float] | None = None
        self.drag_parent_rect: dict[str, float] | None = None
        self._completed_drag: CompletedGizmoDrag | None = None

    def update(
        self,
        world: World,
        mouse_world_pos: rl.Vector2,
        tool: EditorTool | str = EditorTool.MOVE,
        transform_space: TransformSpace = TransformSpace.WORLD,
        pivot_mode: PivotMode = PivotMode.PIVOT,
        snap_settings: SnapSettings | None = None,
        *,
        ui_system: Any | None = None,
        ui_mouse_pos: rl.Vector2 | None = None,
        ui_viewport_size: tuple[float, float] | None = None,
    ) -> None:
        self.current_tool = EditorTool.from_value(tool)
        self.transform_space = transform_space
        self.pivot_mode = pivot_mode
        if snap_settings is not None:
            self.snap_settings = snap_settings

        if self.current_tool == EditorTool.HAND:
            self.active_mode = GizmoMode.NONE
            self.hover_mode = GizmoMode.NONE
            if self.is_dragging and rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                self._end_drag(None)
            return

        selected_entity = self._get_selected_entity(world)
        if not selected_entity:
            self._clear_state()
            return

        rect_transform = selected_entity.get_component(RectTransform)
        if rect_transform is not None:
            self._update_rect_gizmo(
                world,
                selected_entity,
                rect_transform,
                ui_system=ui_system,
                ui_mouse_pos=ui_mouse_pos,
                ui_viewport_size=ui_viewport_size,
            )
            return

        transform = selected_entity.get_component(Transform)
        if transform is None:
            self._clear_state()
            return
        self._update_world_gizmo(selected_entity, transform, mouse_world_pos)

    def render(
        self,
        world: World,
        tool: EditorTool | str = EditorTool.MOVE,
        transform_space: TransformSpace = TransformSpace.WORLD,
        pivot_mode: PivotMode = PivotMode.PIVOT,
    ) -> None:
        selected_entity = self._get_selected_entity(world)
        if not selected_entity:
            return
        if selected_entity.get_component(RectTransform) is not None:
            return

        transform = selected_entity.get_component(Transform)
        if transform is None:
            return

        self.current_tool = EditorTool.from_value(tool)
        self.transform_space = transform_space
        self.pivot_mode = pivot_mode

        active_tool = self._resolve_effective_tool(selected_entity)
        if active_tool == EditorTool.HAND:
            return

        origin_x, origin_y = self._get_gizmo_origin(selected_entity, transform, pivot_mode)
        if active_tool in (EditorTool.MOVE, EditorTool.TRANSFORM):
            self._draw_translate_gizmo(origin_x, origin_y, transform)
        if active_tool in (EditorTool.ROTATE, EditorTool.TRANSFORM):
            self._draw_rotate_gizmo(origin_x, origin_y, transform.rotation)
        if active_tool in (EditorTool.SCALE, EditorTool.TRANSFORM):
            self._draw_scale_gizmo(origin_x, origin_y, transform)

    def render_ui_overlay(
        self,
        world: World,
        ui_system: Any | None,
        tool: EditorTool | str = EditorTool.MOVE,
        transform_space: TransformSpace = TransformSpace.WORLD,
        ui_viewport_size: tuple[float, float] | None = None,
    ) -> None:
        selected_entity = self._get_selected_entity(world)
        if selected_entity is None or ui_system is None:
            return
        rect_transform = selected_entity.get_component(RectTransform)
        if rect_transform is None:
            return

        self.current_tool = EditorTool.from_value(tool)
        self.transform_space = transform_space
        active_tool = self._resolve_effective_tool(selected_entity)
        if active_tool == EditorTool.HAND:
            return

        if ui_viewport_size is not None and hasattr(ui_system, "ensure_layout_cache"):
            ui_system.ensure_layout_cache(world, ui_viewport_size)
        layout = ui_system.get_layout_entry(selected_entity.name, copy_result=False)
        if layout is None:
            return

        canvas_root = self._is_canvas_root(selected_entity)
        self._draw_rect_outline(layout, selected_entity, canvas_root)
        if canvas_root:
            return
        if active_tool in (EditorTool.TRANSFORM, EditorTool.RECT):
            self._draw_rect_handles(layout)
        elif active_tool == EditorTool.MOVE:
            self._draw_rect_move_handle(layout)
        elif active_tool == EditorTool.ROTATE:
            center_x, center_y = self._rect_center(layout)
            self._draw_rotate_gizmo(center_x, center_y, rect_transform.rotation)
        elif active_tool == EditorTool.SCALE:
            self._draw_rect_scale_handles(layout)

    def is_hot(self) -> bool:
        return self.hover_mode != GizmoMode.NONE or self.is_dragging

    def consume_completed_drag(self) -> CompletedGizmoDrag | None:
        drag = self._completed_drag
        self._completed_drag = None
        return drag

    def _update_world_gizmo(self, entity: Entity, transform: Transform, mouse_world_pos: rl.Vector2) -> None:
        mouse_x, mouse_y = mouse_world_pos.x, mouse_world_pos.y
        origin_x, origin_y = self._get_gizmo_origin(entity, transform, self.pivot_mode)

        if self.is_dragging and self.drag_component_name == "Transform":
            if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                self._end_drag(transform)
            else:
                snap_enabled = self._is_snap_modifier_down()
                constrain_enabled = self._is_constrain_modifier_down()
                self._handle_transform_drag(transform, mouse_x, mouse_y, snap_enabled, constrain_enabled)
            return

        self.hover_mode = self._check_transform_intersection(mouse_x, mouse_y, origin_x, origin_y, transform, self._resolve_effective_tool(entity))
        if self.hover_mode != GizmoMode.NONE and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self._start_transform_drag(entity, transform, mouse_x, mouse_y, origin_x, origin_y, self.hover_mode)

    def _update_rect_gizmo(
        self,
        world: World,
        entity: Entity,
        rect_transform: RectTransform,
        *,
        ui_system: Any | None,
        ui_mouse_pos: rl.Vector2 | None,
        ui_viewport_size: tuple[float, float] | None,
    ) -> None:
        effective_tool = self._resolve_effective_tool(entity)
        if ui_system is None or ui_mouse_pos is None:
            self.hover_mode = GizmoMode.NONE
            if not self.is_dragging:
                self.active_mode = GizmoMode.NONE
            return
        if ui_viewport_size is not None and hasattr(ui_system, "ensure_layout_cache"):
            ui_system.ensure_layout_cache(world, ui_viewport_size)
        layout = ui_system.get_layout_entry(entity.name, copy_result=False)
        if layout is None:
            self.hover_mode = GizmoMode.NONE
            return

        canvas_root = self._is_canvas_root(entity)
        if self.is_dragging and self.drag_component_name == "RectTransform":
            if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                self._end_drag(rect_transform)
            else:
                snap_enabled = self._is_snap_modifier_down()
                constrain_enabled = self._is_constrain_modifier_down()
                self._handle_rect_drag(rect_transform, ui_mouse_pos.x, ui_mouse_pos.y, effective_tool, snap_enabled, constrain_enabled)
            return

        self.hover_mode = self._check_rect_intersection(ui_mouse_pos.x, ui_mouse_pos.y, layout, effective_tool, rect_transform, canvas_root)
        if self.hover_mode != GizmoMode.NONE and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            parent_rect = ui_system.get_parent_layout_entry(world, entity.name, copy_result=False)
            if parent_rect is None:
                parent_rect = ui_system.get_layout_entry(layout.get("canvas", entity.name), copy_result=False)
            self._start_rect_drag(
                entity,
                rect_transform,
                layout=layout,
                parent_rect=parent_rect,
                mode=self.hover_mode,
                mouse_x=ui_mouse_pos.x,
                mouse_y=ui_mouse_pos.y,
            )

    def _resolve_effective_tool(self, entity: Entity) -> EditorTool:
        if entity.get_component(RectTransform) is not None and self.current_tool == EditorTool.TRANSFORM:
            return EditorTool.RECT
        return self.current_tool

    def _get_selected_entity(self, world: World) -> Optional[Entity]:
        if not world.selected_entity_name:
            return None
        return world.get_entity_by_name(world.selected_entity_name)

    def _draw_translate_gizmo(self, x: float, y: float, transform: Transform) -> None:
        x_axis, y_axis = self._get_axes(transform)
        color_x = self.HOVER_COLOR if self.hover_mode == GizmoMode.TRANSLATE_X or self.active_mode == GizmoMode.TRANSLATE_X else self.AXIS_X_COLOR
        color_y = self.HOVER_COLOR if self.hover_mode == GizmoMode.TRANSLATE_Y or self.active_mode == GizmoMode.TRANSLATE_Y else self.AXIS_Y_COLOR
        center_color = self.HOVER_COLOR if self.hover_mode == GizmoMode.TRANSLATE_FREE or self.active_mode == GizmoMode.TRANSLATE_FREE else rl.WHITE
        self._draw_axis(x, y, x_axis, color_x)
        self._draw_axis(x, y, y_axis, color_y)
        rl.draw_rectangle(int(x - self.CENTER_SIZE / 2), int(y - self.CENTER_SIZE / 2), self.CENTER_SIZE, self.CENTER_SIZE, center_color)

    def _draw_rotate_gizmo(self, x: float, y: float, rotation: float) -> None:
        color = self.HOVER_COLOR if self.hover_mode == GizmoMode.ROTATE_Z or self.active_mode == GizmoMode.ROTATE_Z else self.ROTATE_COLOR
        rl.draw_circle_lines(int(x), int(y), self.ROTATE_RING_RADIUS, color)
        rl.draw_circle(int(x), int(y), 2, rl.WHITE)
        rad = math.radians(rotation)
        end_x = x + math.cos(rad) * self.ROTATE_RING_RADIUS
        end_y = y - math.sin(rad) * self.ROTATE_RING_RADIUS
        rl.draw_line(int(x), int(y), int(end_x), int(end_y), rl.Color(255, 255, 255, 128))

    def _draw_scale_gizmo(self, x: float, y: float, transform: Transform) -> None:
        x_axis, y_axis = self._get_axes(transform)
        color_x = self.HOVER_COLOR if self.hover_mode == GizmoMode.SCALE_X or self.active_mode == GizmoMode.SCALE_X else self.AXIS_X_COLOR
        color_y = self.HOVER_COLOR if self.hover_mode == GizmoMode.SCALE_Y or self.active_mode == GizmoMode.SCALE_Y else self.AXIS_Y_COLOR
        color_c = self.HOVER_COLOR if self.hover_mode == GizmoMode.SCALE_UNIFORM or self.active_mode == GizmoMode.SCALE_UNIFORM else rl.WHITE
        self._draw_axis(x, y, x_axis, color_x, with_arrow=False)
        self._draw_axis(x, y, y_axis, color_y, with_arrow=False)
        x_end = self._point_along_axis(x, y, x_axis, self.AXIS_LENGTH)
        y_end = self._point_along_axis(x, y, y_axis, self.AXIS_LENGTH)
        rl.draw_rectangle(int(x_end.x - 4), int(x_end.y - 4), 8, 8, color_x)
        rl.draw_rectangle(int(y_end.x - 4), int(y_end.y - 4), 8, 8, color_y)
        rl.draw_rectangle(int(x - 6), int(y - 6), 12, 12, color_c)

    def _draw_axis(self, x: float, y: float, axis: rl.Vector2, color: rl.Color, with_arrow: bool = True) -> None:
        origin = rl.Vector2(x, y)
        end = self._point_along_axis(x, y, axis, self.AXIS_LENGTH)
        rl.draw_line_ex(origin, end, self.AXIS_THICKNESS, color)
        if not with_arrow:
            return
        arrow = self._point_along_axis(x, y, axis, self.AXIS_LENGTH + self.ARROW_HEAD_SIZE)
        perp = rl.Vector2(-axis.y, axis.x)
        rl.draw_triangle(
            arrow,
            rl.Vector2(end.x + perp.x * 5.0, end.y + perp.y * 5.0),
            rl.Vector2(end.x - perp.x * 5.0, end.y - perp.y * 5.0),
            color,
        )

    def _draw_rect_outline(self, layout: dict[str, Any], entity: Entity, canvas_root: bool) -> None:
        rect = rl.Rectangle(float(layout["x"]), float(layout["y"]), float(layout["width"]), float(layout["height"]))
        color = self.HOVER_COLOR if self.hover_mode != GizmoMode.NONE or self.is_dragging else self.RECT_COLOR
        thickness = 2 if not canvas_root else 1
        rl.draw_rectangle_lines_ex(rect, thickness, color)
        if canvas_root:
            rl.draw_text(entity.name, int(rect.x + 6), int(rect.y + 6), 10, rl.Color(210, 210, 210, 255))

    def _draw_rect_handles(self, layout: dict[str, Any]) -> None:
        self._draw_rect_move_handle(layout)
        for mode, point in self._rect_handle_positions(layout).items():
            self._draw_rect_handle(point, self.hover_mode == mode or self.active_mode == mode)

    def _draw_rect_move_handle(self, layout: dict[str, Any]) -> None:
        center = rl.Vector2(*self._rect_center(layout))
        active = self.hover_mode == GizmoMode.TRANSLATE_FREE or self.active_mode == GizmoMode.TRANSLATE_FREE
        size = self.CENTER_SIZE + 4
        color = self.HOVER_COLOR if active else rl.WHITE
        rl.draw_rectangle(int(center.x - size / 2), int(center.y - size / 2), size, size, color)

    def _draw_rect_scale_handles(self, layout: dict[str, Any]) -> None:
        handles = {
            GizmoMode.SCALE_X: rl.Vector2(float(layout["x"] + layout["width"]), float(layout["y"] + layout["height"] * 0.5)),
            GizmoMode.SCALE_Y: rl.Vector2(float(layout["x"] + layout["width"] * 0.5), float(layout["y"])),
            GizmoMode.SCALE_UNIFORM: rl.Vector2(float(layout["x"] + layout["width"]), float(layout["y"])),
        }
        for mode, point in handles.items():
            self._draw_rect_handle(point, self.hover_mode == mode or self.active_mode == mode)

    def _draw_rect_handle(self, point: rl.Vector2, active: bool) -> None:
        size = self.RECT_HANDLE_SIZE
        color = self.HOVER_COLOR if active else rl.WHITE
        rl.draw_rectangle(int(point.x - size / 2), int(point.y - size / 2), size, size, color)
        rl.draw_rectangle_lines(int(point.x - size / 2), int(point.y - size / 2), size, size, rl.Color(20, 20, 20, 220))

    def _check_transform_intersection(
        self,
        mx: float,
        my: float,
        ox: float,
        oy: float,
        transform: Transform,
        tool: EditorTool,
    ) -> GizmoMode:
        x_axis, y_axis = self._get_axes(transform)
        point = rl.Vector2(mx, my)
        origin = rl.Vector2(ox, oy)
        if tool in (EditorTool.MOVE, EditorTool.TRANSFORM):
            if self._point_in_square(point, origin, self.CENTER_SIZE + 8):
                return GizmoMode.TRANSLATE_FREE
            if self._distance_to_axis(point, origin, x_axis) <= self.PICK_TOLERANCE:
                return GizmoMode.TRANSLATE_X
            if self._distance_to_axis(point, origin, y_axis) <= self.PICK_TOLERANCE:
                return GizmoMode.TRANSLATE_Y
        if tool in (EditorTool.ROTATE, EditorTool.TRANSFORM):
            dist = math.dist((mx, my), (ox, oy))
            if abs(dist - self.ROTATE_RING_RADIUS) <= self.PICK_TOLERANCE:
                return GizmoMode.ROTATE_Z
        if tool == EditorTool.SCALE:
            if self._point_in_square(point, origin, 12):
                return GizmoMode.SCALE_UNIFORM
            if self._point_in_square(point, self._point_along_axis(ox, oy, x_axis, self.AXIS_LENGTH), 12):
                return GizmoMode.SCALE_X
            if self._point_in_square(point, self._point_along_axis(ox, oy, y_axis, self.AXIS_LENGTH), 12):
                return GizmoMode.SCALE_Y
        return GizmoMode.NONE

    def _check_rect_intersection(
        self,
        mx: float,
        my: float,
        layout: dict[str, Any],
        tool: EditorTool,
        rect_transform: RectTransform,
        canvas_root: bool,
    ) -> GizmoMode:
        point = rl.Vector2(mx, my)
        rect = rl.Rectangle(float(layout["x"]), float(layout["y"]), float(layout["width"]), float(layout["height"]))
        center = rl.Vector2(*self._rect_center(layout))
        if tool == EditorTool.MOVE:
            return GizmoMode.TRANSLATE_FREE if self._point_in_rect(point, rect) else GizmoMode.NONE
        if tool == EditorTool.RECT:
            if canvas_root:
                return GizmoMode.NONE
            for mode, handle_point in self._rect_handle_positions(layout).items():
                if self._point_in_square(point, handle_point, self.RECT_HANDLE_SIZE + 4):
                    return mode
            if self._point_in_rect(point, rect):
                return GizmoMode.TRANSLATE_FREE
            return GizmoMode.NONE
        if tool == EditorTool.ROTATE:
            del rect_transform
            radius = max(float(layout["width"]), float(layout["height"])) * 0.5 + 18.0
            dist = math.dist((mx, my), (center.x, center.y))
            if abs(dist - radius) <= self.PICK_TOLERANCE:
                return GizmoMode.ROTATE_Z
            return GizmoMode.NONE
        if tool == EditorTool.SCALE:
            scale_handles = {
                GizmoMode.SCALE_X: rl.Vector2(float(layout["x"] + layout["width"]), float(layout["y"] + layout["height"] * 0.5)),
                GizmoMode.SCALE_Y: rl.Vector2(float(layout["x"] + layout["width"] * 0.5), float(layout["y"])),
                GizmoMode.SCALE_UNIFORM: rl.Vector2(float(layout["x"] + layout["width"]), float(layout["y"])),
            }
            for mode, handle_point in scale_handles.items():
                if self._point_in_square(point, handle_point, self.RECT_HANDLE_SIZE + 4):
                    return mode
            return GizmoMode.NONE
        return GizmoMode.NONE

    def _distance_to_axis(self, point: rl.Vector2, origin: rl.Vector2, axis: rl.Vector2) -> float:
        rel_x = point.x - origin.x
        rel_y = point.y - origin.y
        projection = rel_x * axis.x + rel_y * axis.y
        if projection < 0.0 or projection > self.AXIS_LENGTH + self.ARROW_HEAD_SIZE:
            return float("inf")
        closest_x = origin.x + axis.x * projection
        closest_y = origin.y + axis.y * projection
        return math.dist((point.x, point.y), (closest_x, closest_y))

    def _point_in_square(self, point: rl.Vector2, center: rl.Vector2, size: float) -> bool:
        half = size / 2.0
        return center.x - half <= point.x <= center.x + half and center.y - half <= point.y <= center.y + half

    def _point_in_rect(self, point: rl.Vector2, rect: rl.Rectangle) -> bool:
        return rect.x <= point.x <= rect.x + rect.width and rect.y <= point.y <= rect.y + rect.height

    def _start_transform_drag(
        self,
        entity: Entity,
        transform: Transform,
        mx: float,
        my: float,
        origin_x: float,
        origin_y: float,
        mode: GizmoMode,
    ) -> None:
        self.is_dragging = True
        self.active_mode = mode
        self.drag_start_mouse = (mx, my)
        self.drag_start_pos = (transform.x, transform.y)
        self.drag_start_rot = transform.rotation
        self.drag_start_scale = (transform.scale_x, transform.scale_y)
        self.drag_origin = (origin_x, origin_y)
        self.drag_entity_name = entity.name
        self.drag_component_name = "Transform"
        self.drag_before_state = self._capture_transform_state(transform)

    def _start_rect_drag(
        self,
        entity: Entity,
        rect_transform: RectTransform,
        *,
        layout: dict[str, Any],
        parent_rect: dict[str, Any] | None,
        mode: GizmoMode,
        mouse_x: float,
        mouse_y: float,
    ) -> None:
        self.is_dragging = True
        self.active_mode = mode
        self.drag_start_mouse = (mouse_x, mouse_y)
        self.drag_start_pos = (float(layout["x"]), float(layout["y"]))
        center_x, center_y = self._rect_center(layout)
        self.drag_origin = (center_x, center_y)
        self.drag_start_rot = rect_transform.rotation
        self.drag_start_scale = (rect_transform.scale_x, rect_transform.scale_y)
        self.drag_start_rect = {
            "x": float(layout["x"]),
            "y": float(layout["y"]),
            "width": float(layout["width"]),
            "height": float(layout["height"]),
        }
        self.drag_parent_rect = dict(parent_rect) if parent_rect is not None else None
        self.drag_entity_name = entity.name
        self.drag_component_name = "RectTransform"
        self.drag_before_state = self._capture_rect_transform_state(rect_transform)

    def _handle_transform_drag(self, transform: Transform, mx: float, my: float, snap_enabled: bool, constrain_enabled: bool) -> None:
        start_mx, start_my = self.drag_start_mouse
        start_px, start_py = self.drag_start_pos
        origin_x, origin_y = self.drag_origin
        x_axis, y_axis = self._get_axes(transform)
        mouse_delta = rl.Vector2(mx - start_mx, my - start_my)

        if self.active_mode == GizmoMode.TRANSLATE_X:
            amount = self._project(mouse_delta, x_axis)
            if snap_enabled:
                amount = self._snap(amount, self.snap_settings.move_step)
            transform.x = start_px + x_axis.x * amount
            transform.y = start_py + x_axis.y * amount
        elif self.active_mode == GizmoMode.TRANSLATE_Y:
            amount = self._project(mouse_delta, y_axis)
            if snap_enabled:
                amount = self._snap(amount, self.snap_settings.move_step)
            transform.x = start_px + y_axis.x * amount
            transform.y = start_py + y_axis.y * amount
        elif self.active_mode == GizmoMode.TRANSLATE_FREE:
            move = rl.Vector2(mouse_delta.x, mouse_delta.y)
            if constrain_enabled:
                move = self._constrain_move(move, x_axis, y_axis)
            if snap_enabled:
                move = rl.Vector2(
                    self._snap(move.x, self.snap_settings.move_step),
                    self._snap(move.y, self.snap_settings.move_step),
                )
            transform.x = start_px + move.x
            transform.y = start_py + move.y
        elif self.active_mode == GizmoMode.ROTATE_Z:
            angle_start = math.degrees(math.atan2(origin_y - start_my, start_mx - origin_x))
            angle_curr = math.degrees(math.atan2(origin_y - my, mx - origin_x))
            rotation = self.drag_start_rot + (angle_curr - angle_start)
            if snap_enabled:
                rotation = self._snap(rotation, self.snap_settings.rotate_step)
            transform.rotation = rotation
        elif self.active_mode == GizmoMode.SCALE_X:
            scale_delta = self._project(mouse_delta, x_axis) * self.SCALE_SENSITIVITY
            new_scale_x = self.drag_start_scale[0] + scale_delta
            if snap_enabled:
                new_scale_x = self._snap(new_scale_x, self.snap_settings.scale_step)
            transform.scale_x = max(self.MIN_SCALE, new_scale_x)
        elif self.active_mode == GizmoMode.SCALE_Y:
            scale_delta = self._project(mouse_delta, y_axis) * self.SCALE_SENSITIVITY
            new_scale_y = self.drag_start_scale[1] + scale_delta
            if snap_enabled:
                new_scale_y = self._snap(new_scale_y, self.snap_settings.scale_step)
            transform.scale_y = max(self.MIN_SCALE, new_scale_y)
        elif self.active_mode == GizmoMode.SCALE_UNIFORM:
            proj_x = self._project(mouse_delta, x_axis)
            proj_y = self._project(mouse_delta, y_axis)
            uniform_delta = (proj_x + proj_y) * 0.5 * self.SCALE_SENSITIVITY
            if constrain_enabled:
                uniform_delta = max(proj_x, proj_y, key=abs) * self.SCALE_SENSITIVITY
            new_scale_x = self.drag_start_scale[0] + uniform_delta
            new_scale_y = self.drag_start_scale[1] + uniform_delta
            if snap_enabled:
                new_scale_x = self._snap(new_scale_x, self.snap_settings.scale_step)
                new_scale_y = self._snap(new_scale_y, self.snap_settings.scale_step)
            transform.scale_x = max(self.MIN_SCALE, new_scale_x)
            transform.scale_y = max(self.MIN_SCALE, new_scale_y)

    def _handle_rect_drag(
        self,
        rect_transform: RectTransform,
        mx: float,
        my: float,
        effective_tool: EditorTool,
        snap_enabled: bool,
        constrain_enabled: bool,
    ) -> None:
        start_mx, start_my = self.drag_start_mouse
        dx = mx - start_mx
        dy = my - start_my

        if effective_tool in (EditorTool.RECT, EditorTool.MOVE):
            if self.drag_start_rect is None or self.drag_parent_rect is None:
                return
            rect = dict(self.drag_start_rect)
            left = rect["x"]
            top = rect["y"]
            right = rect["x"] + rect["width"]
            bottom = rect["y"] + rect["height"]

            if self.active_mode == GizmoMode.TRANSLATE_FREE:
                if constrain_enabled:
                    if abs(dx) >= abs(dy):
                        dy = 0.0
                    else:
                        dx = 0.0
                left += dx
                right += dx
                top += dy
                bottom += dy
            elif self.active_mode == GizmoMode.RECT_LEFT:
                left += dx
            elif self.active_mode == GizmoMode.RECT_RIGHT:
                right += dx
            elif self.active_mode == GizmoMode.RECT_TOP:
                top += dy
            elif self.active_mode == GizmoMode.RECT_BOTTOM:
                bottom += dy
            elif self.active_mode == GizmoMode.RECT_TOP_LEFT:
                left += dx
                top += dy
            elif self.active_mode == GizmoMode.RECT_TOP_RIGHT:
                right += dx
                top += dy
            elif self.active_mode == GizmoMode.RECT_BOTTOM_LEFT:
                left += dx
                bottom += dy
            elif self.active_mode == GizmoMode.RECT_BOTTOM_RIGHT:
                right += dx
                bottom += dy

            if right - left < self.MIN_RECT_SIZE:
                if self.active_mode in (GizmoMode.RECT_LEFT, GizmoMode.RECT_TOP_LEFT, GizmoMode.RECT_BOTTOM_LEFT):
                    left = right - self.MIN_RECT_SIZE
                else:
                    right = left + self.MIN_RECT_SIZE
            if bottom - top < self.MIN_RECT_SIZE:
                if self.active_mode in (GizmoMode.RECT_TOP, GizmoMode.RECT_TOP_LEFT, GizmoMode.RECT_TOP_RIGHT):
                    top = bottom - self.MIN_RECT_SIZE
                else:
                    bottom = top + self.MIN_RECT_SIZE

            self._apply_visual_rect_to_rect_transform(rect_transform, self.drag_parent_rect, left, top, right, bottom, snap_enabled)
            return

        center_x, center_y = self.drag_origin
        x_axis, y_axis = self._get_rect_axes(rect_transform)
        mouse_delta = rl.Vector2(mx - start_mx, my - start_my)
        if self.active_mode == GizmoMode.ROTATE_Z:
            angle_start = math.degrees(math.atan2(center_y - start_my, start_mx - center_x))
            angle_curr = math.degrees(math.atan2(center_y - my, mx - center_x))
            rotation = self.drag_start_rot + (angle_curr - angle_start)
            if snap_enabled:
                rotation = self._snap(rotation, self.snap_settings.rotate_step)
            rect_transform.rotation = rotation
        elif self.active_mode == GizmoMode.SCALE_X:
            scale_delta = self._project(mouse_delta, x_axis) * self.SCALE_SENSITIVITY
            new_scale_x = self.drag_start_scale[0] + scale_delta
            if snap_enabled:
                new_scale_x = self._snap(new_scale_x, self.snap_settings.scale_step)
            rect_transform.scale_x = max(self.MIN_SCALE, new_scale_x)
        elif self.active_mode == GizmoMode.SCALE_Y:
            scale_delta = self._project(mouse_delta, y_axis) * self.SCALE_SENSITIVITY
            new_scale_y = self.drag_start_scale[1] + scale_delta
            if snap_enabled:
                new_scale_y = self._snap(new_scale_y, self.snap_settings.scale_step)
            rect_transform.scale_y = max(self.MIN_SCALE, new_scale_y)
        elif self.active_mode == GizmoMode.SCALE_UNIFORM:
            proj_x = self._project(mouse_delta, x_axis)
            proj_y = self._project(mouse_delta, y_axis)
            uniform_delta = (proj_x + proj_y) * 0.5 * self.SCALE_SENSITIVITY
            if constrain_enabled:
                uniform_delta = max(proj_x, proj_y, key=abs) * self.SCALE_SENSITIVITY
            new_scale_x = self.drag_start_scale[0] + uniform_delta
            new_scale_y = self.drag_start_scale[1] + uniform_delta
            if snap_enabled:
                new_scale_x = self._snap(new_scale_x, self.snap_settings.scale_step)
                new_scale_y = self._snap(new_scale_y, self.snap_settings.scale_step)
            rect_transform.scale_x = max(self.MIN_SCALE, new_scale_x)
            rect_transform.scale_y = max(self.MIN_SCALE, new_scale_y)

    def _apply_visual_rect_to_rect_transform(
        self,
        rect_transform: RectTransform,
        parent_rect: dict[str, float],
        left: float,
        top: float,
        right: float,
        bottom: float,
        snap_enabled: bool,
    ) -> None:
        visual_width = max(self.MIN_RECT_SIZE, right - left)
        visual_height = max(self.MIN_RECT_SIZE, bottom - top)
        parent_scale_x = max(0.0001, abs(float(parent_rect.get("scale_x", 1.0))))
        parent_scale_y = max(0.0001, abs(float(parent_rect.get("scale_y", 1.0))))
        rect_scale_x = max(0.0001, abs(float(rect_transform.scale_x)))
        rect_scale_y = max(0.0001, abs(float(rect_transform.scale_y)))

        anchor_min_x = max(0.0, min(1.0, rect_transform.anchor_min_x))
        anchor_min_y = max(0.0, min(1.0, rect_transform.anchor_min_y))
        anchor_max_x = max(anchor_min_x, min(1.0, rect_transform.anchor_max_x))
        anchor_max_y = max(anchor_min_y, min(1.0, rect_transform.anchor_max_y))
        anchor_left = float(parent_rect["x"]) + float(parent_rect["width"]) * anchor_min_x
        anchor_top = float(parent_rect["y"]) + float(parent_rect["height"]) * anchor_min_y
        anchor_width = float(parent_rect["width"]) * (anchor_max_x - anchor_min_x)
        anchor_height = float(parent_rect["height"]) * (anchor_max_y - anchor_min_y)

        new_width = max(self.MIN_RECT_SIZE, (visual_width / rect_scale_x - anchor_width) / parent_scale_x)
        new_height = max(self.MIN_RECT_SIZE, (visual_height / rect_scale_y - anchor_height) / parent_scale_y)

        pivot_x = max(0.0, min(1.0, rect_transform.pivot_x))
        pivot_y = max(0.0, min(1.0, rect_transform.pivot_y))
        pivot_pos_x = left + visual_width * pivot_x
        pivot_pos_y = top + visual_height * pivot_y
        anchored_x = (pivot_pos_x - anchor_left - anchor_width * pivot_x) / parent_scale_x
        anchored_y = (pivot_pos_y - anchor_top - anchor_height * pivot_y) / parent_scale_y

        if snap_enabled:
            anchored_x = self._snap(anchored_x, self.snap_settings.move_step)
            anchored_y = self._snap(anchored_y, self.snap_settings.move_step)
            new_width = max(self.MIN_RECT_SIZE, self._snap(new_width, self.snap_settings.move_step))
            new_height = max(self.MIN_RECT_SIZE, self._snap(new_height, self.snap_settings.move_step))

        rect_transform.anchored_x = anchored_x
        rect_transform.anchored_y = anchored_y
        rect_transform.width = new_width
        rect_transform.height = new_height

    def _end_drag(self, component: Any | None) -> None:
        if component is not None and self.drag_before_state is not None:
            if self.drag_component_name == "Transform":
                after_state = self._capture_transform_state(component)
                label = f"transform:{self.drag_entity_name}"
            else:
                after_state = self._capture_rect_transform_state(component)
                label = f"rect_transform:{self.drag_entity_name}"
            if after_state != self.drag_before_state:
                self._completed_drag = CompletedGizmoDrag(
                    entity_name=self.drag_entity_name,
                    component_name=self.drag_component_name,
                    before_state=dict(self.drag_before_state),
                    after_state=after_state,
                    label=label,
                )
        self._clear_state(keep_completed_drag=True)

    def _clear_state(self, keep_completed_drag: bool = True) -> None:
        if not keep_completed_drag:
            self._completed_drag = None
        self.is_dragging = False
        self.active_mode = GizmoMode.NONE
        self.hover_mode = GizmoMode.NONE
        self.drag_before_state = None
        self.drag_entity_name = ""
        self.drag_component_name = ""
        self.drag_start_rect = None
        self.drag_parent_rect = None

    def _capture_transform_state(self, transform: Transform) -> dict[str, float]:
        return {
            "x": float(transform.local_x),
            "y": float(transform.local_y),
            "rotation": float(transform.local_rotation),
            "scale_x": float(transform.local_scale_x),
            "scale_y": float(transform.local_scale_y),
        }

    def _capture_rect_transform_state(self, rect_transform: RectTransform) -> dict[str, float]:
        return {
            "anchored_x": float(rect_transform.anchored_x),
            "anchored_y": float(rect_transform.anchored_y),
            "width": float(rect_transform.width),
            "height": float(rect_transform.height),
            "rotation": float(rect_transform.rotation),
            "scale_x": float(rect_transform.scale_x),
            "scale_y": float(rect_transform.scale_y),
        }

    def _get_axes(self, transform: Transform) -> tuple[rl.Vector2, rl.Vector2]:
        if self.transform_space == TransformSpace.WORLD:
            return rl.Vector2(1.0, 0.0), rl.Vector2(0.0, -1.0)
        radians = math.radians(transform.rotation)
        cos_r = math.cos(radians)
        sin_r = math.sin(radians)
        x_axis = rl.Vector2(cos_r, -sin_r)
        y_axis = rl.Vector2(sin_r, -cos_r)
        return self._normalize(x_axis), self._normalize(y_axis)

    def _get_rect_axes(self, rect_transform: RectTransform) -> tuple[rl.Vector2, rl.Vector2]:
        if self.transform_space == TransformSpace.WORLD:
            return rl.Vector2(1.0, 0.0), rl.Vector2(0.0, -1.0)
        radians = math.radians(rect_transform.rotation)
        cos_r = math.cos(radians)
        sin_r = math.sin(radians)
        x_axis = rl.Vector2(cos_r, -sin_r)
        y_axis = rl.Vector2(sin_r, -cos_r)
        return self._normalize(x_axis), self._normalize(y_axis)

    def _normalize(self, vector: rl.Vector2) -> rl.Vector2:
        length = math.sqrt(vector.x * vector.x + vector.y * vector.y)
        if length <= 0.0001:
            return rl.Vector2(1.0, 0.0)
        return rl.Vector2(vector.x / length, vector.y / length)

    def _point_along_axis(self, x: float, y: float, axis: rl.Vector2, distance: float) -> rl.Vector2:
        return rl.Vector2(x + axis.x * distance, y + axis.y * distance)

    def _project(self, vector: rl.Vector2, axis: rl.Vector2) -> float:
        return vector.x * axis.x + vector.y * axis.y

    def _constrain_move(self, move: rl.Vector2, x_axis: rl.Vector2, y_axis: rl.Vector2) -> rl.Vector2:
        amount_x = self._project(move, x_axis)
        amount_y = self._project(move, y_axis)
        if abs(amount_x) >= abs(amount_y):
            return rl.Vector2(x_axis.x * amount_x, x_axis.y * amount_x)
        return rl.Vector2(y_axis.x * amount_y, y_axis.y * amount_y)

    def _snap(self, value: float, step: float) -> float:
        if step <= 0.0:
            return value
        return round(value / step) * step

    def _is_snap_modifier_down(self) -> bool:
        return rl.is_key_down(rl.KEY_LEFT_CONTROL) or rl.is_key_down(rl.KEY_RIGHT_CONTROL)

    def _is_constrain_modifier_down(self) -> bool:
        return rl.is_key_down(rl.KEY_LEFT_SHIFT) or rl.is_key_down(rl.KEY_RIGHT_SHIFT)

    def _get_gizmo_origin(self, entity: Entity, transform: Transform, pivot_mode: PivotMode) -> tuple[float, float]:
        if pivot_mode == PivotMode.PIVOT:
            return transform.x, transform.y
        bounds = self._compute_entity_bounds(entity, transform)
        if bounds is None:
            return transform.x, transform.y
        left, top, width, height = bounds
        return left + width * 0.5, top + height * 0.5

    def _compute_entity_bounds(self, entity: Entity, transform: Transform) -> tuple[float, float, float, float] | None:
        width = 0.0
        height = 0.0
        center_offset_x = 0.0
        center_offset_y = 0.0

        sprite = entity.get_component(Sprite)
        animator = entity.get_component(Animator)
        collider = entity.get_component(Collider)
        if sprite is not None:
            width = float(sprite.width or (animator.frame_width if animator is not None else 32))
            height = float(sprite.height or (animator.frame_height if animator is not None else 32))
            center_offset_x = (0.5 - float(sprite.origin_x)) * width * transform.scale_x
            center_offset_y = (float(sprite.origin_y) - 0.5) * height * transform.scale_y
        elif animator is not None:
            width = float(animator.frame_width)
            height = float(animator.frame_height)
        elif collider is not None:
            width = float(collider.width)
            height = float(collider.height)
            center_offset_x = float(collider.offset_x)
            center_offset_y = float(collider.offset_y)

        if width <= 0.0 or height <= 0.0:
            return None

        width *= abs(transform.scale_x)
        height *= abs(transform.scale_y)
        center_x = transform.x + center_offset_x
        center_y = transform.y + center_offset_y
        return center_x - width * 0.5, center_y - height * 0.5, width, height

    def _rect_center(self, layout: dict[str, Any]) -> tuple[float, float]:
        return (
            float(layout["x"]) + float(layout["width"]) * 0.5,
            float(layout["y"]) + float(layout["height"]) * 0.5,
        )

    def _rect_handle_positions(self, layout: dict[str, Any]) -> dict[GizmoMode, rl.Vector2]:
        left = float(layout["x"])
        top = float(layout["y"])
        right = left + float(layout["width"])
        bottom = top + float(layout["height"])
        center_x = left + float(layout["width"]) * 0.5
        center_y = top + float(layout["height"]) * 0.5
        return {
            GizmoMode.RECT_LEFT: rl.Vector2(left, center_y),
            GizmoMode.RECT_RIGHT: rl.Vector2(right, center_y),
            GizmoMode.RECT_TOP: rl.Vector2(center_x, top),
            GizmoMode.RECT_BOTTOM: rl.Vector2(center_x, bottom),
            GizmoMode.RECT_TOP_LEFT: rl.Vector2(left, top),
            GizmoMode.RECT_TOP_RIGHT: rl.Vector2(right, top),
            GizmoMode.RECT_BOTTOM_LEFT: rl.Vector2(left, bottom),
            GizmoMode.RECT_BOTTOM_RIGHT: rl.Vector2(right, bottom),
        }

    def _is_canvas_root(self, entity: Entity) -> bool:
        return entity.get_component(Canvas) is not None and not entity.parent_name
