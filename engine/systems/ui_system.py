"""
engine/systems/ui_system.py - Layout e interaccion UI overlay estilo Canvas.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Optional

import pyray as rl

from engine.components.canvas import Canvas
from engine.components.recttransform import RectTransform
from engine.components.uibutton import UIButton
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.events.event_bus import EventBus


class UISystem:
    """Calcula layout overlay y procesa interaccion declarativa de botones."""

    def __init__(self) -> None:
        self._event_bus: Optional[EventBus] = None
        self._scene_loader: Any = None
        self._scene_flow_loader: Any = None
        self._layout_cache: dict[str, dict[str, Any]] = {}
        self._canvas_order: list[str] = []
        self._button_runtime: dict[int, dict[str, bool]] = {}
        self._pointer_override: Optional[dict[str, Any]] = None

    def set_event_bus(self, event_bus: Optional[EventBus]) -> None:
        self._event_bus = event_bus

    def set_scene_loader(self, callback: Any) -> None:
        self._scene_loader = callback

    def set_scene_flow_loader(self, callback: Any) -> None:
        self._scene_flow_loader = callback

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

    def get_layout_snapshot(self) -> dict[str, dict[str, Any]]:
        return copy.deepcopy(self._layout_cache)

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

    def click_entity(self, world: World, entity_name: str, viewport_size: tuple[float, float]) -> bool:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        button = entity.get_component(UIButton)
        if button is None or not button.enabled or not button.interactable:
            return False
        self.update(world, viewport_size)
        return self._execute_button_action(entity, button)

    def update(self, world: World, viewport_size: tuple[float, float]) -> None:
        pointer = self._resolve_pointer_state()
        self._layout_cache = {}
        self._canvas_order = []

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
                "width": float(viewport_size[0]),
                "height": float(viewport_size[1]),
                "canvas": canvas_entity.name,
                "scale_x": float(viewport_size[0]) / max(1.0, float(canvas.reference_width)),
                "scale_y": float(viewport_size[1]) / max(1.0, float(canvas.reference_height)),
            }
            self._canvas_order.append(canvas_entity.name)
            self._layout_cache[canvas_entity.name] = dict(canvas_rect)
            self._layout_children(world, canvas_entity.name, canvas_rect)

        visible_buttons = {
            entity.id
            for entity in world.get_entities_with(UIButton)
            if entity.name in self._layout_cache and entity.get_component(UIButton) is not None
        }
        self._button_runtime = {
            entity_id: state
            for entity_id, state in self._button_runtime.items()
            if entity_id in visible_buttons
        }

        if not visible_buttons:
            return

        for entity in world.get_entities_with(UIButton):
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

    def get_button_state(self, entity: Entity) -> dict[str, bool]:
        return dict(self._button_runtime.get(entity.id, {"hovered": False, "pressed": False}))

    def _layout_children(self, world: World, parent_name: str, parent_rect: dict[str, Any]) -> None:
        for child in world.get_children(parent_name):
            rect_transform = child.get_component(RectTransform)
            child_rect = dict(parent_rect)
            if rect_transform is not None and rect_transform.enabled:
                child_rect = self._compute_rect(rect_transform, parent_rect)
            child_rect["canvas"] = parent_rect["canvas"]
            self._layout_cache[child.name] = child_rect
            self._layout_children(world, child.name, child_rect)

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
            if self._scene_loader is None or not path:
                return False
            return bool(self._scene_loader(path))
        if action_type == "emit_event":
            event_name = str(action.get("name", "")).strip()
            if self._event_bus is None or not event_name:
                return False
            self._event_bus.emit(event_name, {"entity": entity.name, "source": "UIButton"})
            return True
        return False

    def _point_in_rect(self, x: float, y: float, rect: dict[str, Any]) -> bool:
        return (
            x >= float(rect["x"])
            and x <= float(rect["x"]) + float(rect["width"])
            and y >= float(rect["y"])
            and y <= float(rect["y"]) + float(rect["height"])
        )
