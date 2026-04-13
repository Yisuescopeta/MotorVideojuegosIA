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
from engine.editor.cursor_manager import CursorVisualState
from engine.events.event_bus import EventBus


class UISystem:
    """Calcula layout overlay y procesa interaccion declarativa de botones."""

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
        self._button_runtime: dict[int, dict[str, bool]] = {}
        self._pointer_override: Optional[dict[str, Any]] = None
        self._navigation_override: Optional[dict[str, Any]] = None
        self._focus_by_canvas: dict[str, str] = {}
        self._active_canvas_name: Optional[str] = None
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

    def inject_navigation_state(
        self,
        *,
        move_x: int = 0,
        move_y: int = 0,
        submit: bool = False,
        cancel: bool = False,
        frames: int = 1,
    ) -> None:
        self._navigation_override = {
            "move_x": max(-1, min(1, int(move_x))),
            "move_y": max(-1, min(1, int(move_y))),
            "submit": bool(submit),
            "cancel": bool(cancel),
            "frames": max(1, int(frames)),
        }

    def get_layout_snapshot(self, copy_result: bool = True) -> dict[str, dict[str, Any]]:
        return copy.deepcopy(self._layout_cache) if copy_result else self._layout_cache

    def get_canvas_order(self) -> list[str]:
        return list(self._canvas_order)

    def get_draw_order(self) -> list[str]:
        return list(self._draw_order)

    def get_focus_snapshot(self) -> dict[str, str]:
        return dict(self._focus_by_canvas)

    def get_active_canvas_name(self) -> Optional[str]:
        if self._active_canvas_name and self._active_canvas_name in self._canvas_order:
            return self._active_canvas_name
        return None

    def get_focused_entity_name(self, canvas_name: Optional[str] = None) -> Optional[str]:
        if canvas_name is not None:
            focused = self._focus_by_canvas.get(canvas_name)
            return focused if focused in self._layout_cache else None
        active_canvas = self.get_active_canvas_name()
        if active_canvas is not None:
            focused = self._focus_by_canvas.get(active_canvas)
            if focused in self._layout_cache:
                return focused
        for current_canvas in reversed(self._canvas_order):
            focused = self._focus_by_canvas.get(current_canvas)
            if focused in self._layout_cache:
                return focused
        return None

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
        self._focus_entity(world, entity)
        return self._execute_button_action(entity, button)

    def move_focus(self, world: World, viewport_size: tuple[float, float], direction: str) -> Optional[str]:
        self._ensure_layout_cache(world, viewport_size)
        focusables = self._collect_focusable_buttons(world)
        self._sync_focus_state(world, focusables)
        active_canvas = self._resolve_active_canvas(focusables)
        if active_canvas is None:
            return None
        move_x = 0
        move_y = 0
        normalized_direction = str(direction or "").strip().lower()
        if normalized_direction == "up":
            move_y = -1
        elif normalized_direction == "down":
            move_y = 1
        elif normalized_direction == "left":
            move_x = -1
        elif normalized_direction == "right":
            move_x = 1
        else:
            return None
        return self._move_focus_in_direction(world, active_canvas, focusables.get(active_canvas, []), move_x, move_y)

    def submit_focused(self, world: World, viewport_size: tuple[float, float]) -> bool:
        self._ensure_layout_cache(world, viewport_size)
        focusables = self._collect_focusable_buttons(world)
        self._sync_focus_state(world, focusables)
        active_canvas = self._resolve_active_canvas(focusables)
        if active_canvas is None:
            return False
        focused_name = self._focus_by_canvas.get(active_canvas, "")
        if not focused_name:
            return False
        entity = world.get_entity_by_name(focused_name)
        if entity is None:
            return False
        button = entity.get_component(UIButton)
        if button is None or not button.enabled or not button.interactable:
            return False
        self._active_canvas_name = active_canvas
        return self._execute_button_action(entity, button)

    def set_focus(
        self,
        world: World,
        viewport_size: tuple[float, float],
        entity_name: str,
        *,
        canvas_name: Optional[str] = None,
    ) -> Optional[str]:
        self._ensure_layout_cache(world, viewport_size)
        focusables = self._collect_focusable_buttons(world)
        self._sync_focus_state(world, focusables)
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return None
        layout = self._layout_cache.get(entity.name)
        if layout is None:
            return None
        resolved_canvas_name = str(layout.get("canvas", "") or "")
        if not resolved_canvas_name:
            return None
        if canvas_name is not None and resolved_canvas_name != str(canvas_name).strip():
            return None
        valid_targets = {candidate.name for candidate in focusables.get(resolved_canvas_name, [])}
        if entity.name not in valid_targets:
            return None
        self._focus_entity(world, entity)
        return entity.name

    def cancel_active_focus(self, world: World, viewport_size: tuple[float, float]) -> Optional[str]:
        self._ensure_layout_cache(world, viewport_size)
        focusables = self._collect_focusable_buttons(world)
        self._sync_focus_state(world, focusables)
        active_canvas = self._resolve_active_canvas(focusables)
        if active_canvas is None:
            return None
        return active_canvas if self._emit_cancel(active_canvas) else None

    def update(
        self,
        world: World,
        viewport_size: tuple[float, float],
        *,
        allow_interaction: Optional[bool] = None,
    ) -> None:
        self._ensure_layout_cache(world, viewport_size)

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

        focusables = self._collect_focusable_buttons(world)
        self._sync_focus_state(world, focusables)
        interaction_enabled = self._resolve_interaction_enabled(allow_interaction)
        if not interaction_enabled:
            for entity in world.get_entities_with(UIButton):
                button = entity.get_component(UIButton)
                layout = self._layout_cache.get(entity.name)
                if button is None or layout is None:
                    continue
                state = self._button_runtime.setdefault(entity.id, {"hovered": False, "pressed": False})
                state["hovered"] = False
                state["pressed"] = False
            return

        pointer = self._resolve_pointer_state()
        navigation = self._resolve_navigation_state()

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
                self._focus_entity(world, entity)
            if pointer["released"]:
                should_fire = state["pressed"] and hovered
                state["pressed"] = False
                if should_fire:
                    self._focus_entity(world, entity)
                    self._execute_button_action(entity, button)

        active_canvas = self._resolve_active_canvas(focusables)
        if active_canvas is not None:
            focusable_entities = focusables.get(active_canvas, [])
            if navigation["move_x"] or navigation["move_y"]:
                self._move_focus_in_direction(
                    world,
                    active_canvas,
                    focusable_entities,
                    int(navigation["move_x"]),
                    int(navigation["move_y"]),
                )
            if navigation["submit"]:
                self.submit_focused(world, viewport_size)
            if navigation["cancel"]:
                self._emit_cancel(active_canvas)

    def _ensure_layout_cache(self, world: World, viewport_size: tuple[float, float]) -> None:
        world_id = id(world)
        world_version = int(getattr(world, "version", -1))
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

        self._layout_world_id = world_id
        self._layout_world_version = world_version
        self._layout_viewport_size = normalized_viewport

    def get_button_state(self, entity: Entity) -> dict[str, bool]:
        state = dict(self._button_runtime.get(entity.id, {"hovered": False, "pressed": False}))
        state["focused"] = bool(self._is_entity_focused(entity))
        return state

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
        for child in world.get_children(parent_name):
            rect_transform = child.get_component(RectTransform)
            child_rect = dict(parent_rect)
            if rect_transform is not None and rect_transform.enabled:
                child_rect = self._compute_rect(rect_transform, parent_rect)
            child_rect["canvas"] = parent_rect["canvas"]
            self._layout_cache[child.name] = child_rect
            self._draw_order.append(child.name)
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

    def _resolve_navigation_state(self) -> dict[str, Any]:
        if self._navigation_override is not None:
            payload = dict(self._navigation_override)
            frames = int(payload.get("frames", 1))
            if frames <= 1:
                self._navigation_override = None
            else:
                payload["frames"] = frames - 1
                self._navigation_override = payload
            return payload

        move_x = 0
        move_y = 0
        if self._is_key_pressed((rl.KEY_UP, rl.KEY_W)):
            move_y = -1
        elif self._is_key_pressed((rl.KEY_DOWN, rl.KEY_S, rl.KEY_TAB)):
            move_y = 1
        elif self._is_key_pressed((rl.KEY_LEFT, rl.KEY_A)):
            move_x = -1
        elif self._is_key_pressed((rl.KEY_RIGHT, rl.KEY_D)):
            move_x = 1

        if rl.is_gamepad_available(0):
            if rl.is_gamepad_button_pressed(0, rl.GAMEPAD_BUTTON_LEFT_FACE_UP):
                move_y = -1
            elif rl.is_gamepad_button_pressed(0, rl.GAMEPAD_BUTTON_LEFT_FACE_DOWN):
                move_y = 1
            elif rl.is_gamepad_button_pressed(0, rl.GAMEPAD_BUTTON_LEFT_FACE_LEFT):
                move_x = -1
            elif rl.is_gamepad_button_pressed(0, rl.GAMEPAD_BUTTON_LEFT_FACE_RIGHT):
                move_x = 1

        submit = self._is_key_pressed((rl.KEY_ENTER, rl.KEY_SPACE))
        cancel = self._is_key_pressed((rl.KEY_ESCAPE, rl.KEY_BACKSPACE))
        if rl.is_gamepad_available(0):
            submit = submit or rl.is_gamepad_button_pressed(0, rl.GAMEPAD_BUTTON_RIGHT_FACE_DOWN)
            cancel = cancel or rl.is_gamepad_button_pressed(0, rl.GAMEPAD_BUTTON_RIGHT_FACE_RIGHT)

        return {
            "move_x": move_x,
            "move_y": move_y,
            "submit": submit,
            "cancel": cancel,
        }

    def _is_key_pressed(self, keys: tuple[int, ...]) -> bool:
        return any(bool(rl.is_key_pressed(key)) for key in keys)

    def _collect_focusable_buttons(self, world: World) -> dict[str, list[Entity]]:
        focusables: dict[str, list[Entity]] = {}
        for entity_name in self._draw_order:
            entity = world.get_entity_by_name(entity_name)
            if entity is None:
                continue
            button = entity.get_component(UIButton)
            layout = self._layout_cache.get(entity.name)
            if button is None or layout is None:
                continue
            if not button.enabled or not button.interactable or not getattr(button, "focusable", True):
                continue
            canvas_name = str(layout.get("canvas", ""))
            if not canvas_name:
                continue
            focusables.setdefault(canvas_name, []).append(entity)
        return focusables

    def _sync_focus_state(self, world: World, focusables: dict[str, list[Entity]]) -> None:
        valid_names = {
            canvas_name: {entity.name for entity in entities}
            for canvas_name, entities in focusables.items()
        }
        self._focus_by_canvas = {
            canvas_name: entity_name
            for canvas_name, entity_name in self._focus_by_canvas.items()
            if entity_name in valid_names.get(canvas_name, set())
        }
        valid_canvases = {canvas_name for canvas_name, entities in focusables.items() if entities}
        if self._active_canvas_name not in valid_canvases:
            self._active_canvas_name = None
        for canvas_name, entities in focusables.items():
            if canvas_name in self._focus_by_canvas or not entities:
                continue
            canvas_entity = world.get_entity_by_name(canvas_name)
            canvas = canvas_entity.get_component(Canvas) if canvas_entity is not None else None
            initial_focus = str(getattr(canvas, "initial_focus_entity_id", "") or "").strip()
            if initial_focus and initial_focus in valid_names.get(canvas_name, set()):
                self._focus_by_canvas[canvas_name] = initial_focus
            else:
                self._focus_by_canvas[canvas_name] = entities[0].name
        if self._active_canvas_name is None:
            self._active_canvas_name = self._pick_topmost_focusable_canvas(focusables)

    def _resolve_active_canvas(self, focusables: dict[str, list[Entity]]) -> Optional[str]:
        if self._active_canvas_name and focusables.get(self._active_canvas_name):
            return self._active_canvas_name
        self._active_canvas_name = self._pick_topmost_focusable_canvas(focusables)
        for canvas_name in reversed(self._canvas_order):
            if focusables.get(canvas_name):
                return canvas_name
        return None

    def _focus_entity(self, world: World, entity: Entity) -> None:
        layout = self._layout_cache.get(entity.name)
        if layout is None:
            return
        canvas_name = str(layout.get("canvas", "") or "")
        if not canvas_name:
            return
        button = entity.get_component(UIButton)
        if button is None or not button.enabled or not button.interactable or not getattr(button, "focusable", True):
            return
        self._focus_by_canvas[canvas_name] = entity.name
        self._active_canvas_name = canvas_name

    def _is_entity_focused(self, entity: Entity) -> bool:
        layout = self._layout_cache.get(entity.name)
        if layout is None:
            return False
        canvas_name = str(layout.get("canvas", "") or "")
        return bool(canvas_name) and self._focus_by_canvas.get(canvas_name) == entity.name

    def _move_focus_in_direction(
        self,
        world: World,
        canvas_name: str,
        focusable_entities: list[Entity],
        move_x: int,
        move_y: int,
    ) -> Optional[str]:
        if not focusable_entities:
            return None
        self._active_canvas_name = canvas_name
        current_name = self._focus_by_canvas.get(canvas_name)
        if not current_name:
            current_name = focusable_entities[0].name
            self._focus_by_canvas[canvas_name] = current_name
            return current_name
        current_entity = world.get_entity_by_name(current_name)
        if current_entity is None:
            fallback = focusable_entities[0].name
            self._focus_by_canvas[canvas_name] = fallback
            return fallback

        explicit_target = self._resolve_explicit_navigation(current_entity, move_x, move_y)
        valid_targets = {entity.name for entity in focusable_entities}
        if explicit_target and explicit_target in valid_targets:
            self._focus_by_canvas[canvas_name] = explicit_target
            return explicit_target

        current_layout = self._layout_cache.get(current_name)
        if current_layout is None:
            return current_name
        current_center_x = float(current_layout["x"]) + (float(current_layout["width"]) * 0.5)
        current_center_y = float(current_layout["y"]) + (float(current_layout["height"]) * 0.5)

        best_target: Optional[str] = None
        best_score: tuple[float, float, str] | None = None
        for candidate in focusable_entities:
            if candidate.name == current_name:
                continue
            candidate_layout = self._layout_cache.get(candidate.name)
            if candidate_layout is None:
                continue
            candidate_center_x = float(candidate_layout["x"]) + (float(candidate_layout["width"]) * 0.5)
            candidate_center_y = float(candidate_layout["y"]) + (float(candidate_layout["height"]) * 0.5)
            delta_x = candidate_center_x - current_center_x
            delta_y = candidate_center_y - current_center_y

            if move_y < 0 and delta_y >= -1e-6:
                continue
            if move_y > 0 and delta_y <= 1e-6:
                continue
            if move_x < 0 and delta_x >= -1e-6:
                continue
            if move_x > 0 and delta_x <= 1e-6:
                continue

            primary_distance = abs(delta_y) if move_y else abs(delta_x)
            secondary_distance = abs(delta_x) if move_y else abs(delta_y)
            score = (primary_distance, secondary_distance, candidate.name)
            if best_score is None or score < best_score:
                best_score = score
                best_target = candidate.name

        if best_target is None:
            return current_name
        self._focus_by_canvas[canvas_name] = best_target
        return best_target

    def _pick_topmost_focusable_canvas(self, focusables: dict[str, list[Entity]]) -> Optional[str]:
        for canvas_name in reversed(self._canvas_order):
            if focusables.get(canvas_name):
                return canvas_name
        return None

    def _resolve_explicit_navigation(self, entity: Entity, move_x: int, move_y: int) -> str:
        button = entity.get_component(UIButton)
        if button is None:
            return ""
        if move_y < 0:
            return str(getattr(button, "nav_up", "") or "").strip()
        if move_y > 0:
            return str(getattr(button, "nav_down", "") or "").strip()
        if move_x < 0:
            return str(getattr(button, "nav_left", "") or "").strip()
        if move_x > 0:
            return str(getattr(button, "nav_right", "") or "").strip()
        return ""

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

    def _emit_cancel(self, active_canvas: str) -> bool:
        if self._event_bus is None or not active_canvas:
            return False
        self._event_bus.emit("ui.cancel", {"canvas": active_canvas, "source": "UISystem"})
        return True

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
