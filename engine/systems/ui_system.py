"""
engine/systems/ui_system.py - Layout e interaccion UI overlay estilo Canvas.
"""

from __future__ import annotations

import copy
from typing import Any, Optional

import pyray as rl

from engine.components.canvas import Canvas
from engine.components.recttransform import RectTransform
from engine.components.uibutton import UIButton
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.editor.cursor_manager import CursorVisualState
from engine.events.event_bus import EventBus


class UISystem:
    """Calcula layout overlay free/stack y procesa interaccion declarativa."""

    def __init__(self) -> None:
        self._event_bus: Optional[EventBus] = None
        self._scene_loader: Any = None
        self._runtime_scene_loader: Any = None
        self._scene_flow_loader: Any = None
        self._scene_transition_runner: Any = None
        self._interaction_enabled_resolver: Any = None
        self._layout_cache: dict[str, dict[str, Any]] = {}
        self._canvas_order: list[str] = []
        self._draw_order: list[str] = []
        self._visible_button_entities: list[Entity] = []
        self._button_runtime: dict[int, dict[str, bool]] = {}
        self._pointer_override: Optional[dict[str, Any]] = None
        self._layout_world_id: int = -1
        self._layout_world_version: int = -1
        self._layout_viewport_size: tuple[float, float] = (0.0, 0.0)

    def set_event_bus(self, event_bus: Optional[EventBus]) -> None:
        self._event_bus = event_bus

    def set_scene_loader(self, callback: Any) -> None:
        self._scene_loader = callback

    def set_runtime_scene_loader(self, callback: Any) -> None:
        self._runtime_scene_loader = callback

    def set_scene_flow_loader(self, callback: Any) -> None:
        self._scene_flow_loader = callback

    def set_scene_transition_runner(self, callback: Any) -> None:
        self._scene_transition_runner = callback

    def set_interaction_enabled_resolver(self, callback: Any) -> None:
        self._interaction_enabled_resolver = callback

    def inject_pointer_state(
        self,
        x: float,
        y: float,
        down: bool,
        pressed: bool,
        released: bool,
        frames: int = 1,
    ) -> None:
        self._pointer_override = {
            "x": float(x),
            "y": float(y),
            "down": bool(down),
            "pressed": bool(pressed),
            "released": bool(released),
            "frames": max(1, int(frames)),
        }

    def get_layout_snapshot(self, copy_result: bool = True) -> dict[str, dict[str, Any]]:
        return copy.deepcopy(self._layout_cache) if copy_result else self._layout_cache

    def get_canvas_order(self) -> list[str]:
        return list(self._canvas_order)

    def get_draw_order(self) -> list[str]:
        return list(self._draw_order)

    def ensure_layout_cache(self, world: World, viewport_size: tuple[float, float]) -> None:
        self._ensure_layout_cache(world, viewport_size)

    def get_entity_screen_rect(self, entity_name: str) -> Optional[dict[str, float]]:
        layout = self._layout_cache.get(entity_name)
        if layout is None:
            return None
        return {
            "x": float(layout["x"]),
            "y": float(layout["y"]),
            "width": float(layout["width"]),
            "height": float(layout["height"]),
        }

    def get_layout_entry(self, entity_name: str, copy_result: bool = True) -> Optional[dict[str, Any]]:
        layout = self._layout_cache.get(entity_name)
        if layout is None:
            return None
        return copy.deepcopy(layout) if copy_result else layout

    def get_selected_canvas_root(self, world: World) -> Optional[Entity]:
        selected_name = getattr(world, "selected_entity_name", None)
        if not selected_name:
            return None
        entity = world.get_entity_by_name(selected_name)
        if entity is None or not entity.active or entity.parent_name is not None:
            return None
        canvas = entity.get_component(Canvas)
        if canvas is None or not canvas.enabled:
            return None
        return entity

    def should_render_scene_view_ui(self, world: World, *, allow_runtime: bool = False) -> bool:
        if allow_runtime:
            return True
        return self.get_selected_canvas_root(world) is not None

    def get_parent_layout_entry(self, world: World, entity_name: str, copy_result: bool = True) -> Optional[dict[str, Any]]:
        entity = world.get_entity_by_name(entity_name)
        if entity is None or not entity.parent_name:
            return None
        return self.get_layout_entry(entity.parent_name, copy_result=copy_result)

    def find_topmost_entity_at_point(
        self,
        world: World,
        x: float,
        y: float,
        viewport_size: tuple[float, float],
        *,
        include_canvas_roots: bool = False,
    ) -> Optional[Entity]:
        self._ensure_layout_cache(world, viewport_size)
        for entity_name in reversed(self._draw_order):
            entity = world.get_entity_by_name(entity_name)
            if entity is None:
                continue
            layout = self._layout_cache.get(entity_name)
            if layout is None or not self._point_in_rect(x, y, layout):
                continue
            has_rect_transform = entity.get_component(RectTransform) is not None
            if has_rect_transform:
                return entity
            if include_canvas_roots and entity.get_component(Canvas) is not None and not entity.parent_name:
                return entity
        return None

    def click_entity(self, world: World, entity_name: str, viewport_size: tuple[float, float]) -> bool:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        button = entity.get_component(UIButton)
        if button is None or not button.enabled or not button.interactable:
            return False
        self.update(world, viewport_size)
        return self._execute_button_action(entity, button)

    def update(
        self,
        world: World,
        viewport_size: tuple[float, float],
        *,
        allow_interaction: Optional[bool] = None,
    ) -> None:
        self._ensure_layout_cache(world, viewport_size)

        visible_buttons = {entity.id for entity in self._visible_button_entities}
        self._button_runtime = {
            entity_id: state
            for entity_id, state in self._button_runtime.items()
            if entity_id in visible_buttons
        }

        if not visible_buttons:
            return

        interaction_enabled = self._resolve_interaction_enabled(allow_interaction)
        if not interaction_enabled:
            for entity in self._visible_button_entities:
                button = entity.get_component(UIButton)
                layout = self._layout_cache.get(entity.name)
                if button is None or layout is None:
                    continue
                state = self._button_runtime.setdefault(entity.id, {"hovered": False, "pressed": False})
                state["hovered"] = False
                state["pressed"] = False
            return

        pointer = self._resolve_pointer_state()

        for entity in self._visible_button_entities:
            button = entity.get_component(UIButton)
            layout = self._layout_cache.get(entity.name)
            if button is None or layout is None:
                continue
            state = self._button_runtime.setdefault(entity.id, {"hovered": False, "pressed": False})
            hovered = button.enabled and button.interactable and self._point_in_rect(pointer["x"], pointer["y"], layout)
            state["hovered"] = hovered

            if not button.enabled or not button.interactable:
                state["pressed"] = False
                continue

            if pointer["pressed"] and hovered:
                state["pressed"] = True
            if pointer["released"]:
                should_fire = state["pressed"] and hovered
                state["pressed"] = False
                if should_fire:
                    self._execute_button_action(entity, button)

    def _ensure_layout_cache(self, world: World, viewport_size: tuple[float, float]) -> None:
        world_id = id(world)
        world_version = self._resolve_layout_version(world)
        normalized_viewport = (float(viewport_size[0]), float(viewport_size[1]))
        if (
            self._layout_world_id == world_id
            and self._layout_world_version == world_version
            and self._layout_viewport_size == normalized_viewport
        ):
            return

        self._layout_cache = {}
        self._canvas_order = []
        self._draw_order = []
        self._visible_button_entities = []

        canvas_entities = []
        for entity in world.get_entities_with(Canvas):
            canvas = entity.get_component(Canvas)
            if canvas is None or not canvas.enabled:
                continue
            canvas_entities.append(entity)

        canvas_entities.sort(key=lambda entity: (entity.get_component(Canvas).sort_order, entity.id))  # type: ignore[union-attr]

        for canvas_entity in canvas_entities:
            canvas = canvas_entity.get_component(Canvas)
            if canvas is None:
                continue
            canvas_rect = {
                "x": 0.0,
                "y": 0.0,
                "width": normalized_viewport[0],
                "height": normalized_viewport[1],
                "canvas": canvas_entity.name,
                "scale_x": normalized_viewport[0] / max(1.0, float(canvas.reference_width)),
                "scale_y": normalized_viewport[1] / max(1.0, float(canvas.reference_height)),
            }
            self._canvas_order.append(canvas_entity.name)
            self._layout_cache[canvas_entity.name] = dict(canvas_rect)
            self._draw_order.append(canvas_entity.name)
            self._layout_children(world, canvas_entity.name, canvas_rect)

        self._visible_button_entities = [
            entity
            for entity in world.get_entities_with(UIButton)
            if entity.name in self._layout_cache and entity.get_component(UIButton) is not None
        ]
        self._layout_world_id = world_id
        self._layout_world_version = world_version
        self._layout_viewport_size = normalized_viewport

    def _resolve_layout_version(self, world: World) -> int:
        try:
            return int(getattr(world, "ui_layout_version"))
        except (AttributeError, TypeError, ValueError):
            return int(getattr(world, "version", -1))

    def get_button_state(self, entity: Entity) -> dict[str, bool]:
        return dict(self._button_runtime.get(entity.id, {"hovered": False, "pressed": False}))

    def get_cursor_intent(
        self,
        world: World,
        viewport_size: tuple[float, float],
        x: float,
        y: float,
        *,
        allow_interaction: Optional[bool] = None,
    ) -> CursorVisualState:
        if not self._resolve_interaction_enabled(allow_interaction):
            return CursorVisualState.DEFAULT
        self._ensure_layout_cache(world, viewport_size)
        for entity in world.get_entities_with(UIButton):
            button = entity.get_component(UIButton)
            layout = self._layout_cache.get(entity.name)
            if button is None or layout is None:
                continue
            if not button.enabled or not button.interactable:
                continue
            if self._point_in_rect(float(x), float(y), layout):
                return CursorVisualState.INTERACTIVE
        return CursorVisualState.DEFAULT

    def _layout_children(self, world: World, parent_name: str, parent_rect: dict[str, Any]) -> None:
        children = world.get_children(parent_name)
        if not children:
            return

        parent_entity = world.get_entity_by_name(parent_name)
        parent_rect_transform = parent_entity.get_component(RectTransform) if parent_entity is not None else None
        layout_mode = self._resolve_layout_mode(parent_rect_transform)

        if layout_mode == "free":
            child_rects = {
                child.name: self._resolve_legacy_child_rect(child, parent_rect)
                for child in children
            }
        else:
            child_rects = self._resolve_stack_child_rects(
                children,
                parent_rect,
                parent_rect_transform,
                layout_mode=layout_mode,
            )

        for child in children:
            child_rect = child_rects.get(child.name, dict(parent_rect))
            child_rect["canvas"] = parent_rect["canvas"]
            self._layout_cache[child.name] = child_rect
            self._draw_order.append(child.name)
            self._layout_children(world, child.name, child_rect)

    def _resolve_stack_child_rects(
        self,
        children: list[Entity],
        parent_rect: dict[str, Any],
        parent_rect_transform: RectTransform | None,
        *,
        layout_mode: str,
    ) -> dict[str, dict[str, Any]]:
        resolved = {
            child.name: self._resolve_legacy_child_rect(child, parent_rect)
            for child in children
        }
        if parent_rect_transform is None:
            return resolved

        managed_children: list[tuple[int, int, Entity, RectTransform]] = []
        for index, child in enumerate(children):
            rect_transform = child.get_component(RectTransform)
            if rect_transform is None or not rect_transform.enabled or rect_transform.layout_ignore:
                continue
            managed_children.append((rect_transform.layout_order, index, child, rect_transform))

        if not managed_children:
            return resolved

        managed_children.sort(key=lambda item: (item[0], item[1]))

        content_rect = self._compute_content_rect(parent_rect, parent_rect_transform)
        align = self._resolve_layout_align(parent_rect_transform)
        horizontal = layout_mode == "horizontal_stack"
        spacing = max(
            0.0,
            float(parent_rect_transform.spacing)
            * float(parent_rect["scale_x"] if horizontal else parent_rect["scale_y"]),
        )

        preferred_sizes: dict[str, tuple[float, float]] = {}
        fixed_total = 0.0
        stretch_count = 0
        for _, _, child, rect_transform in managed_children:
            preferred_width, preferred_height = self._preferred_size(rect_transform, parent_rect)
            preferred_sizes[child.name] = (preferred_width, preferred_height)
            if self._is_main_axis_stretch(rect_transform, horizontal):
                stretch_count += 1
            else:
                fixed_total += preferred_width if horizontal else preferred_height

        spacing_total = spacing * max(0, len(managed_children) - 1)
        available_main = float(content_rect["width"] if horizontal else content_rect["height"])
        remaining_main = max(0.0, available_main - fixed_total - spacing_total)
        stretch_size = remaining_main / stretch_count if stretch_count else 0.0
        cursor = float(content_rect["x"] if horizontal else content_rect["y"])

        for _, _, child, rect_transform in managed_children:
            preferred_width, preferred_height = preferred_sizes[child.name]
            if horizontal:
                width = max(1.0, stretch_size) if self._is_main_axis_stretch(rect_transform, True) else preferred_width
                height, y = self._resolve_cross_axis(
                    rect_transform,
                    content_start=float(content_rect["y"]),
                    content_size=float(content_rect["height"]),
                    preferred_size=preferred_height,
                    align=align,
                    horizontal=True,
                )
                x = cursor
                cursor += width + spacing
            else:
                height = max(1.0, stretch_size) if self._is_main_axis_stretch(rect_transform, False) else preferred_height
                width, x = self._resolve_cross_axis(
                    rect_transform,
                    content_start=float(content_rect["x"]),
                    content_size=float(content_rect["width"]),
                    preferred_size=preferred_width,
                    align=align,
                    horizontal=False,
                )
                y = cursor
                cursor += height + spacing

            resolved[child.name] = {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "rotation": rect_transform.rotation,
                "scale_x": float(parent_rect.get("scale_x", 1.0)),
                "scale_y": float(parent_rect.get("scale_y", 1.0)),
            }
        return resolved

    def _resolve_legacy_child_rect(self, child: Entity, parent_rect: dict[str, Any]) -> dict[str, Any]:
        rect_transform = child.get_component(RectTransform)
        if rect_transform is None or not rect_transform.enabled:
            return dict(parent_rect)
        return self._compute_rect(rect_transform, parent_rect)

    def _compute_content_rect(
        self,
        parent_rect: dict[str, Any],
        parent_rect_transform: RectTransform,
    ) -> dict[str, float]:
        scale_x = float(parent_rect.get("scale_x", 1.0))
        scale_y = float(parent_rect.get("scale_y", 1.0))
        padding_left = max(0.0, float(parent_rect_transform.padding_left) * scale_x)
        padding_top = max(0.0, float(parent_rect_transform.padding_top) * scale_y)
        padding_right = max(0.0, float(parent_rect_transform.padding_right) * scale_x)
        padding_bottom = max(0.0, float(parent_rect_transform.padding_bottom) * scale_y)
        return {
            "x": float(parent_rect["x"]) + padding_left,
            "y": float(parent_rect["y"]) + padding_top,
            "width": max(0.0, float(parent_rect["width"]) - padding_left - padding_right),
            "height": max(0.0, float(parent_rect["height"]) - padding_top - padding_bottom),
        }

    def _preferred_size(
        self,
        rect_transform: RectTransform,
        parent_rect: dict[str, Any],
    ) -> tuple[float, float]:
        scale_x = float(parent_rect.get("scale_x", 1.0))
        scale_y = float(parent_rect.get("scale_y", 1.0))
        return (
            max(1.0, float(rect_transform.width) * scale_x * float(rect_transform.scale_x)),
            max(1.0, float(rect_transform.height) * scale_y * float(rect_transform.scale_y)),
        )

    def _resolve_cross_axis(
        self,
        rect_transform: RectTransform,
        *,
        content_start: float,
        content_size: float,
        preferred_size: float,
        align: str,
        horizontal: bool,
    ) -> tuple[float, float]:
        if self._is_cross_axis_stretch(rect_transform, horizontal) or align == "stretch":
            return max(1.0, content_size), content_start
        if align == "center":
            return preferred_size, content_start + (content_size - preferred_size) * 0.5
        if align == "end":
            return preferred_size, content_start + (content_size - preferred_size)
        return preferred_size, content_start

    def _is_main_axis_stretch(self, rect_transform: RectTransform, horizontal: bool) -> bool:
        return self._resolve_size_mode(rect_transform.size_mode_x if horizontal else rect_transform.size_mode_y) == "stretch"

    def _is_cross_axis_stretch(self, rect_transform: RectTransform, horizontal: bool) -> bool:
        return self._resolve_size_mode(rect_transform.size_mode_y if horizontal else rect_transform.size_mode_x) == "stretch"

    def _resolve_layout_mode(self, rect_transform: RectTransform | None) -> str:
        if rect_transform is None or not rect_transform.enabled:
            return "free"
        layout_mode = str(getattr(rect_transform, "layout_mode", "free") or "free").strip().lower()
        if layout_mode in {"vertical_stack", "horizontal_stack"}:
            return layout_mode
        return "free"

    def _resolve_size_mode(self, size_mode: Any) -> str:
        normalized = str(size_mode or "fixed").strip().lower()
        return normalized if normalized == "stretch" else "fixed"

    def _resolve_layout_align(self, rect_transform: RectTransform) -> str:
        normalized = str(getattr(rect_transform, "layout_align", "start") or "start").strip().lower()
        if normalized in {"center", "end", "stretch"}:
            return normalized
        return "start"

    def _compute_rect(self, rect_transform: RectTransform, parent_rect: dict[str, Any]) -> dict[str, Any]:
        anchor_min_x = max(0.0, min(1.0, rect_transform.anchor_min_x))
        anchor_min_y = max(0.0, min(1.0, rect_transform.anchor_min_y))
        anchor_max_x = max(anchor_min_x, min(1.0, rect_transform.anchor_max_x))
        anchor_max_y = max(anchor_min_y, min(1.0, rect_transform.anchor_max_y))
        scale_x = float(parent_rect.get("scale_x", 1.0))
        scale_y = float(parent_rect.get("scale_y", 1.0))

        anchor_left = parent_rect["x"] + parent_rect["width"] * anchor_min_x
        anchor_top = parent_rect["y"] + parent_rect["height"] * anchor_min_y
        anchor_width = parent_rect["width"] * (anchor_max_x - anchor_min_x)
        anchor_height = parent_rect["height"] * (anchor_max_y - anchor_min_y)

        width = max(1.0, (anchor_width + rect_transform.width * scale_x) * rect_transform.scale_x)
        height = max(1.0, (anchor_height + rect_transform.height * scale_y) * rect_transform.scale_y)

        pivot_x = max(0.0, min(1.0, rect_transform.pivot_x))
        pivot_y = max(0.0, min(1.0, rect_transform.pivot_y))
        pivot_pos_x = anchor_left + (anchor_width * pivot_x) + (rect_transform.anchored_x * scale_x)
        pivot_pos_y = anchor_top + (anchor_height * pivot_y) + (rect_transform.anchored_y * scale_y)

        return {
            "x": pivot_pos_x - (width * pivot_x),
            "y": pivot_pos_y - (height * pivot_y),
            "width": width,
            "height": height,
            "rotation": rect_transform.rotation,
            "scale_x": scale_x,
            "scale_y": scale_y,
        }

    def _resolve_pointer_state(self) -> dict[str, Any]:
        if self._pointer_override is None:
            mouse = rl.get_mouse_position()
            return {
                "x": float(mouse.x),
                "y": float(mouse.y),
                "down": bool(rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT)),
                "pressed": bool(rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)),
                "released": bool(rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT)),
            }

        payload = dict(self._pointer_override)
        frames = int(payload.get("frames", 1))
        if frames <= 1:
            self._pointer_override = None
        else:
            payload["frames"] = frames - 1
            self._pointer_override = payload
        return payload

    def _execute_button_action(self, entity: Entity, button: UIButton) -> bool:
        action = button.on_click if isinstance(button.on_click, dict) else {}
        action_type = str(action.get("type", "")).strip()
        if not action_type:
            return False
        if action_type == "load_scene_flow":
            target = str(action.get("target", "")).strip()
            if self._scene_flow_loader is None or not target:
                return False
            return bool(self._scene_flow_loader(target))
        if action_type == "load_scene":
            path = str(action.get("path", "")).strip()
            loader = self._runtime_scene_loader or self._scene_loader
            if loader is None or not path:
                return False
            return bool(loader(path))
        if action_type == "emit_event":
            event_name = str(action.get("name", "")).strip()
            if self._event_bus is None or not event_name:
                return False
            self._event_bus.emit(event_name, {"entity": entity.name, "source": "UIButton"})
            return True
        if action_type == "run_scene_transition":
            if self._scene_transition_runner is None:
                return False
            return bool(self._scene_transition_runner(entity.name))
        return False

    def _point_in_rect(self, x: float, y: float, rect: dict[str, Any]) -> bool:
        return (
            x >= float(rect["x"])
            and x <= float(rect["x"]) + float(rect["width"])
            and y >= float(rect["y"])
            and y <= float(rect["y"]) + float(rect["height"])
        )

    def _resolve_interaction_enabled(self, allow_interaction: Optional[bool]) -> bool:
        if allow_interaction is not None:
            return bool(allow_interaction)
        if self._interaction_enabled_resolver is None:
            return True
        try:
            return bool(self._interaction_enabled_resolver())
        except Exception:
            return False
