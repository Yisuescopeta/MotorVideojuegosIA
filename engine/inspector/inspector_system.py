"""
engine/inspector/inspector_system.py - Dedicated inspector editors.
"""

from __future__ import annotations

import copy
import math
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pyray as rl
from engine.assets.asset_reference import clone_asset_reference, normalize_asset_reference
from engine.assets.asset_service import AssetService
from engine.components.collider import Collider
from engine.components.playercontroller2d import PlayerController2D
from engine.components.scene_transition_on_contact import SceneTransitionOnContact
from engine.components.scene_transition_on_interact import SceneTransitionOnInteract
from engine.components.scene_transition_on_player_death import SceneTransitionOnPlayerDeath
from engine.components.uibutton import UIButton
from engine.ecs.component import Component
from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.editor.cursor_manager import CursorVisualState
from engine.editor.render_safety import editor_scissor
from engine.inspector.component_editor_registry import ComponentEditorRegistry
from engine.levels.component_registry import create_default_registry
from engine.project.project_service import ProjectService
from engine.resources.texture_manager import TextureManager
from engine.scenes.scene_transition_support import list_scene_entry_points, validate_scene_transition_references

PayloadUpdater = Callable[..., Any]
CommitCallback = Callable[..., Any]


@dataclass
class TilemapAuthoringState:
    enabled: bool = False
    entity_name: str = ""
    layer_name: str = ""
    tile_id: str = ""
    source: dict[str, str] = field(default_factory=dict)
    mode: str = "paint"
    shortcut_mode: str = ""
    hover_cell: tuple[int, int] | None = None
    palette_scroll: float = 0.0
    palette_focused: bool = False
    palette_selected_index: int = 0
    stroke_active: bool = False
    stroke_cells: set[tuple[int, int]] = field(default_factory=set)
    box_fill_anchor: tuple[int, int] | None = None
    stamp_tiles: list[dict[str, Any]] = field(default_factory=list)
    flood_bounds_mode: str = "auto"
    flood_margin: int = 8
    flood_max_cells: int = 4096
    flood_min_x: int = -8
    flood_min_y: int = -8
    flood_max_x: int = 7
    flood_max_y: int = 7
    flood_effective_bounds: tuple[int, int, int, int] | None = None
    flood_preview_count: int = 0
    flood_truncated: bool = False


class InspectorSystem:
    """Unity-like inspector with dedicated editors for built-in components."""

    SCENE_TRANSITION_TRIGGER_OPTIONS: list[tuple[str, str]] = [
        ("none", "None"),
        ("ui_button", "UI Button"),
        ("interact_near", "Interact Near"),
        ("trigger_enter", "Trigger Enter"),
        ("collision", "Collision"),
        ("player_death", "Player Death"),
    ]
    SCENE_TRANSITION_HIDDEN_COMPONENTS: Set[str] = {
        "SceneTransitionAction",
        "SceneTransitionOnContact",
        "SceneTransitionOnInteract",
        "SceneTransitionOnPlayerDeath",
    }
    SCENE_TRANSITION_ADD_MENU_HIDDEN_COMPONENTS: Set[str] = {
        "SceneTransitionAction",
        "SceneTransitionOnContact",
        "SceneTransitionOnInteract",
        "SceneTransitionOnPlayerDeath",
    }

    BG_COLOR = rl.Color(30, 30, 30, 255)
    HEADER_COLOR = rl.Color(50, 50, 50, 255)
    FIELD_BG_COLOR = rl.Color(20, 20, 20, 255)
    TEXT_COLOR = rl.Color(220, 220, 220, 255)
    LABEL_COLOR = rl.Color(180, 180, 180, 255)
    HIGHLIGHT_COLOR = rl.Color(60, 100, 150, 255)
    ORIGIN_NATIVE_COLOR = rl.Color(79, 152, 209, 255)
    ORIGIN_AI_COLOR = rl.Color(206, 142, 58, 255)
    ORIGIN_UNKNOWN_COLOR = rl.Color(110, 110, 110, 255)

    FONT_SIZE: int = 10
    LINE_HEIGHT: int = 18
    MARGIN: int = 4
    LABEL_WIDTH: int = 80

    def __init__(self) -> None:
        self.expanded_components: Set[str] = set()
        self._scene_manager: Any = None

        self.editing_text_field: Optional[str] = None
        self.editing_value_type: str = "float"
        self._editing_commit: Optional[CommitCallback] = None
        self.text_buffer: bytearray = bytearray(128)

        self.show_add_menu: bool = False
        self.registry = create_default_registry()
        self.component_editors = ComponentEditorRegistry()
        self.request_open_sprite_editor_for: Optional[str] = None
        self._scene_path_cache: List[str] = []
        self._scene_path_cache_root: str = ""
        self._scene_path_cache_time: float = 0.0
        self._scene_entry_point_cache: List[Dict[str, str]] = []
        self._scene_entry_point_cache_key: tuple[str, str] = ("", "")
        self._scene_entry_point_cache_time: float = 0.0
        self._cursor_interactive_rects: List[rl.Rectangle] = []
        self._cursor_text_rects: List[rl.Rectangle] = []
        self._tilemap_authoring = TilemapAuthoringState()
        self._tilemap_project_service: Optional[ProjectService] = None
        self._tilemap_asset_service: Optional[AssetService] = None
        self._tilemap_asset_service_root: str = ""
        self._tilemap_texture_manager = TextureManager()
        self._register_default_component_editors()

    def set_scene_manager(self, manager: Any) -> None:
        self._scene_manager = manager
        self._scene_path_cache = []
        self._scene_path_cache_root = ""
        self._scene_path_cache_time = 0.0
        self._tilemap_project_service = None
        self._tilemap_asset_service = None
        self._tilemap_asset_service_root = ""

    def open_sprite_editor(self, asset_path: str) -> None:
        self.request_open_sprite_editor_for = asset_path

    def get_tilemap_tool_state(self) -> Dict[str, Any]:
        return {
            "enabled": bool(self._tilemap_authoring.enabled),
            "entity_name": str(self._tilemap_authoring.entity_name or ""),
            "layer_name": str(self._tilemap_authoring.layer_name or ""),
            "tile_id": str(self._tilemap_authoring.tile_id or ""),
            "source": clone_asset_reference(self._tilemap_authoring.source),
            "mode": str(self._tilemap_authoring.mode or "paint"),
            "effective_mode": self._tilemap_effective_mode(),
            "shortcut_mode": str(self._tilemap_authoring.shortcut_mode or ""),
            "hover_cell": tuple(self._tilemap_authoring.hover_cell) if self._tilemap_authoring.hover_cell is not None else None,
            "palette_scroll": float(self._tilemap_authoring.palette_scroll),
            "palette_focused": bool(self._tilemap_authoring.palette_focused),
            "palette_selected_index": int(self._tilemap_authoring.palette_selected_index),
            "stroke_active": bool(self._tilemap_authoring.stroke_active),
            "stroke_cells": sorted(self._tilemap_authoring.stroke_cells),
            "box_fill_anchor": tuple(self._tilemap_authoring.box_fill_anchor) if self._tilemap_authoring.box_fill_anchor is not None else None,
            "stamp_tiles": copy.deepcopy(self._tilemap_authoring.stamp_tiles),
            "flood_bounds_mode": str(self._tilemap_authoring.flood_bounds_mode or "auto"),
            "flood_margin": int(self._tilemap_authoring.flood_margin),
            "flood_max_cells": int(self._tilemap_authoring.flood_max_cells),
            "flood_manual_bounds": (
                int(self._tilemap_authoring.flood_min_x),
                int(self._tilemap_authoring.flood_min_y),
                int(self._tilemap_authoring.flood_max_x),
                int(self._tilemap_authoring.flood_max_y),
            ),
            "flood_effective_bounds": tuple(self._tilemap_authoring.flood_effective_bounds) if self._tilemap_authoring.flood_effective_bounds is not None else None,
            "flood_preview_count": int(self._tilemap_authoring.flood_preview_count),
            "flood_truncated": bool(self._tilemap_authoring.flood_truncated),
        }

    def get_tilemap_preview_snapshot(self, world: "World") -> Optional[Dict[str, Any]]:
        entity_name = self._resolve_tilemap_tool_entity_name(world)
        if entity_name is None or self._tilemap_authoring.hover_cell is None:
            return None
        return self._build_tilemap_preview_snapshot(world, entity_name, self._tilemap_authoring.hover_cell)

    def activate_tilemap_tool(
        self,
        world: "World",
        entity_name: Optional[str] = None,
        *,
        layer_name: Optional[str] = None,
    ) -> bool:
        target_name = str(entity_name or world.selected_entity_name or "").strip()
        if not target_name or not self._entity_has_component(world, target_name, "Tilemap"):
            return False
        previous_entity = self._tilemap_authoring.entity_name
        previous_layer = self._tilemap_authoring.layer_name
        self._tilemap_authoring.enabled = True
        self._tilemap_authoring.entity_name = target_name
        self._tilemap_authoring.palette_focused = True
        payload = self._current_component_payload(world, target_name, "Tilemap") or {}
        preferred_layer = layer_name
        if preferred_layer is None and self._tilemap_authoring.entity_name == target_name:
            preferred_layer = self._tilemap_authoring.layer_name
        self._tilemap_authoring.layer_name = self._resolve_tilemap_layer_name(payload, preferred_layer)
        if previous_entity != target_name or previous_layer != self._tilemap_authoring.layer_name:
            self._tilemap_authoring.palette_scroll = 0.0
            self._tilemap_authoring.palette_selected_index = 0
            self._tilemap_authoring.tile_id = ""
            self._tilemap_authoring.source = {}
        self._synchronize_tilemap_tool_selection(world, target_name)
        return True

    def deactivate_tilemap_tool(self) -> None:
        if self._tilemap_authoring.stroke_active:
            self._finish_tilemap_stroke(commit=False)
        self._tilemap_authoring = TilemapAuthoringState()

    def is_tilemap_tool_active(self, world: "World") -> bool:
        if not self._tilemap_authoring.enabled:
            return False
        entity_name = self._resolve_tilemap_tool_entity_name(world)
        return bool(entity_name)

    def set_tilemap_tool_mode(self, mode: str) -> bool:
        normalized_mode = self._normalize_tilemap_tool_mode(mode)
        self._tilemap_authoring.mode = normalized_mode
        self._tilemap_authoring.shortcut_mode = ""
        if normalized_mode != "box_fill":
            self._tilemap_authoring.box_fill_anchor = None
        if normalized_mode != "flood_fill":
            self._tilemap_authoring.flood_effective_bounds = None
            self._tilemap_authoring.flood_preview_count = 0
            self._tilemap_authoring.flood_truncated = False
        return True

    def set_tilemap_active_layer(self, world: "World", entity_name: str, layer_name: str) -> bool:
        if not self.activate_tilemap_tool(world, entity_name, layer_name=layer_name):
            return False
        self._tilemap_authoring.layer_name = str(layer_name or "").strip()
        self._tilemap_authoring.palette_scroll = 0.0
        self._synchronize_tilemap_tool_selection(world, entity_name)
        return True

    def set_tilemap_selected_tile(
        self,
        world: "World",
        entity_name: str,
        tile_id: str,
        *,
        source: Any = None,
    ) -> bool:
        normalized_entity_name = str(entity_name or "").strip()
        if not normalized_entity_name:
            return False
        if not (self._tilemap_authoring.enabled and self._tilemap_authoring.entity_name == normalized_entity_name):
            if not self.activate_tilemap_tool(world, normalized_entity_name):
                return False
        self._tilemap_authoring.tile_id = str(tile_id or "").strip()
        if source is not None:
            self._tilemap_authoring.source = normalize_asset_reference(source)
        else:
            payload = self._current_component_payload(world, normalized_entity_name, "Tilemap") or {}
            self._tilemap_authoring.source = self._resolve_tilemap_palette_source(payload, self._tilemap_authoring.layer_name)
        entries = self.list_tilemap_palette_entries(world, normalized_entity_name, self._tilemap_authoring.layer_name)
        self._sync_tilemap_palette_index_to_tile(entries)
        return True

    def set_tilemap_palette_selection(self, world: "World", entity_name: str, index: int) -> bool:
        entries = self.list_tilemap_palette_entries(world, entity_name, self._tilemap_authoring.layer_name)
        if not entries:
            return False
        clamped_index = max(0, min(len(entries) - 1, int(index)))
        self._tilemap_authoring.palette_selected_index = clamped_index
        entry = entries[clamped_index]
        return self.set_tilemap_selected_tile(world, entity_name, str(entry.get("tile_id", "")), source=entry.get("source"))

    def set_tilemap_flood_bounds(
        self,
        *,
        mode: str | None = None,
        margin: int | None = None,
        max_cells: int | None = None,
        min_x: int | None = None,
        min_y: int | None = None,
        max_x: int | None = None,
        max_y: int | None = None,
    ) -> bool:
        """Configures editor-only flood fill limits without changing scene data."""
        if mode is not None:
            normalized_mode = str(mode or "").strip().lower()
            if normalized_mode not in {"auto", "manual"}:
                return False
            self._tilemap_authoring.flood_bounds_mode = normalized_mode
        if margin is not None:
            self._tilemap_authoring.flood_margin = max(0, int(margin))
        if max_cells is not None:
            self._tilemap_authoring.flood_max_cells = max(1, min(4096, int(max_cells)))
        if min_x is not None:
            self._tilemap_authoring.flood_min_x = int(min_x)
        if min_y is not None:
            self._tilemap_authoring.flood_min_y = int(min_y)
        if max_x is not None:
            self._tilemap_authoring.flood_max_x = int(max_x)
        if max_y is not None:
            self._tilemap_authoring.flood_max_y = int(max_y)
        if self._tilemap_authoring.flood_min_x > self._tilemap_authoring.flood_max_x:
            self._tilemap_authoring.flood_min_x, self._tilemap_authoring.flood_max_x = (
                self._tilemap_authoring.flood_max_x,
                self._tilemap_authoring.flood_min_x,
            )
        if self._tilemap_authoring.flood_min_y > self._tilemap_authoring.flood_max_y:
            self._tilemap_authoring.flood_min_y, self._tilemap_authoring.flood_max_y = (
                self._tilemap_authoring.flood_max_y,
                self._tilemap_authoring.flood_min_y,
            )
        return True

    def list_tilemap_palette_options(
        self,
        world: "World",
        entity_name: str,
        layer_name: Optional[str] = None,
    ) -> List[tuple[str, str]]:
        return [
            (str(entry.get("tile_id", "")), str(entry.get("label", "")))
            for entry in self.list_tilemap_palette_entries(world, entity_name, layer_name)
        ]

    def list_tilemap_palette_entries(
        self,
        world: "World",
        entity_name: str,
        layer_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        payload = self._current_component_payload(world, entity_name, "Tilemap")
        if payload is None:
            return []
        active_layer = self._resolve_tilemap_layer_name(payload, layer_name)
        asset_ref = self._resolve_tilemap_palette_source(payload, active_layer)
        entries = self._build_tilemap_palette_entries(payload, asset_ref)
        for entry in entries:
            entry["layer_name"] = active_layer
        return entries

    def tilemap_world_to_cell(
        self,
        world: "World",
        entity_name: str,
        world_x: float,
        world_y: float,
    ) -> Optional[tuple[int, int]]:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return None
        transform = self._find_component(entity, "Transform")
        tilemap = self._find_component(entity, "Tilemap")
        if transform is None or tilemap is None or not getattr(tilemap, "enabled", True):
            return None
        payload = self._current_component_payload(world, entity_name, "Tilemap") or {}
        layer = self._find_tilemap_layer_payload(payload, self._tilemap_authoring.layer_name)
        layer_offset_x = float((layer or {}).get("offset_x", 0.0))
        layer_offset_y = float((layer or {}).get("offset_y", 0.0))
        cell_width = max(1, int(getattr(tilemap, "cell_width", 1)))
        cell_height = max(1, int(getattr(tilemap, "cell_height", 1)))
        local_point = self._tilemap_world_to_local_point(transform, float(world_x), float(world_y))
        if local_point is None:
            return None
        local_x = local_point[0] - layer_offset_x
        local_y = local_point[1] - layer_offset_y
        return (int(math.floor(local_x / cell_width)), int(math.floor(local_y / cell_height)))

    def handle_tilemap_scene_input(self, world: "World", mouse_world: rl.Vector2, mouse_in_scene: bool) -> bool:
        entity_name = self._resolve_tilemap_tool_entity_name(world)
        if entity_name is None:
            self._tilemap_authoring.hover_cell = None
            if self._tilemap_authoring.stroke_active:
                self._finish_tilemap_stroke(commit=False)
            return False

        payload = self._current_component_payload(world, entity_name, "Tilemap") or {}
        self._tilemap_authoring.layer_name = self._resolve_tilemap_layer_name(payload, self._tilemap_authoring.layer_name)
        self._synchronize_tilemap_tool_selection(world, entity_name)

        hover_cell = None
        if mouse_in_scene:
            hover_cell = self.tilemap_world_to_cell(world, entity_name, float(mouse_world.x), float(mouse_world.y))
        self._tilemap_authoring.hover_cell = hover_cell

        left_pressed = rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT)
        left_down = rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT)
        left_released = rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT)
        effective_mode = self._tilemap_effective_mode()

        if mouse_in_scene and hover_cell is not None and effective_mode == "pick" and left_pressed:
            self._tilemap_authoring.box_fill_anchor = hover_cell
            return True
        if mouse_in_scene and hover_cell is not None and effective_mode == "pick" and left_released:
            anchor = self._tilemap_authoring.box_fill_anchor or hover_cell
            if anchor != hover_cell:
                if not self._set_tilemap_stamp_from_scene(world, entity_name, anchor, hover_cell):
                    self._tilemap_authoring.mode = "paint"
            else:
                self._pick_tilemap_tile(world, entity_name, hover_cell)
                self._tilemap_authoring.mode = "paint"
            self._tilemap_authoring.box_fill_anchor = None
            return True

        if mouse_in_scene and hover_cell is not None and left_pressed:
            if effective_mode == "flood_fill":
                if self._begin_tilemap_stroke(label="Tilemap Flood Fill"):
                    self._apply_tilemap_flood_fill(world, entity_name, hover_cell)
                    self._finish_tilemap_stroke(commit=True)
                return True
            if effective_mode == "box_fill":
                self._tilemap_authoring.box_fill_anchor = hover_cell
                if not self._begin_tilemap_stroke(label="Tilemap Box Fill"):
                    return True
                return True
            if not self._begin_tilemap_stroke():
                return True
            self._apply_tilemap_brush(world, entity_name, hover_cell)
        elif self._tilemap_authoring.stroke_active and mouse_in_scene and hover_cell is not None and left_down and effective_mode in {"paint", "erase", "stamp"}:
            self._apply_tilemap_brush(world, entity_name, hover_cell)

        if self._tilemap_authoring.stroke_active and (left_released or not left_down):
            if effective_mode == "box_fill" and hover_cell is not None:
                self._apply_tilemap_box_fill(world, entity_name, hover_cell)
            self._finish_tilemap_stroke(commit=True)
            self._tilemap_authoring.box_fill_anchor = None

        return bool(self._tilemap_authoring.enabled)

    def has_dedicated_editor(self, component_name: str) -> bool:
        return self.component_editors.has(component_name)

    def list_dedicated_editors(self) -> list[str]:
        return self.component_editors.list_registered()

    def _component_expansion_key(self, entity_name: str, component_name: str) -> str:
        """Returns the stable UI key used to remember component fold state."""
        return f"{entity_name}:{component_name}"

    def replace_component_payload(
        self,
        world: "World",
        entity_name: str,
        component_name: str,
        component_data: Dict[str, Any],
    ) -> bool:
        payload = copy.deepcopy(component_data)
        if self._scene_manager is not None:
            return self._scene_manager.replace_component_data(entity_name, component_name, payload)

        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False

        rebuilt = self.registry.create(component_name, payload)
        if rebuilt is not None:
            entity.add_component(rebuilt)
            return True

        component = self._find_component(entity, component_name)
        if component is None:
            return False
        for key, value in payload.items():
            setattr(component, key, copy.deepcopy(value))
        return True

    def update_component_payload(
        self,
        world: "World",
        entity_name: str,
        component_name: str,
        updater: PayloadUpdater,
    ) -> bool:
        payload = self._current_component_payload(world, entity_name, component_name)
        if payload is None:
            return False
        updater(payload)
        return self.replace_component_payload(world, entity_name, component_name, payload)

    def _register_default_component_editors(self) -> None:
        self.component_editors.register("Transform", self._draw_transform_editor)
        self.component_editors.register("Sprite", self._draw_sprite_editor)
        self.component_editors.register("Collider", self._draw_collider_editor)
        self.component_editors.register("RigidBody", self._draw_rigidbody_editor)
        self.component_editors.register("Animator", self._draw_animator_editor)
        self.component_editors.register("Camera2D", self._draw_camera2d_editor)
        self.component_editors.register("AudioSource", self._draw_audio_source_editor)
        self.component_editors.register("InputMap", self._draw_input_map_editor)
        self.component_editors.register("PlayerController2D", self._draw_player_controller_editor)
        self.component_editors.register("Tilemap", self._draw_tilemap_editor)
        self.component_editors.register("ScriptBehaviour", self._draw_script_behaviour_editor)
        self.component_editors.register("SceneEntryPoint", self._draw_scene_entry_point_editor)
        self.component_editors.register("SceneLink", self._draw_scene_link_editor)
        self.component_editors.register("Canvas", self._draw_canvas_editor)
        self.component_editors.register("RectTransform", self._draw_rect_transform_editor)
        self.component_editors.register("UIText", self._draw_ui_text_editor)
        self.component_editors.register("UIButton", self._draw_ui_button_editor)

    def update(self, dt: float, world: "World", is_edit_mode: bool) -> None:
        """Processes keyboard-only inspector input."""
        del dt
        if not is_edit_mode:
            self._clear_text_edit()
            return
        if self.editing_text_field and rl.is_key_pressed(rl.KEY_ESCAPE):
            self._clear_text_edit()
            return
        if self.editing_text_field:
            return
        self._handle_tilemap_keyboard(world)

    def _commit_text_edit(self, world: "World") -> None:
        """Applies the active text buffer to the current field."""
        if not self.editing_text_field:
            return

        try:
            value_text = self.text_buffer.decode("utf-8").rstrip("\x00")
            value: Any
            if self.editing_value_type == "float":
                value = float(value_text) if value_text else 0.0
            elif self.editing_value_type == "int":
                value = int(float(value_text)) if value_text else 0
            else:
                value = value_text

            if self._editing_commit is not None:
                self._editing_commit(value)
            else:
                self._apply_property_change(world, self.editing_text_field, value)
        except Exception as exc:
            print(f"[INSPECTOR] Failed to commit edit: {exc}")

    def render(self, world: "World", x: int, y: int, width: int, height: int, is_edit_mode: bool) -> None:
        """Draws the inspector."""
        self._cursor_interactive_rects = []
        self._cursor_text_rects = []
        panel_x = x
        panel_y = y
        panel_w = width
        panel_h = height

        unity_header = rl.Color(56, 56, 56, 255)
        unity_tab_bg = rl.Color(42, 42, 42, 255)
        unity_tab_line = rl.Color(58, 121, 187, 255)
        unity_text = rl.Color(200, 200, 200, 255)
        unity_border = rl.Color(25, 25, 25, 255)
        header_height = 22

        with editor_scissor(rl.Rectangle(panel_x, panel_y, panel_w, panel_h)):
            rl.draw_rectangle(panel_x, panel_y, panel_w, panel_h, self.BG_COLOR)

            header_rect = rl.Rectangle(panel_x, panel_y, panel_w, header_height)
            rl.draw_rectangle_rec(header_rect, unity_header)

            tab_width = 65
            tab_rect = rl.Rectangle(panel_x + 2, panel_y + 2, tab_width, header_height - 4)
            rl.draw_rectangle_rec(tab_rect, unity_tab_bg)
            rl.draw_rectangle(int(panel_x + 2), int(panel_y + header_height - 2), tab_width, 2, unity_tab_line)
            rl.draw_text("Inspector", int(panel_x + 10), int(panel_y + 6), 10, unity_text)
            rl.draw_line(panel_x, int(panel_y + header_height), panel_x + panel_w, int(panel_y + header_height), unity_border)

            content_y = panel_y + header_height + 5
            selected_name = world.selected_entity_name
            if not selected_name:
                rl.draw_text("No selection", int(panel_x + 10), int(content_y + 10), 10, rl.Color(128, 128, 128, 255))
                return

            entity = world.get_entity_by_name(selected_name)
            if entity is None:
                return

            active_rect = rl.Rectangle(panel_x + 10, content_y, 14, 14)
            self._register_cursor_rect(active_rect)
            rl.draw_rectangle_rec(active_rect, rl.Color(42, 42, 42, 255))
            rl.draw_rectangle_lines_ex(active_rect, 1, rl.Color(80, 80, 80, 255))
            if entity.active:
                rl.draw_rectangle(int(panel_x + 13), int(content_y + 3), 8, 8, rl.Color(70, 130, 200, 255))

            rl.draw_text(entity.name, int(panel_x + 32), int(content_y + 2), 12, rl.Color(230, 230, 230, 255))
            if rl.check_collision_point_rec(rl.get_mouse_position(), active_rect) and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._apply_property_change(world, f"entity:{entity.id}:active", not entity.active)

            content_y += 22
            rl.draw_line(panel_x, int(content_y), panel_x + panel_w, int(content_y), unity_border)
            content_y += 5

            content_y = self._draw_entity_property("Active", entity.active, f"entity:{entity.id}:active", panel_x, content_y, panel_w, is_edit_mode, world)
            content_y = self._draw_entity_property("Tag", entity.tag, f"entity:{entity.id}:tag", panel_x, content_y, panel_w, is_edit_mode, world)
            content_y = self._draw_entity_property("Layer", entity.layer, f"entity:{entity.id}:layer", panel_x, content_y, panel_w, is_edit_mode, world)
            content_y += 4
            content_y = self._draw_scene_transition_block(entity, panel_x, content_y, panel_w, is_edit_mode, world)
            content_y += 4

            for component in entity.iter_components():
                if type(component).__name__ in self.SCENE_TRANSITION_HIDDEN_COMPONENTS:
                    continue
                content_y = self._draw_component(component, entity.id, panel_x, content_y, panel_w, is_edit_mode, world)
                content_y += 5

            add_btn_rect = rl.Rectangle(panel_x + 10, content_y + 10, panel_w - 20, 24)
            self._register_cursor_rect(add_btn_rect)
            if rl.gui_button(add_btn_rect, "Add Component"):
                self.show_add_menu = not self.show_add_menu

        if self.show_add_menu:
            self._draw_add_menu(world, entity, int(panel_x + 10), int(content_y + 35))

    def _draw_component(self, component: Component, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        comp_name = type(component).__name__
        entity = world.get_entity(entity_id)
        entity_name = entity.name if entity is not None else str(entity_id)
        unique_id = self._component_expansion_key(entity_name, comp_name)
        is_expanded = unique_id in self.expanded_components
        header_rect = rl.Rectangle(x + 2, y, width - 4, 20)
        origin = self._get_component_origin(entity, comp_name, component)
        accent_color = self._origin_color(origin)

        mouse_pos = rl.get_mouse_position()
        is_hover = rl.check_collision_point_rec(mouse_pos, header_rect)
        self._register_cursor_rect(header_rect)
        bg_color = rl.Color(70, 70, 70, 255) if is_hover else rl.Color(60, 60, 60, 255)
        rl.draw_rectangle_rec(header_rect, bg_color)
        rl.draw_rectangle(int(header_rect.x), int(header_rect.y), 3, int(header_rect.height), accent_color)

        arrow = "v" if is_expanded else ">"
        rl.draw_text(arrow, int(x + 8), int(y + 5), 10, rl.Color(200, 200, 200, 255))
        rl.draw_text(comp_name, int(x + 22), int(y + 5), 10, rl.Color(220, 220, 220, 255))
        badge = self._origin_badge(origin)
        badge_w = rl.measure_text(badge, 10) + 10
        badge_rect = rl.Rectangle(x + width - badge_w - 26, y + 3, badge_w, 14)
        rl.draw_rectangle_rec(badge_rect, accent_color)
        rl.draw_text(badge, int(badge_rect.x + 5), int(badge_rect.y + 2), 10, rl.BLACK)

        remove_rect = rl.Rectangle(x + width - 20, y + 2, 16, 16)
        remove_hover = False
        if comp_name != "Transform":
            remove_hover = rl.check_collision_point_rec(mouse_pos, remove_rect)
            self._register_cursor_rect(remove_rect)
            remove_color = rl.Color(200, 60, 60, 255) if remove_hover else rl.Color(150, 80, 80, 255)
            rl.draw_rectangle_rec(remove_rect, remove_color)
            rl.draw_text("x", int(x + width - 15), int(y + 3), 10, rl.WHITE)

            if remove_hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                if self._remove_component(world, entity_id, comp_name):
                    return y + 20

        if is_hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT) and not remove_hover:
            if is_expanded:
                self.expanded_components.discard(unique_id)
            else:
                self.expanded_components.add(unique_id)
            is_expanded = not is_expanded

        current_y = y + 22
        if is_expanded:
            editor = self.component_editors.get(comp_name)
            if editor is not None:
                current_y = editor(component, entity_id, x, current_y, width, is_edit, world)
            else:
                for prop_name, value in self._get_properties(component):
                    full_prop_id = f"{entity_id}:{comp_name}:{prop_name}"
                    current_y = self._draw_property(prop_name, value, full_prop_id, x, current_y, width, is_edit, world)

        return current_y

    def _draw_property(self, label: str, value: Any, prop_id: str, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        if isinstance(value, bool):
            return self._draw_bool_row(label, value, prop_id, x, y, width, is_edit, world)
        if isinstance(value, int) and not isinstance(value, bool):
            return self._draw_int_row(label, int(value), prop_id, x, y, width, is_edit, world)
        if isinstance(value, float):
            return self._draw_float_row(label, float(value), prop_id, x, y, width, is_edit, world)
        if isinstance(value, str):
            return self._draw_text_row(label, value, prop_id, x, y, width, is_edit, world)
        return self._draw_readonly_row(label, str(value), x, y, width)

    def _draw_float_field(
        self,
        value: float,
        prop_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        is_edit: bool,
        world: "World",
        on_commit: Optional[CommitCallback] = None,
    ) -> None:
        self._draw_number_field(f"{value:.2f}", prop_id, x, y, w, h, is_edit, world, "float", on_commit)

    def _draw_int_field(
        self,
        value: int,
        prop_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        is_edit: bool,
        world: "World",
        on_commit: Optional[CommitCallback] = None,
    ) -> None:
        self._draw_number_field(str(value), prop_id, x, y, w, h, is_edit, world, "int", on_commit)

    def _draw_number_field(
        self,
        value_text: str,
        prop_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        is_edit: bool,
        world: "World",
        value_type: str,
        on_commit: Optional[CommitCallback] = None,
    ) -> None:
        val_rect = rl.Rectangle(x, y + 1, w, h - 2)
        if self.editing_text_field == prop_id:
            self._draw_editing_field(prop_id, value_text, value_type, val_rect, world)
            return

        rl.draw_rectangle_rec(val_rect, rl.Color(42, 42, 42, 255))
        rl.draw_text(value_text, int(x + 5), int(y + 4), 10, rl.Color(200, 200, 200, 255))

        if not is_edit:
            return
        mouse_pos = rl.get_mouse_position()
        self._register_text_rect(val_rect)
        if rl.check_collision_point_rec(mouse_pos, val_rect):
            rl.draw_rectangle_lines_ex(val_rect, 1, rl.Color(70, 130, 200, 255))
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._begin_text_edit(prop_id, value_text, value_type, on_commit)

    def _draw_text_field(
        self,
        value: str,
        prop_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        is_edit: bool,
        world: "World",
        on_commit: Optional[CommitCallback] = None,
    ) -> None:
        val_rect = rl.Rectangle(x, y + 1, w, h - 2)
        if self.editing_text_field == prop_id:
            self._draw_editing_field(prop_id, value, "string", val_rect, world)
            return

        rl.draw_rectangle_rec(val_rect, rl.Color(42, 42, 42, 255))
        rl.draw_text(value, int(x + 5), int(y + 4), 10, rl.Color(200, 200, 200, 255))

        if not is_edit:
            return
        mouse_pos = rl.get_mouse_position()
        self._register_text_rect(val_rect)
        if rl.check_collision_point_rec(mouse_pos, val_rect):
            rl.draw_rectangle_lines_ex(val_rect, 1, rl.Color(70, 130, 200, 255))
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._begin_text_edit(prop_id, value, "string", on_commit)

    def _draw_bool_field(
        self,
        value: bool,
        prop_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        is_edit: bool,
        world: "World",
        on_toggle: Optional[CommitCallback] = None,
    ) -> None:
        del w
        check_rect = rl.Rectangle(x, y + 2, 14, 14)
        rl.draw_rectangle_rec(check_rect, rl.Color(42, 42, 42, 255))
        rl.draw_rectangle_lines_ex(check_rect, 1, rl.Color(80, 80, 80, 255))
        if value:
            inner = rl.Rectangle(x + 3, y + 5, 8, 8)
            rl.draw_rectangle_rec(inner, rl.Color(70, 130, 200, 255))

        if not is_edit:
            return
        mouse_pos = rl.get_mouse_position()
        self._register_cursor_rect(check_rect)
        if rl.check_collision_point_rec(mouse_pos, check_rect):
            rl.draw_rectangle_lines_ex(check_rect, 1, rl.Color(100, 150, 220, 255))
            if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                if on_toggle is not None:
                    on_toggle(not value)
                else:
                    self._apply_property_change(world, prop_id, not value)

    def _draw_editing_field(
        self,
        prop_id: str,
        display_value: str,
        value_type: str,
        rect: rl.Rectangle,
        world: "World",
    ) -> None:
        self._register_text_rect(rect)
        rl.draw_rectangle_rec(rect, rl.Color(30, 30, 30, 255))
        rl.draw_rectangle_lines_ex(rect, 1, rl.Color(0, 200, 255, 255))

        current_text = self.text_buffer.decode("utf-8").rstrip("\x00")
        if not current_text and display_value and self.editing_text_field != prop_id:
            current_text = display_value
        rl.draw_text(f"{current_text}_", int(rect.x + 5), int(rect.y + 3), 10, rl.WHITE)

        key = rl.get_char_pressed()
        while key > 0:
            if 32 <= key <= 125 and len(current_text) < len(self.text_buffer) - 1:
                self.text_buffer[len(current_text)] = key
                current_text += chr(key)
            key = rl.get_char_pressed()

        if rl.is_key_pressed(rl.KEY_BACKSPACE) and current_text:
            self.text_buffer[len(current_text) - 1] = 0

        if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
            self._commit_text_edit(world)
            self._clear_text_edit()
            return

        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            mouse_pos = rl.get_mouse_position()
            if not rl.check_collision_point_rec(mouse_pos, rect):
                self._commit_text_edit(world)
                self._clear_text_edit()

    def _draw_readonly_field(self, value: str, x: int, y: int, w: int, h: int) -> None:
        val_rect = rl.Rectangle(x, y, w, h)
        rl.draw_rectangle_rec(val_rect, rl.Color(36, 36, 36, 255))
        rl.draw_rectangle_lines_ex(val_rect, 1, rl.Color(52, 52, 52, 255))
        rl.draw_text(value, int(x + 5), int(y + 4), 10, rl.Color(140, 140, 140, 255))

    def _get_properties(self, component: Any) -> List[Tuple[str, Any]]:
        props: List[Tuple[str, Any]] = []
        if hasattr(component, "to_dict"):
            try:
                data = component.to_dict()
                for key in data.keys():
                    if hasattr(component, key):
                        value = getattr(component, key)
                        if isinstance(value, (bool, int, float, str)):
                            props.append((key, value))
                return props
            except Exception:
                pass

        for attr in dir(component):
            if attr.startswith("_") or callable(getattr(component, attr)):
                continue
            value = getattr(component, attr)
            if isinstance(value, (bool, int, float, str)):
                props.append((attr, value))
        return props

    def _draw_add_menu(self, world: "World", entity: Entity, x: int, y: int) -> None:
        available = []
        for descriptor in self.registry.list_descriptors():
            if descriptor.name in self.SCENE_TRANSITION_ADD_MENU_HIDDEN_COMPONENTS:
                continue
            if not entity.has_component(descriptor.component_class):
                available.append(descriptor)

        item_height = 24
        menu_w = 200
        menu_h = max(1, len(available)) * item_height
        if y + menu_h > rl.get_screen_height():
            y -= menu_h + 30

        menu_rect = rl.Rectangle(x, y, menu_w, menu_h)
        self._register_cursor_rect(menu_rect)
        rl.draw_rectangle_rec(menu_rect, rl.Color(40, 40, 40, 255))
        rl.draw_rectangle_lines_ex(menu_rect, 1, rl.Color(80, 80, 80, 255))

        mouse = rl.get_mouse_position()
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            if not rl.check_collision_point_rec(mouse, menu_rect):
                self.show_add_menu = False
                return

        for index, descriptor in enumerate(available):
            rect = rl.Rectangle(x, y + index * item_height, menu_w, item_height)
            self._register_cursor_rect(rect)
            is_hover = rl.check_collision_point_rec(mouse, rect)
            if is_hover:
                rl.draw_rectangle_rec(rect, rl.Color(60, 60, 60, 255))
                if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                    self._add_component(world, entity.id, descriptor.name)
                    self.show_add_menu = False
            badge_color = self._origin_color(descriptor.origin)
            badge_rect = rl.Rectangle(x + 8, y + index * item_height + 4, 28, 14)
            rl.draw_rectangle_rec(badge_rect, badge_color)
            rl.draw_text(descriptor.badge, int(badge_rect.x + 4), int(badge_rect.y + 2), 10, rl.BLACK)
            rl.draw_text(descriptor.name, int(x + 44), int(y + index * item_height + 6), 10, rl.Color(200, 200, 200, 255))

    def _draw_entity_property(
        self,
        label: str,
        value: Any,
        prop_id: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
    ) -> int:
        return self._draw_property(label, value, prop_id, x, y, width, is_edit, world)

    def _begin_text_edit(
        self,
        prop_id: str,
        value: Any,
        value_type: str,
        on_commit: Optional[CommitCallback] = None,
    ) -> None:
        self.editing_text_field = prop_id
        self.editing_value_type = value_type
        self._editing_commit = on_commit
        self.text_buffer[:] = b"\x00" * len(self.text_buffer)
        encoded = str(value).encode("utf-8")[: len(self.text_buffer) - 1]
        self.text_buffer[: len(encoded)] = encoded

    def _clear_text_edit(self) -> None:
        self.editing_text_field = None
        self.editing_value_type = "float"
        self._editing_commit = None
        self.text_buffer[:] = b"\x00" * len(self.text_buffer)

    def get_cursor_intent(self, mouse_pos: Optional[rl.Vector2] = None) -> CursorVisualState:
        mouse = rl.get_mouse_position() if mouse_pos is None else mouse_pos
        for rect in self._cursor_text_rects:
            if rl.check_collision_point_rec(mouse, rect):
                return CursorVisualState.TEXT
        for rect in self._cursor_interactive_rects:
            if rl.check_collision_point_rec(mouse, rect):
                return CursorVisualState.INTERACTIVE
        return CursorVisualState.DEFAULT

    def _register_cursor_rect(self, rect: rl.Rectangle) -> None:
        self._cursor_interactive_rects.append(rl.Rectangle(rect.x, rect.y, rect.width, rect.height))

    def _register_text_rect(self, rect: rl.Rectangle) -> None:
        self._cursor_text_rects.append(rl.Rectangle(rect.x, rect.y, rect.width, rect.height))

    def _apply_property_change(self, world: "World", prop_id: str, value: Any) -> bool:
        parts = prop_id.split(":")

        if parts[0] == "entity" and len(parts) >= 3:
            entity = world.get_entity(int(parts[1]))
            if entity is None:
                return False
            property_name = parts[2]
            if self._scene_manager is not None:
                return self._scene_manager.update_entity_property(entity.name, property_name, value)
            setattr(entity, property_name, value)
            return True

        if len(parts) < 3:
            return False

        entity = world.get_entity(int(parts[0]))
        if entity is None:
            return False
        return self._apply_component_property(world, entity.name, parts[1], parts[2], value)

    def _apply_component_property(
        self,
        world: "World",
        entity_name: str,
        component_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        if self._scene_manager is not None:
            return self._scene_manager.apply_edit_to_world(entity_name, component_name, property_name, value)

        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        component = self._find_component(entity, component_name)
        if component is None:
            return False
        setattr(component, property_name, value)
        return True

    def _entity_name_from_id(self, world: "World", entity_id: int) -> Optional[str]:
        entity = world.get_entity(entity_id)
        return entity.name if entity is not None else None

    def _current_component_payload(self, world: "World", entity_name: str, component_name: str) -> Optional[Dict[str, Any]]:
        if self._scene_manager is not None and self._scene_manager.current_scene is not None:
            entity_data = self._scene_manager.current_scene.find_entity(entity_name)
            if entity_data is not None:
                components = entity_data.get("components", {})
                if component_name in components:
                    return copy.deepcopy(components[component_name])

        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return None
        component = self._find_component(entity, component_name)
        if component is None:
            return None
        if hasattr(component, "to_dict"):
            return copy.deepcopy(component.to_dict())

        payload: Dict[str, Any] = {}
        for attr in dir(component):
            if attr.startswith("_") or callable(getattr(component, attr)):
                continue
            value = getattr(component, attr)
            if isinstance(value, (bool, int, float, str, list, dict, type(None))):
                payload[attr] = copy.deepcopy(value)
        return payload

    def _find_component(self, entity: Entity, component_name: str) -> Optional[Component]:
        for component in entity.iter_components():
            if type(component).__name__ == component_name:
                return component
        return None

    def _entity_has_component(self, world: "World", entity_name: str, component_name: str) -> bool:
        entity = world.get_entity_by_name(entity_name)
        return bool(entity is not None and self._find_component(entity, component_name) is not None)

    def _resolve_tilemap_tool_entity_name(self, world: "World") -> Optional[str]:
        stored_name = str(self._tilemap_authoring.entity_name or "").strip()
        if stored_name and self._entity_has_component(world, stored_name, "Tilemap"):
            return stored_name
        selected_name = str(world.selected_entity_name or "").strip()
        if selected_name and self._entity_has_component(world, selected_name, "Tilemap"):
            self._tilemap_authoring.entity_name = selected_name
            return selected_name
        self._tilemap_authoring.enabled = False
        self._tilemap_authoring.entity_name = ""
        return None

    def _resolve_tilemap_layer_name(self, payload: Dict[str, Any], preferred: Optional[str]) -> str:
        preferred_name = str(preferred or "").strip()
        layers = payload.get("layers", [])
        if isinstance(layers, list):
            for layer in layers:
                if isinstance(layer, dict) and str(layer.get("name", "")).strip() == preferred_name:
                    return preferred_name
            for layer in layers:
                if isinstance(layer, dict):
                    candidate = str(layer.get("name", "")).strip()
                    if candidate:
                        return candidate
        return str(payload.get("default_layer_name", "") or "Layer").strip() or "Layer"

    def _find_tilemap_layer_payload(self, payload: Dict[str, Any], layer_name: str) -> Optional[Dict[str, Any]]:
        for layer in payload.get("layers", []):
            if isinstance(layer, dict) and str(layer.get("name", "")).strip() == str(layer_name or "").strip():
                return layer
        return None

    def _ensure_tilemap_layer_payload(self, payload: Dict[str, Any], layer_name: str) -> Dict[str, Any]:
        existing = self._find_tilemap_layer_payload(payload, layer_name)
        if existing is not None:
            return existing
        normalized_name = str(layer_name or payload.get("default_layer_name", "Layer")).strip() or "Layer"
        layer_payload = {
            "name": normalized_name,
            "visible": True,
            "opacity": 1.0,
            "locked": False,
            "offset_x": 0.0,
            "offset_y": 0.0,
            "collision_layer": 0,
            "tilemap_source": {},
            "metadata": {},
            "tiles": [],
        }
        payload.setdefault("layers", []).append(layer_payload)
        return layer_payload

    def _find_serialized_tile_entry(self, layer_payload: Dict[str, Any], x: int, y: int) -> Optional[Dict[str, Any]]:
        for tile in layer_payload.get("tiles", []):
            if not isinstance(tile, dict):
                continue
            if int(tile.get("x", 0)) == int(x) and int(tile.get("y", 0)) == int(y):
                return tile
        return None

    def _set_tilemap_tileset_reference(self, payload: Dict[str, Any], locator: Any) -> None:
        reference = normalize_asset_reference(locator)
        payload["tileset"] = clone_asset_reference(reference)
        payload["tileset_path"] = reference.get("path", "")

    def _set_tilemap_layer_source(self, payload: Dict[str, Any], layer_name: str, locator: Any) -> None:
        layer = self._ensure_tilemap_layer_payload(payload, layer_name)
        layer["tilemap_source"] = clone_asset_reference(locator)

    def _set_tilemap_layer_field(self, payload: Dict[str, Any], layer_name: str, field_name: str, value: Any) -> None:
        layer = self._ensure_tilemap_layer_payload(payload, layer_name)
        layer[field_name] = copy.deepcopy(value)

    def _append_tilemap_layer(self, payload: Dict[str, Any]) -> None:
        layers = payload.setdefault("layers", [])
        existing_names = {str(layer.get("name", "")).strip() for layer in layers if isinstance(layer, dict)}
        base_name = str(payload.get("default_layer_name", "Layer")).strip() or "Layer"
        candidate = base_name
        suffix = 1
        while candidate in existing_names:
            candidate = f"{base_name}_{suffix}"
            suffix += 1
        layers.append(
            {
                "name": candidate,
                "visible": True,
                "opacity": 1.0,
                "locked": False,
                "offset_x": 0.0,
                "offset_y": 0.0,
                "collision_layer": 0,
                "tilemap_source": {},
                "metadata": {},
                "tiles": [],
            }
        )

    def _resolve_tilemap_palette_source(self, payload: Dict[str, Any], layer_name: str) -> dict[str, str]:
        layer = self._find_tilemap_layer_payload(payload, layer_name)
        if layer is not None:
            layer_source = normalize_asset_reference(layer.get("tilemap_source"))
            if layer_source.get("guid") or layer_source.get("path"):
                return layer_source
        return normalize_asset_reference(payload.get("tileset"))

    def _normalize_tilemap_tool_mode(self, mode: str) -> str:
        normalized = str(mode or "").strip().lower()
        if normalized in {"paint", "erase", "pick", "box_fill", "flood_fill", "stamp"}:
            return normalized
        return "paint"

    def _tilemap_effective_mode(self) -> str:
        if self._tilemap_authoring.shortcut_mode:
            return self._tilemap_authoring.shortcut_mode
        try:
            if rl.is_key_down(rl.KEY_LEFT_CONTROL) or rl.is_key_down(rl.KEY_RIGHT_CONTROL):
                return "pick"
            if rl.is_key_down(rl.KEY_LEFT_SHIFT) or rl.is_key_down(rl.KEY_RIGHT_SHIFT):
                return "erase"
        except Exception:
            pass
        return self._normalize_tilemap_tool_mode(self._tilemap_authoring.mode)

    def _handle_tilemap_keyboard(self, world: "World") -> None:
        entity_name = self._resolve_tilemap_tool_entity_name(world)
        if entity_name is None:
            return

        self._tilemap_authoring.shortcut_mode = ""
        ctrl_down = bool(rl.is_key_down(rl.KEY_LEFT_CONTROL) or rl.is_key_down(rl.KEY_RIGHT_CONTROL))
        shift_down = bool(rl.is_key_down(rl.KEY_LEFT_SHIFT) or rl.is_key_down(rl.KEY_RIGHT_SHIFT))

        if ctrl_down:
            self._tilemap_authoring.shortcut_mode = "pick"
        elif shift_down:
            self._tilemap_authoring.shortcut_mode = "erase"

        pressed_b = bool(rl.is_key_pressed(rl.KEY_B))
        pressed_d = bool(rl.is_key_pressed(rl.KEY_D))
        pressed_i = bool(rl.is_key_pressed(rl.KEY_I))
        pressed_u = bool(rl.is_key_pressed(rl.KEY_U))
        pressed_g = bool(rl.is_key_pressed(rl.KEY_G))

        if pressed_b:
            self.set_tilemap_tool_mode("paint")
        elif pressed_d:
            self.set_tilemap_tool_mode("erase")
        elif pressed_i:
            self.set_tilemap_tool_mode("pick")
        elif pressed_u:
            self.set_tilemap_tool_mode("box_fill")
        elif pressed_g:
            self.set_tilemap_tool_mode("flood_fill")

        if not self._tilemap_authoring.palette_focused:
            return
        entries = self.list_tilemap_palette_entries(world, entity_name, self._tilemap_authoring.layer_name)
        if not entries:
            return

        cols = 4
        index = self._tilemap_current_palette_index(entries)

        pressed_right = bool(rl.is_key_pressed(rl.KEY_RIGHT))
        pressed_left = bool(rl.is_key_pressed(rl.KEY_LEFT))
        pressed_down = bool(rl.is_key_pressed(rl.KEY_DOWN))
        pressed_up = bool(rl.is_key_pressed(rl.KEY_UP))
        pressed_home = bool(rl.is_key_pressed(rl.KEY_HOME))
        pressed_end = bool(rl.is_key_pressed(rl.KEY_END))
        pressed_page_down = bool(rl.is_key_pressed(rl.KEY_PAGE_DOWN))
        pressed_page_up = bool(rl.is_key_pressed(rl.KEY_PAGE_UP))
        pressed_enter = bool(rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER))

        if pressed_right:
            index += 1
        elif pressed_left:
            index -= 1
        elif pressed_down:
            index += cols
        elif pressed_up:
            index -= cols
        elif pressed_home:
            index = 0
        elif pressed_end:
            index = len(entries) - 1
        elif pressed_page_down:
            index += cols * 3
        elif pressed_page_up:
            index -= cols * 3

        self._tilemap_authoring.palette_selected_index = max(0, min(len(entries) - 1, index))

        if pressed_enter:
            selected = entries[self._tilemap_authoring.palette_selected_index]
            self.set_tilemap_selected_tile(
                world,
                entity_name,
                str(selected.get("tile_id", "")),
                source=selected.get("source"),
            )

    def _tilemap_current_palette_index(self, entries: List[Dict[str, Any]]) -> int:
        if not entries:
            self._tilemap_authoring.palette_selected_index = 0
            return 0
        if self._tilemap_authoring.palette_focused:
            self._tilemap_authoring.palette_selected_index = max(0, min(len(entries) - 1, self._tilemap_authoring.palette_selected_index))
            return self._tilemap_authoring.palette_selected_index
        return self._sync_tilemap_palette_index_to_tile(entries)

    def _sync_tilemap_palette_index_to_tile(self, entries: List[Dict[str, Any]]) -> int:
        if not entries:
            self._tilemap_authoring.palette_selected_index = 0
            return 0
        selected_tile = str(self._tilemap_authoring.tile_id or "")
        for index, entry in enumerate(entries):
            if str(entry.get("tile_id", "")) == selected_tile:
                self._tilemap_authoring.palette_selected_index = index
                return index
        self._tilemap_authoring.palette_selected_index = max(0, min(len(entries) - 1, self._tilemap_authoring.palette_selected_index))
        return self._tilemap_authoring.palette_selected_index

    def _synchronize_tilemap_tool_selection(self, world: "World", entity_name: str) -> None:
        payload = self._current_component_payload(world, entity_name, "Tilemap")
        if payload is None:
            return
        self._tilemap_authoring.layer_name = self._resolve_tilemap_layer_name(payload, self._tilemap_authoring.layer_name)
        source = self._resolve_tilemap_palette_source(payload, self._tilemap_authoring.layer_name)
        entries = self.list_tilemap_palette_entries(world, entity_name, self._tilemap_authoring.layer_name)
        valid_tile_ids = {str(entry.get("tile_id", "")) for entry in entries}
        if entries and self._tilemap_authoring.tile_id not in valid_tile_ids:
            self._tilemap_authoring.tile_id = str(entries[0].get("tile_id", ""))
        if entries:
            self._sync_tilemap_palette_index_to_tile(entries)
        if source.get("guid") or source.get("path"):
            self._tilemap_authoring.source = source

    def _build_tilemap_palette_entries(self, payload: Dict[str, Any], asset_ref: dict[str, str]) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for tile_id, label in self._list_tilemap_slice_options(asset_ref):
            entries.append(self._build_tilemap_visual_entry(payload, asset_ref, tile_id, label=label))
        if entries:
            return entries
        for tile_id, label in self._list_tilemap_grid_options(payload, asset_ref):
            entries.append(self._build_tilemap_visual_entry(payload, asset_ref, tile_id, label=label))
        return entries

    def _build_tilemap_visual_entry(
        self,
        payload: Dict[str, Any],
        asset_ref: dict[str, str],
        tile_id: str,
        *,
        label: str,
    ) -> Dict[str, Any]:
        source_rect, resolution = self._resolve_tilemap_source_rect(payload, asset_ref, tile_id)
        return {
            "tile_id": str(tile_id or "").strip(),
            "label": str(label or tile_id or "").strip(),
            "source": clone_asset_reference(asset_ref),
            "texture_path": self._resolve_tilemap_texture_path(asset_ref),
            "source_rect": copy.deepcopy(source_rect) if source_rect is not None else None,
            "resolution": resolution,
            "status": "ok" if source_rect is not None else "unresolved",
        }

    def _get_tilemap_asset_service(self) -> Optional[AssetService]:
        current_scene = getattr(self._scene_manager, "current_scene", None) if self._scene_manager is not None else None
        scene_path = str(getattr(current_scene, "source_path", "") or "").strip()
        if not scene_path:
            return None
        project_root = Path(scene_path).resolve().parent.parent
        root_key = project_root.as_posix()
        if self._tilemap_asset_service is not None and self._tilemap_asset_service_root == root_key:
            return self._tilemap_asset_service
        project_file = project_root / ProjectService.PROJECT_FILE
        if not project_file.exists():
            return None
        try:
            project_service = ProjectService(
                project_root.as_posix(),
                global_state_dir=(project_root / ".motor" / "inspector_state").as_posix(),
                auto_ensure=False,
            )
            project_service.open_project(project_root.as_posix())
        except Exception:
            return None
        self._tilemap_project_service = project_service
        self._tilemap_asset_service = AssetService(project_service)
        self._tilemap_asset_service_root = root_key
        return self._tilemap_asset_service

    def _list_tilemap_slice_options(self, asset_ref: dict[str, str]) -> List[tuple[str, str]]:
        if not (asset_ref.get("guid") or asset_ref.get("path")):
            return []
        asset_service = self._get_tilemap_asset_service()
        if asset_service is None:
            return []
        try:
            slices = asset_service.list_slices(asset_ref)
        except Exception:
            return []
        options: List[tuple[str, str]] = []
        for slice_info in slices:
            name = str(slice_info.get("name", "")).strip()
            if name:
                options.append((name, name))
        return options

    def _list_tilemap_grid_options(self, payload: Dict[str, Any], asset_ref: dict[str, str]) -> List[tuple[str, str]]:
        tile_width = max(1, int(payload.get("tileset_tile_width", payload.get("cell_width", 1)) or 1))
        tile_height = max(1, int(payload.get("tileset_tile_height", payload.get("cell_height", 1)) or 1))
        spacing = max(0, int(payload.get("tileset_spacing", 0) or 0))
        margin = max(0, int(payload.get("tileset_margin", 0) or 0))
        columns = max(0, int(payload.get("tileset_columns", 0) or 0))
        image_width = 0
        image_height = 0
        asset_service = self._get_tilemap_asset_service()
        if asset_service is not None and (asset_ref.get("guid") or asset_ref.get("path")):
            try:
                image_width, image_height = asset_service.get_sprite_image_size(asset_ref)
            except Exception:
                image_width, image_height = (0, 0)
        if columns <= 0 and image_width > 0:
            usable_width = max(0, image_width - (margin * 2) + spacing)
            columns = max(1, usable_width // max(1, tile_width + spacing))
        if columns <= 0:
            return []
        rows = 1
        if image_height > 0:
            usable_height = max(0, image_height - (margin * 2) + spacing)
            rows = max(1, usable_height // max(1, tile_height + spacing))
        total = max(1, rows * columns)
        return [(str(index), str(index)) for index in range(total)]

    def _resolve_tilemap_texture_path(self, asset_ref: dict[str, str]) -> str:
        asset_service = self._get_tilemap_asset_service()
        if asset_service is None or not (asset_ref.get("guid") or asset_ref.get("path")):
            return ""
        try:
            return asset_service.resolve_asset_path(asset_ref).as_posix()
        except Exception:
            return ""

    def _resolve_tilemap_source_rect(
        self,
        payload: Dict[str, Any],
        asset_ref: dict[str, str],
        tile_id: str,
    ) -> tuple[Dict[str, int] | None, str]:
        slice_rect = self._resolve_tilemap_slice_rect(asset_ref, tile_id)
        if slice_rect is not None:
            return slice_rect, "slice"
        grid_rect = self._resolve_tilemap_grid_rect(payload, tile_id)
        if grid_rect is not None:
            return grid_rect, "grid"
        return None, "unresolved"

    def _resolve_tilemap_slice_rect(self, asset_ref: dict[str, str], tile_id: str) -> Dict[str, int] | None:
        asset_service = self._get_tilemap_asset_service()
        if asset_service is None or not tile_id or not (asset_ref.get("guid") or asset_ref.get("path")):
            return None
        try:
            slice_rect = asset_service.get_slice_rect(asset_ref, tile_id)
        except Exception:
            slice_rect = None
        if slice_rect is None:
            return None
        return {
            "x": int(slice_rect.get("x", 0)),
            "y": int(slice_rect.get("y", 0)),
            "width": max(1, int(slice_rect.get("width", 0))),
            "height": max(1, int(slice_rect.get("height", 0))),
        }

    def _resolve_tilemap_grid_rect(self, payload: Dict[str, Any], tile_id: str) -> Dict[str, int] | None:
        tile_width = max(1, int(payload.get("tileset_tile_width", payload.get("cell_width", 1)) or 1))
        tile_height = max(1, int(payload.get("tileset_tile_height", payload.get("cell_height", 1)) or 1))
        columns = max(1, int(payload.get("tileset_columns", 0) or 0))
        spacing = max(0, int(payload.get("tileset_spacing", 0) or 0))
        margin = max(0, int(payload.get("tileset_margin", 0) or 0))
        tile_index = self._parse_tilemap_tile_index(tile_id)
        if tile_index is None:
            if columns != 1:
                return None
            tile_index = 0
        if tile_index < 0:
            return None
        return {
            "x": margin + ((tile_index % columns) * (tile_width + spacing)),
            "y": margin + ((tile_index // columns) * (tile_height + spacing)),
            "width": tile_width,
            "height": tile_height,
        }

    def _parse_tilemap_tile_index(self, tile_id: str) -> Optional[int]:
        try:
            return int(str(tile_id or "").strip())
        except (TypeError, ValueError):
            return None

    def _tilemap_transform_scale_is_valid(self, transform: Component) -> bool:
        try:
            scale_x = float(getattr(transform, "scale_x", 1.0))
            scale_y = float(getattr(transform, "scale_y", 1.0))
        except (TypeError, ValueError):
            return False
        return math.isfinite(scale_x) and math.isfinite(scale_y) and scale_x != 0.0 and scale_y != 0.0

    def _tilemap_world_to_local_point(self, transform: Component, world_x: float, world_y: float) -> Optional[tuple[float, float]]:
        if not self._tilemap_transform_scale_is_valid(transform):
            return None
        scale_x = float(getattr(transform, "scale_x", 1.0))
        scale_y = float(getattr(transform, "scale_y", 1.0))
        dx = float(world_x) - float(getattr(transform, "x", 0.0))
        dy = float(world_y) - float(getattr(transform, "y", 0.0))
        radians = math.radians(float(getattr(transform, "rotation", 0.0)))
        cos_r = math.cos(radians)
        sin_r = math.sin(radians)
        local_x = (dx * cos_r + dy * sin_r) / scale_x
        local_y = (-dx * sin_r + dy * cos_r) / scale_y
        return (local_x, local_y)

    def _tilemap_local_to_world_point(self, transform: Component, local_x: float, local_y: float) -> tuple[float, float]:
        scale_x = float(getattr(transform, "scale_x", 1.0))
        scale_y = float(getattr(transform, "scale_y", 1.0))
        scaled_x = float(local_x) * scale_x
        scaled_y = float(local_y) * scale_y
        radians = math.radians(float(getattr(transform, "rotation", 0.0)))
        cos_r = math.cos(radians)
        sin_r = math.sin(radians)
        world_x = float(getattr(transform, "x", 0.0)) + (scaled_x * cos_r) - (scaled_y * sin_r)
        world_y = float(getattr(transform, "y", 0.0)) + (scaled_x * sin_r) + (scaled_y * cos_r)
        return (world_x, world_y)

    def _tilemap_cell_draw_rect(
        self,
        transform: Component,
        local_x: float,
        local_y: float,
        width: float,
        height: float,
    ) -> dict[str, float]:
        if not self._tilemap_transform_scale_is_valid(transform):
            return {"x": float(getattr(transform, "x", 0.0)), "y": float(getattr(transform, "y", 0.0)), "width": 0.0, "height": 0.0}
        scale_x = float(getattr(transform, "scale_x", 1.0))
        scale_y = float(getattr(transform, "scale_y", 1.0))
        anchor_x = local_x + (width if scale_x < 0.0 else 0.0)
        anchor_y = local_y + (height if scale_y < 0.0 else 0.0)
        world_x, world_y = self._tilemap_local_to_world_point(transform, anchor_x, anchor_y)
        return {
            "x": world_x,
            "y": world_y,
            "width": abs(width * scale_x),
            "height": abs(height * scale_y),
        }

    def _tilemap_cell_world_corners(
        self,
        transform: Component,
        local_x: float,
        local_y: float,
        width: float,
        height: float,
    ) -> list[tuple[float, float]]:
        if not self._tilemap_transform_scale_is_valid(transform):
            x = float(getattr(transform, "x", 0.0))
            y = float(getattr(transform, "y", 0.0))
            return [(x, y), (x, y), (x, y), (x, y)]
        return [
            self._tilemap_local_to_world_point(transform, local_x, local_y),
            self._tilemap_local_to_world_point(transform, local_x + width, local_y),
            self._tilemap_local_to_world_point(transform, local_x + width, local_y + height),
            self._tilemap_local_to_world_point(transform, local_x, local_y + height),
        ]

    def _tilemap_source_rect_for_transform(self, source_rect: Optional[Dict[str, Any]], transform: Component) -> Optional[dict[str, float]]:
        if not isinstance(source_rect, dict):
            return None
        rect = {
            "x": float(source_rect.get("x", 0.0)),
            "y": float(source_rect.get("y", 0.0)),
            "width": float(source_rect.get("width", 0.0)),
            "height": float(source_rect.get("height", 0.0)),
        }
        if float(getattr(transform, "scale_x", 1.0)) < 0.0:
            rect["x"] += rect["width"]
            rect["width"] *= -1.0
        if float(getattr(transform, "scale_y", 1.0)) < 0.0:
            rect["y"] += rect["height"]
            rect["height"] *= -1.0
        return rect

    def _build_tilemap_preview_tile(
        self,
        payload: Dict[str, Any],
        transform: Component,
        cell: tuple[int, int],
        tile_id: str,
        asset_ref: Dict[str, str],
        cell_width: int,
        cell_height: int,
        layer_offset_x: float,
        layer_offset_y: float,
    ) -> Dict[str, Any]:
        normalized_tile_id = str(tile_id or "").strip()
        normalized_asset_ref = normalize_asset_reference(asset_ref)
        source_rect, resolution = self._resolve_tilemap_source_rect(payload, normalized_asset_ref, normalized_tile_id)
        texture_path = self._resolve_tilemap_texture_path(normalized_asset_ref)
        status = "ok"
        if not self._tilemap_transform_scale_is_valid(transform):
            status = "invalid_transform"
        elif not (normalized_asset_ref.get("guid") or normalized_asset_ref.get("path")):
            status = "missing_source"
        elif not normalized_tile_id:
            status = "missing_tile"
        elif source_rect is None:
            status = "unresolved_tile"
        elif not texture_path:
            status = "missing_texture"
        cell_x, cell_y = int(cell[0]), int(cell[1])
        local_x = layer_offset_x + (cell_x * cell_width)
        local_y = layer_offset_y + (cell_y * cell_height)
        return {
            "cell": (cell_x, cell_y),
            "tile_id": normalized_tile_id,
            "source": clone_asset_reference(normalized_asset_ref),
            "texture_path": texture_path,
            "source_rect": self._tilemap_source_rect_for_transform(source_rect, transform),
            "resolution": resolution,
            "cell_rect": self._tilemap_cell_draw_rect(transform, local_x, local_y, float(cell_width), float(cell_height)),
            "cell_corners": self._tilemap_cell_world_corners(transform, local_x, local_y, float(cell_width), float(cell_height)),
            "rotation": float(getattr(transform, "rotation", 0.0)),
            "scale": {
                "x": float(getattr(transform, "scale_x", 1.0)),
                "y": float(getattr(transform, "scale_y", 1.0)),
            },
            "status": status,
            "status_label": self._tilemap_preview_status_label(status),
            "editable": status == "ok",
        }

    def _tilemap_preview_status_label(self, status: str) -> str:
        return {
            "ok": "Ready",
            "missing_layer": "Missing layer",
            "hidden": "Hidden layer",
            "locked": "Locked layer",
            "missing_source": "Missing tileset",
            "missing_tile": "Missing tile",
            "unresolved_tile": "Unresolved tile",
            "missing_texture": "Missing texture",
            "invalid_transform": "Invalid transform",
        }.get(str(status or "").strip(), "Invalid")

    def _build_tilemap_preview_snapshot(
        self,
        world: "World",
        entity_name: str,
        cell: tuple[int, int],
    ) -> Optional[Dict[str, Any]]:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return None
        transform = self._find_component(entity, "Transform")
        tilemap = self._find_component(entity, "Tilemap")
        if transform is None or tilemap is None or not getattr(tilemap, "enabled", True):
            return None
        payload = self._current_component_payload(world, entity_name, "Tilemap")
        if payload is None:
            return None
        layer_name = self._resolve_tilemap_layer_name(payload, self._tilemap_authoring.layer_name)
        layer = self._find_tilemap_layer_payload(payload, layer_name)
        asset_ref = self._resolve_tilemap_palette_source(payload, layer_name)
        tile_id = str(self._tilemap_authoring.tile_id or "").strip()
        source_rect, resolution = self._resolve_tilemap_source_rect(payload, asset_ref, tile_id)
        texture_path = self._resolve_tilemap_texture_path(asset_ref)
        cell_width = max(1, int(payload.get("cell_width", getattr(tilemap, "cell_width", 1)) or 1))
        cell_height = max(1, int(payload.get("cell_height", getattr(tilemap, "cell_height", 1)) or 1))
        layer_offset_x = float((layer or {}).get("offset_x", 0.0))
        layer_offset_y = float((layer or {}).get("offset_y", 0.0))
        mode = self._tilemap_effective_mode()
        status = "ok"
        if not self._tilemap_transform_scale_is_valid(transform):
            status = "invalid_transform"
        if layer is None:
            status = "missing_layer"
        elif not bool(layer.get("visible", True)):
            status = "hidden"
        elif bool(layer.get("locked", False)):
            status = "locked"
        elif mode in {"paint", "box_fill", "flood_fill"} and not (asset_ref.get("guid") or asset_ref.get("path")):
            status = "missing_source"
        elif mode in {"paint", "box_fill", "flood_fill"} and not tile_id:
            status = "missing_tile"
        elif mode == "stamp" and not self._tilemap_authoring.stamp_tiles:
            status = "missing_tile"
        elif mode in {"paint", "box_fill", "flood_fill"} and source_rect is None:
            status = "unresolved_tile"
        elif mode in {"paint", "box_fill", "flood_fill"} and not texture_path:
            status = "missing_texture"
        cell_x, cell_y = int(cell[0]), int(cell[1])
        local_x = layer_offset_x + (cell_x * cell_width)
        local_y = layer_offset_y + (cell_y * cell_height)
        cell_rect = self._tilemap_cell_draw_rect(transform, local_x, local_y, float(cell_width), float(cell_height))
        cell_corners = self._tilemap_cell_world_corners(transform, local_x, local_y, float(cell_width), float(cell_height))
        preview_tiles: list[dict[str, Any]] = []
        if mode == "box_fill" and self._tilemap_authoring.box_fill_anchor is not None:
            anchor_x, anchor_y = self._tilemap_authoring.box_fill_anchor
            min_x = min(anchor_x, cell_x)
            max_x = max(anchor_x, cell_x)
            min_y = min(anchor_y, cell_y)
            max_y = max(anchor_y, cell_y)
            box_local_x = layer_offset_x + (min_x * cell_width)
            box_local_y = layer_offset_y + (min_y * cell_height)
            box_width = float((max_x - min_x + 1) * cell_width)
            box_height = float((max_y - min_y + 1) * cell_height)
            cell_corners = self._tilemap_cell_world_corners(transform, box_local_x, box_local_y, box_width, box_height)
        elif mode == "stamp" and status == "ok":
            for stamp_tile in self._tilemap_authoring.stamp_tiles:
                offset_x = int(stamp_tile.get("offset_x", 0))
                offset_y = int(stamp_tile.get("offset_y", 0))
                stamp_source = normalize_asset_reference(stamp_tile.get("source"))
                if not (stamp_source.get("guid") or stamp_source.get("path")):
                    stamp_source = asset_ref
                preview_tile = self._build_tilemap_preview_tile(
                    payload,
                    transform,
                    (cell_x + offset_x, cell_y + offset_y),
                    str(stamp_tile.get("tile_id", "")),
                    stamp_source,
                    cell_width,
                    cell_height,
                    layer_offset_x,
                    layer_offset_y,
                )
                preview_tiles.append(preview_tile)
            invalid_stamp_tiles = [tile for tile in preview_tiles if not bool(tile.get("editable"))]
            if invalid_stamp_tiles:
                status = str(invalid_stamp_tiles[0].get("status", "unresolved_tile"))
            if preview_tiles:
                first_tile = preview_tiles[0]
                texture_path = str(first_tile.get("texture_path", ""))
                source_rect = first_tile.get("source_rect")
                resolution = str(first_tile.get("resolution", "unresolved") or "unresolved")
        if mode == "flood_fill":
            self._tilemap_authoring.flood_effective_bounds = None
            self._tilemap_authoring.flood_preview_count = 0
            self._tilemap_authoring.flood_truncated = False
        if mode == "flood_fill" and status == "ok" and layer is not None:
            flood_cells, flood_bounds, flood_truncated = self._compute_tilemap_flood_fill_cells(layer, (cell_x, cell_y))
            self._tilemap_authoring.flood_effective_bounds = flood_bounds
            self._tilemap_authoring.flood_preview_count = len(flood_cells)
            self._tilemap_authoring.flood_truncated = flood_truncated
        snapshot_source_rect = self._tilemap_source_rect_for_transform(source_rect, transform)
        if mode == "stamp" and preview_tiles:
            snapshot_source_rect = copy.deepcopy(preview_tiles[0].get("source_rect"))
        return {
            "entity_name": entity_name,
            "layer_name": layer_name,
            "cell": (cell_x, cell_y),
            "mode": mode,
            "tile_id": tile_id,
            "source": clone_asset_reference(asset_ref),
            "texture_path": texture_path,
            "source_rect": snapshot_source_rect,
            "resolution": resolution,
            "cell_rect": cell_rect,
            "cell_corners": cell_corners,
            "preview_tiles": preview_tiles,
            "flood_bounds": tuple(self._tilemap_authoring.flood_effective_bounds) if self._tilemap_authoring.flood_effective_bounds is not None else None,
            "flood_preview_count": int(self._tilemap_authoring.flood_preview_count),
            "flood_truncated": bool(self._tilemap_authoring.flood_truncated),
            "rotation": float(getattr(transform, "rotation", 0.0)),
            "scale": {
                "x": float(getattr(transform, "scale_x", 1.0)),
                "y": float(getattr(transform, "scale_y", 1.0)),
            },
            "editable": status == "ok",
            "status": status,
            "status_label": self._tilemap_preview_status_label(status),
        }

    def _begin_tilemap_stroke(self, label: str | None = None) -> bool:
        if self._scene_manager is None or self._tilemap_authoring.stroke_active:
            return self._tilemap_authoring.stroke_active
        transaction_label = label or ("Tilemap Erase Stroke" if self._tilemap_effective_mode() == "erase" else "Tilemap Paint Stroke")
        if not self._scene_manager.begin_transaction(label=transaction_label):
            return False
        self._tilemap_authoring.stroke_active = True
        self._tilemap_authoring.stroke_cells.clear()
        return True

    def _finish_tilemap_stroke(self, *, commit: bool) -> None:
        if not self._tilemap_authoring.stroke_active or self._scene_manager is None:
            self._tilemap_authoring.stroke_active = False
            self._tilemap_authoring.stroke_cells.clear()
            return
        if commit:
            self._scene_manager.commit_transaction()
        else:
            self._scene_manager.rollback_transaction()
        self._tilemap_authoring.stroke_active = False
        self._tilemap_authoring.stroke_cells.clear()

    def _apply_tilemap_brush(self, world: "World", entity_name: str, cell: tuple[int, int]) -> bool:
        if cell in self._tilemap_authoring.stroke_cells:
            return False
        preview = self._build_tilemap_preview_snapshot(world, entity_name, cell)
        if preview is None or not bool(preview.get("editable")):
            return False
        payload = self._current_component_payload(world, entity_name, "Tilemap")
        if payload is None:
            return False
        layer = self._ensure_tilemap_layer_payload(payload, self._tilemap_authoring.layer_name)
        tile_x, tile_y = int(cell[0]), int(cell[1])
        existing = self._find_serialized_tile_entry(layer, tile_x, tile_y)
        effective_mode = self._tilemap_effective_mode()
        if effective_mode == "erase":
            if existing is None:
                self._tilemap_authoring.stroke_cells.add(cell)
                return False
            self._remove_serialized_tile_entry(layer, tile_x, tile_y)
        elif effective_mode == "stamp" and self._tilemap_authoring.stamp_tiles:
            for stamp_tile in self._tilemap_authoring.stamp_tiles:
                offset_x = int(stamp_tile.get("offset_x", 0))
                offset_y = int(stamp_tile.get("offset_y", 0))
                self._upsert_serialized_tile_entry(
                    layer,
                    tile_x + offset_x,
                    tile_y + offset_y,
                    str(stamp_tile.get("tile_id", "")),
                    stamp_tile.get("source", self._tilemap_authoring.source),
                )
        else:
            tile_id = str(self._tilemap_authoring.tile_id or "").strip()
            if not tile_id:
                return False
            self._upsert_serialized_tile_entry(layer, tile_x, tile_y, tile_id, self._tilemap_authoring.source)
        success = self.replace_component_payload(world, entity_name, "Tilemap", payload)
        if success:
            self._tilemap_authoring.stroke_cells.add(cell)
        return success

    def _upsert_serialized_tile_entry(self, layer: Dict[str, Any], x: int, y: int, tile_id: str, source: Any) -> None:
        existing = self._find_serialized_tile_entry(layer, x, y)
        tile_payload = {
            "x": int(x),
            "y": int(y),
            "tile_id": str(tile_id),
            "source": clone_asset_reference(source),
            "flags": [],
            "tags": [],
            "custom": {},
            "animated": False,
            "animation_id": "",
            "terrain_type": "",
        }
        if existing is None:
            layer.setdefault("tiles", []).append(tile_payload)
        else:
            existing.clear()
            existing.update(tile_payload)

    def _remove_serialized_tile_entry(self, layer: Dict[str, Any], x: int, y: int) -> None:
        layer["tiles"] = [
            tile
            for tile in layer.get("tiles", [])
            if not (isinstance(tile, dict) and int(tile.get("x", 0)) == int(x) and int(tile.get("y", 0)) == int(y))
        ]

    def _pick_tilemap_tile(self, world: "World", entity_name: str, cell: tuple[int, int]) -> bool:
        payload = self._current_component_payload(world, entity_name, "Tilemap")
        if payload is None:
            return False
        layer = self._find_tilemap_layer_payload(payload, self._tilemap_authoring.layer_name)
        if layer is None or bool(layer.get("locked", False)) or not bool(layer.get("visible", True)):
            return False
        tile = self._find_serialized_tile_entry(layer, int(cell[0]), int(cell[1]))
        if tile is None:
            return False
        self._tilemap_authoring.tile_id = str(tile.get("tile_id", ""))
        picked_source = normalize_asset_reference(tile.get("source"))
        self._tilemap_authoring.source = picked_source if (picked_source.get("guid") or picked_source.get("path")) else self._resolve_tilemap_palette_source(payload, self._tilemap_authoring.layer_name)
        self._tilemap_authoring.mode = "paint"
        self._tilemap_authoring.stamp_tiles = [
            {
                "offset_x": 0,
                "offset_y": 0,
                "tile_id": self._tilemap_authoring.tile_id,
                "source": clone_asset_reference(self._tilemap_authoring.source),
            }
        ]
        return True

    def _set_tilemap_stamp_from_scene(self, world: "World", entity_name: str, start: tuple[int, int], end: tuple[int, int]) -> bool:
        payload = self._current_component_payload(world, entity_name, "Tilemap")
        if payload is None:
            return False
        layer = self._find_tilemap_layer_payload(payload, self._tilemap_authoring.layer_name)
        if layer is None or bool(layer.get("locked", False)) or not bool(layer.get("visible", True)):
            return False
        min_x, max_x = sorted((int(start[0]), int(end[0])))
        min_y, max_y = sorted((int(start[1]), int(end[1])))
        stamp_tiles: list[dict[str, Any]] = []
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                tile = self._find_serialized_tile_entry(layer, x, y)
                if tile is None:
                    continue
                source = normalize_asset_reference(tile.get("source"))
                if not (source.get("guid") or source.get("path")):
                    source = self._resolve_tilemap_palette_source(payload, self._tilemap_authoring.layer_name)
                stamp_tiles.append(
                    {
                        "offset_x": x - min_x,
                        "offset_y": y - min_y,
                        "tile_id": str(tile.get("tile_id", "")),
                        "source": clone_asset_reference(source),
                    }
                )
        if not stamp_tiles:
            return False
        self._tilemap_authoring.stamp_tiles = stamp_tiles
        self._tilemap_authoring.tile_id = str(stamp_tiles[0].get("tile_id", ""))
        self._tilemap_authoring.source = clone_asset_reference(stamp_tiles[0].get("source", {}))
        self._tilemap_authoring.mode = "stamp" if len(stamp_tiles) > 1 else "paint"
        return True

    def _apply_tilemap_box_fill(self, world: "World", entity_name: str, cell: tuple[int, int]) -> bool:
        anchor = self._tilemap_authoring.box_fill_anchor
        if anchor is None:
            return False
        payload = self._current_component_payload(world, entity_name, "Tilemap")
        if payload is None:
            return False
        layer = self._ensure_tilemap_layer_payload(payload, self._tilemap_authoring.layer_name)
        min_x, max_x = sorted((int(anchor[0]), int(cell[0])))
        min_y, max_y = sorted((int(anchor[1]), int(cell[1])))
        tile_id = str(self._tilemap_authoring.tile_id or "").strip()
        if not tile_id:
            return False
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                preview = self._build_tilemap_preview_snapshot(world, entity_name, (x, y))
                if preview is not None and bool(preview.get("editable")):
                    self._upsert_serialized_tile_entry(layer, x, y, tile_id, self._tilemap_authoring.source)
        return self.replace_component_payload(world, entity_name, "Tilemap", payload)

    def _apply_tilemap_flood_fill(self, world: "World", entity_name: str, cell: tuple[int, int]) -> bool:
        payload = self._current_component_payload(world, entity_name, "Tilemap")
        if payload is None:
            return False
        preview = self._build_tilemap_preview_snapshot(world, entity_name, cell)
        if preview is None or not bool(preview.get("editable")):
            return False
        layer = self._ensure_tilemap_layer_payload(payload, self._tilemap_authoring.layer_name)
        tile_id = str(self._tilemap_authoring.tile_id or "").strip()
        if not tile_id:
            return False
        fill_cells, bounds, truncated = self._compute_tilemap_flood_fill_cells(layer, cell)
        self._tilemap_authoring.flood_effective_bounds = bounds
        self._tilemap_authoring.flood_preview_count = len(fill_cells)
        self._tilemap_authoring.flood_truncated = truncated
        for x, y in fill_cells:
            self._upsert_serialized_tile_entry(layer, x, y, tile_id, self._tilemap_authoring.source)
        return self.replace_component_payload(world, entity_name, "Tilemap", payload)

    def _compute_tilemap_flood_fill_cells(
        self,
        layer: Dict[str, Any],
        cell: tuple[int, int],
    ) -> tuple[list[tuple[int, int]], tuple[int, int, int, int], bool]:
        start_x, start_y = int(cell[0]), int(cell[1])
        min_x, min_y, max_x, max_y = self._resolve_tilemap_flood_bounds(layer, (start_x, start_y))
        target_identity = self._serialized_tile_identity(self._find_serialized_tile_entry(layer, start_x, start_y))
        max_cells = max(1, min(4096, int(self._tilemap_authoring.flood_max_cells)))
        visited: set[tuple[int, int]] = set()
        queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
        fill_cells: list[tuple[int, int]] = []
        truncated = False
        while queue:
            x, y = queue.popleft()
            if (x, y) in visited or x < min_x or x > max_x or y < min_y or y > max_y:
                continue
            visited.add((x, y))
            current_identity = self._serialized_tile_identity(self._find_serialized_tile_entry(layer, x, y))
            if current_identity != target_identity:
                continue
            if len(fill_cells) >= max_cells:
                truncated = True
                continue
            fill_cells.append((x, y))
            queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
        return fill_cells, (min_x, min_y, max_x, max_y), truncated

    def _resolve_tilemap_flood_bounds(self, layer: Dict[str, Any], cell: tuple[int, int]) -> tuple[int, int, int, int]:
        start_x, start_y = int(cell[0]), int(cell[1])
        if str(self._tilemap_authoring.flood_bounds_mode or "auto").strip().lower() == "manual":
            return (
                min(int(self._tilemap_authoring.flood_min_x), int(self._tilemap_authoring.flood_max_x)),
                min(int(self._tilemap_authoring.flood_min_y), int(self._tilemap_authoring.flood_max_y)),
                max(int(self._tilemap_authoring.flood_min_x), int(self._tilemap_authoring.flood_max_x)),
                max(int(self._tilemap_authoring.flood_min_y), int(self._tilemap_authoring.flood_max_y)),
            )
        existing_tiles = [tile for tile in layer.get("tiles", []) if isinstance(tile, dict)]
        if existing_tiles:
            margin = max(0, int(self._tilemap_authoring.flood_margin))
            xs = [int(tile.get("x", 0)) for tile in existing_tiles] + [start_x]
            ys = [int(tile.get("y", 0)) for tile in existing_tiles] + [start_y]
            return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)
        return (start_x - 8, start_y - 8, start_x + 7, start_y + 7)

    def _serialized_tile_identity(self, tile: Optional[Dict[str, Any]]) -> tuple[str, str, str] | None:
        if tile is None:
            return None
        source = normalize_asset_reference(tile.get("source"))
        return (str(tile.get("tile_id", "")), str(source.get("guid", "")), str(source.get("path", "")))

    def _get_component_origin(self, entity: Optional[Entity], component_name: str, component: Optional[Component] = None) -> str:
        if entity is not None:
            metadata = entity.get_component_metadata_by_name(component_name)
            origin = str(metadata.get("origin", "") or "").strip().lower()
            if origin:
                return origin
            if component is not None:
                metadata = entity.get_component_metadata(type(component))
                origin = str(metadata.get("origin", "") or "").strip().lower()
                if origin:
                    return origin
        return self.registry.get_origin(component_name)

    def _origin_color(self, origin: str) -> rl.Color:
        normalized = str(origin or "").strip().lower()
        if normalized == "ai_custom":
            return self.ORIGIN_AI_COLOR
        if normalized == "native":
            return self.ORIGIN_NATIVE_COLOR
        return self.ORIGIN_UNKNOWN_COLOR

    def _origin_badge(self, origin: str) -> str:
        normalized = str(origin or "").strip().lower()
        if normalized == "ai_custom":
            return "AI"
        if normalized == "native":
            return "CORE"
        return "UNK"

    def _label_and_field_rect(self, label: str, x: int, y: int, width: int) -> Tuple[int, int, int]:
        row_height = self.LINE_HEIGHT
        padding = 5
        rl.gui_label(rl.Rectangle(x + padding, y, self.LABEL_WIDTH, row_height), label)
        field_x = x + self.LABEL_WIDTH + padding
        field_w = width - self.LABEL_WIDTH - (padding * 2)
        return field_x, field_w, row_height

    def _draw_text_row(
        self,
        label: str,
        value: str,
        prop_id: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
        on_commit: Optional[CommitCallback] = None,
    ) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        self._draw_text_field(value, prop_id, field_x, y, field_w, row_height, is_edit, world, on_commit=on_commit)
        return y + row_height

    def _draw_int_row(
        self,
        label: str,
        value: int,
        prop_id: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
        on_commit: Optional[CommitCallback] = None,
    ) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        self._draw_int_field(value, prop_id, field_x, y, field_w, row_height, is_edit, world, on_commit=on_commit)
        return y + row_height

    def _draw_float_row(
        self,
        label: str,
        value: float,
        prop_id: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
        on_commit: Optional[CommitCallback] = None,
    ) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        self._draw_float_field(value, prop_id, field_x, y, field_w, row_height, is_edit, world, on_commit=on_commit)
        return y + row_height

    def _draw_bool_row(
        self,
        label: str,
        value: bool,
        prop_id: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
        on_toggle: Optional[CommitCallback] = None,
    ) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        self._draw_bool_field(value, prop_id, field_x, y, field_w, row_height, is_edit, world, on_toggle=on_toggle)
        return y + row_height

    def _draw_readonly_row(self, label: str, value: str, x: int, y: int, width: int) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        self._draw_readonly_field(value, field_x, y + 1, field_w, row_height - 2)
        return y + row_height

    def _draw_action_row(
        self,
        label: str,
        button_text: str,
        x: int,
        y: int,
        width: int,
        enabled: bool,
        on_click: Callable[[], None],
    ) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        button_rect = rl.Rectangle(field_x, y + 1, field_w, row_height - 2)
        button_label = button_text if enabled else f"{button_text} (missing asset)"
        if rl.gui_button(button_rect, button_label) and enabled:
            on_click()
        return y + row_height

    def _draw_section_title(self, title: str, x: int, y: int, width: int) -> int:
        rect = rl.Rectangle(x + 4, y, width - 8, self.LINE_HEIGHT)
        rl.draw_rectangle_rec(rect, rl.Color(44, 44, 44, 255))
        rl.draw_text(title, int(x + 10), int(y + 4), 10, rl.Color(200, 200, 200, 255))
        return y + self.LINE_HEIGHT

    def _draw_section_title_with_tint(self, title: str, x: int, y: int, width: int, color: rl.Color) -> int:
        rect = rl.Rectangle(x + 4, y, width - 8, self.LINE_HEIGHT)
        rl.draw_rectangle_rec(rect, color)
        rl.draw_text(title, int(x + 10), int(y + 4), 10, rl.Color(230, 230, 230, 255))
        return y + self.LINE_HEIGHT

    def _draw_message_row(self, severity: str, message: str, x: int, y: int, width: int) -> int:
        level = str(severity or "").strip().lower()
        color = rl.Color(140, 120, 40, 255)
        prefix = "Warning"
        if level == "error":
            color = rl.Color(128, 56, 56, 255)
            prefix = "Error"
        rect = rl.Rectangle(x + 5, y + 1, width - 10, self.LINE_HEIGHT - 2)
        rl.draw_rectangle_rec(rect, color)
        rl.draw_text(f"{prefix}: {message}", int(rect.x + 6), int(rect.y + 4), 10, rl.Color(240, 240, 240, 255))
        return y + self.LINE_HEIGHT

    def _draw_choice_row(
        self,
        label: str,
        options: List[tuple[str, str]],
        current_key: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        on_select: Optional[Callable[[str], bool]] = None,
    ) -> int:
        field_x, field_w, row_height = self._label_and_field_rect(label, x, y, width)
        option_keys = [key for key, _ in options]
        current_index = option_keys.index(current_key) if current_key in option_keys else 0
        left_rect = rl.Rectangle(field_x, y + 1, 22, row_height - 2)
        value_rect = rl.Rectangle(field_x + 24, y + 1, field_w - 48, row_height - 2)
        right_rect = rl.Rectangle(field_x + field_w - 22, y + 1, 22, row_height - 2)
        current_label = options[current_index][1] if options else ""
        rl.draw_rectangle_rec(value_rect, rl.Color(42, 42, 42, 255))
        rl.draw_text(current_label, int(value_rect.x + 5), int(value_rect.y + 4), 10, rl.Color(200, 200, 200, 255))
        self._register_cursor_rect(left_rect)
        self._register_cursor_rect(value_rect)
        self._register_cursor_rect(right_rect)
        if not is_edit or not options:
            rl.draw_rectangle_lines_ex(value_rect, 1, rl.Color(80, 80, 80, 255))
            return y + row_height

        if rl.gui_button(left_rect, "<") and current_index > 0 and on_select is not None:
            on_select(options[current_index - 1][0])
        if rl.gui_button(right_rect, ">") and current_index < len(options) - 1 and on_select is not None:
            on_select(options[current_index + 1][0])
        return y + row_height

    def _draw_tilemap_palette_grid(
        self,
        entries: List[Dict[str, Any]],
        selected_tile: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        *,
        on_select: Optional[Callable[[str], bool]] = None,
    ) -> int:
        current_y = self._draw_section_title("Palette", x, y, width)
        frame_rect = rl.Rectangle(x + 5, current_y + 2, width - 10, 116)
        content_rect = rl.Rectangle(frame_rect.x + 4, frame_rect.y + 4, frame_rect.width - 8, frame_rect.height - 8)
        rl.draw_rectangle_rec(frame_rect, rl.Color(34, 34, 34, 255))
        rl.draw_rectangle_lines_ex(frame_rect, 1, rl.Color(60, 60, 60, 255))
        mouse_pos = rl.get_mouse_position()
        if rl.check_collision_point_rec(mouse_pos, frame_rect):
            wheel = rl.get_mouse_wheel_move()
            if abs(float(wheel)) > 0.01:
                self._tilemap_authoring.palette_scroll = max(0.0, self._tilemap_authoring.palette_scroll - (float(wheel) * 28.0))

        tile_size = 34.0
        tile_gap = 6.0
        cols = max(1, int((content_rect.width + tile_gap) // (tile_size + tile_gap)))
        self._tilemap_authoring.palette_selected_index = self._tilemap_current_palette_index(entries)
        rows = max(1, math.ceil(len(entries) / cols))
        content_height = rows * (tile_size + tile_gap)
        max_scroll = max(0.0, content_height - content_rect.height)
        self._tilemap_authoring.palette_scroll = min(self._tilemap_authoring.palette_scroll, max_scroll)

        with editor_scissor(content_rect):
            for index, entry in enumerate(entries):
                col = index % cols
                row = index // cols
                tile_rect = rl.Rectangle(
                    content_rect.x + col * (tile_size + tile_gap),
                    content_rect.y + row * (tile_size + tile_gap) - self._tilemap_authoring.palette_scroll,
                    tile_size,
                    tile_size,
                )
                if tile_rect.y + tile_rect.height < content_rect.y or tile_rect.y > content_rect.y + content_rect.height:
                    continue
                entry_tile_id = str(entry.get("tile_id", ""))
                selected = entry_tile_id == selected_tile
                hovered = rl.check_collision_point_rec(mouse_pos, tile_rect)
                border_color = rl.Color(80, 180, 255, 255) if selected else rl.Color(88, 88, 88, 255)
                if hovered and not selected:
                    border_color = rl.Color(170, 170, 170, 255)
                rl.draw_rectangle_rec(tile_rect, rl.Color(28, 28, 28, 255))
                texture = self._load_tilemap_palette_texture(str(entry.get("texture_path", "")))
                source_rect = entry.get("source_rect")
                if texture is not None and getattr(texture, "id", 0) != 0 and isinstance(source_rect, dict):
                    inset = 3.0
                    rl.draw_texture_pro(
                        texture,
                        rl.Rectangle(
                            float(source_rect.get("x", 0)),
                            float(source_rect.get("y", 0)),
                            float(source_rect.get("width", 1)),
                            float(source_rect.get("height", 1)),
                        ),
                        rl.Rectangle(tile_rect.x + inset, tile_rect.y + inset, tile_rect.width - (inset * 2), tile_rect.height - (inset * 2)),
                        rl.Vector2(0, 0),
                        0.0,
                        rl.WHITE,
                    )
                else:
                    rl.draw_text(str(entry.get("label", entry_tile_id))[:6], int(tile_rect.x + 4), int(tile_rect.y + 11), 10, rl.Color(210, 210, 210, 255))
                rl.draw_rectangle_lines_ex(tile_rect, 2, border_color)
                self._register_cursor_rect(tile_rect)
                if is_edit and hovered and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT) and on_select is not None:
                    self._tilemap_authoring.palette_focused = True
                    self._tilemap_authoring.palette_selected_index = index
                    on_select(entry_tile_id)
        if max_scroll > 0.0:
            ratio = content_rect.height / max(content_rect.height, content_height)
            thumb_height = max(12.0, content_rect.height * ratio)
            thumb_range = max(0.0, content_rect.height - thumb_height)
            thumb_offset = 0.0 if max_scroll <= 0.0 else (self._tilemap_authoring.palette_scroll / max_scroll) * thumb_range
            scrollbar_rect = rl.Rectangle(frame_rect.x + frame_rect.width - 5, content_rect.y + thumb_offset, 3, thumb_height)
            rl.draw_rectangle_rec(scrollbar_rect, rl.Color(92, 92, 92, 255))
        return int(frame_rect.y + frame_rect.height + 6)

    def _load_tilemap_palette_texture(self, texture_path: str) -> Any:
        normalized = str(texture_path or "").strip()
        if not normalized:
            return None
        try:
            texture = self._tilemap_texture_manager.load(normalized, cache_key=normalized)
        except Exception:
            return None
        return texture if getattr(texture, "id", 0) != 0 else None

    def _draw_scene_transition_block(
        self,
        entity: Entity,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
    ) -> int:
        validation = self._get_scene_transition_validation_messages(world, entity.name)
        has_errors = any(level == "error" for level, _ in validation)
        header_color = rl.Color(68, 56, 56, 255) if has_errors else rl.Color(44, 44, 44, 255)
        current_y = self._draw_section_title_with_tint("Scene Transition", x, y, width, header_color)
        trigger_options = self._get_scene_transition_trigger_options(entity)
        current_trigger = self._detect_scene_transition_preset(entity)
        current_y = self._draw_choice_row(
            "Trigger",
            trigger_options,
            current_trigger,
            x,
            current_y,
            width,
            is_edit,
            on_select=lambda value: self._set_scene_transition_preset(world, entity.name, value),
        )

        current_action = self._get_scene_transition_action_payload(world, entity.name)
        current_target_scene = str(current_action.get("target_scene_path", "") or "") if current_action is not None else ""
        scene_options = self._get_scene_transition_scene_options(current_target_scene)
        selected_scene_key = current_target_scene if any(key == current_target_scene for key, _ in scene_options) else scene_options[0][0]
        current_y = self._draw_choice_row(
            "Target Scene",
            scene_options,
            selected_scene_key,
            x,
            current_y,
            width,
            is_edit,
            on_select=lambda value: self._set_scene_transition_target_scene(world, entity.name, value),
        )

        current_target_entry = str(current_action.get("target_entry_id", "") or "") if current_action is not None else ""
        spawn_options = self._get_scene_transition_spawn_options(world, entity.name)
        selected_spawn_key = current_target_entry if any(key == current_target_entry for key, _ in spawn_options) else spawn_options[0][0]
        current_y = self._draw_choice_row(
            "Target Spawn",
            spawn_options,
            selected_spawn_key,
            x,
            current_y,
            width,
            is_edit,
            on_select=lambda value: self._set_scene_transition_target_spawn(world, entity.name, value),
        )

        for severity, message in validation:
            current_y = self._draw_message_row(severity, message, x, current_y, width)
        return current_y

    def _draw_component_field(
        self,
        label: str,
        value: Any,
        entity_id: int,
        component_name: str,
        property_name: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
    ) -> int:
        prop_id = f"{entity_id}:{component_name}:{property_name}"
        return self._draw_property(label, value, prop_id, x, y, width, is_edit, world)

    def _get_scene_transition_trigger_options(self, entity: Entity) -> List[tuple[str, str]]:
        options: List[tuple[str, str]] = [("none", "None")]
        current = self._detect_scene_transition_preset(entity)
        if entity.get_component(UIButton) is not None or current == "ui_button":
            options.append(("ui_button", "UI Button"))
        options.extend(
            [
                ("interact_near", "Interact Near"),
                ("trigger_enter", "Trigger Enter"),
                ("collision", "Collision"),
                ("player_death", "Player Death"),
            ]
        )
        return options

    def _detect_scene_transition_preset(self, entity: Entity) -> str:
        button = entity.get_component(UIButton)
        if button is not None:
            action = dict(button.on_click or {})
            if str(action.get("type", "") or "").strip() == "run_scene_transition":
                return "ui_button"

        interact = entity.get_component(SceneTransitionOnInteract)
        if interact is not None and getattr(interact, "enabled", True):
            return "interact_near"

        contact = entity.get_component(SceneTransitionOnContact)
        if contact is not None and getattr(contact, "enabled", True):
            mode = str(getattr(contact, "mode", "") or "").strip()
            if mode == "collision":
                return "collision"
            return "trigger_enter"

        death = entity.get_component(SceneTransitionOnPlayerDeath)
        if death is not None and getattr(death, "enabled", True):
            return "player_death"
        return "none"

    def _set_scene_transition_preset(self, world: "World", entity_name: str, preset: str) -> bool:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        normalized = str(preset or "none").strip() or "none"
        self._remove_scene_transition_trigger_components(world, entity_name)

        if normalized == "none":
            self._reset_ui_button_scene_transition(world, entity_name)
            return True

        if not self._ensure_scene_transition_action(world, entity_name):
            return False

        if normalized == "ui_button":
            if entity.get_component(UIButton) is None:
                return False
            return self._set_ui_button_scene_transition(world, entity_name)

        self._reset_ui_button_scene_transition(world, entity_name)
        if normalized == "interact_near":
            return self._upsert_component_payload(
                world,
                entity_name,
                "SceneTransitionOnInteract",
                {"enabled": True, "require_player": True},
            )
        if normalized == "trigger_enter":
            return self._upsert_component_payload(
                world,
                entity_name,
                "SceneTransitionOnContact",
                {"enabled": True, "mode": "trigger_enter", "require_player": True},
            )
        if normalized == "collision":
            return self._upsert_component_payload(
                world,
                entity_name,
                "SceneTransitionOnContact",
                {"enabled": True, "mode": "collision", "require_player": True},
            )
        if normalized == "player_death":
            return self._upsert_component_payload(
                world,
                entity_name,
                "SceneTransitionOnPlayerDeath",
                {"enabled": True},
            )
        return False

    def _set_scene_transition_target_scene(self, world: "World", entity_name: str, scene_path: str) -> bool:
        normalized_path = str(scene_path or "").strip()
        if not self._ensure_scene_transition_action(world, entity_name):
            return False
        current_entry_id = ""
        current_action = self._get_scene_transition_action_payload(world, entity_name)
        if current_action is not None:
            current_entry_id = str(current_action.get("target_entry_id", "") or "").strip()
        valid_entry_ids = {option["entry_id"] for option in self._list_scene_entry_points_for_target(normalized_path)}
        next_entry_id = current_entry_id if current_entry_id in valid_entry_ids else ""
        return self.update_component_payload(
            world,
            entity_name,
            "SceneTransitionAction",
            lambda payload, normalized_path=normalized_path, next_entry_id=next_entry_id: payload.update(
                {
                    "target_scene_path": normalized_path,
                    "target_entry_id": next_entry_id,
                }
            ),
        )

    def _set_scene_transition_target_spawn(self, world: "World", entity_name: str, entry_id: str) -> bool:
        normalized_entry_id = str(entry_id or "").strip()
        if not self._ensure_scene_transition_action(world, entity_name):
            return False
        return self.update_component_payload(
            world,
            entity_name,
            "SceneTransitionAction",
            lambda payload, normalized_entry_id=normalized_entry_id: payload.update({"target_entry_id": normalized_entry_id}),
        )

    def _get_scene_transition_action_payload(self, world: "World", entity_name: str) -> Optional[Dict[str, Any]]:
        return self._current_component_payload(world, entity_name, "SceneTransitionAction")

    def _get_scene_transition_scene_options(self, current_target_scene: str = "") -> List[tuple[str, str]]:
        options: List[tuple[str, str]] = [("", "Select scene")]
        for scene_path in self._list_available_scene_paths():
            options.append((scene_path, scene_path))
        normalized_current = str(current_target_scene or "").strip()
        if normalized_current and all(key != normalized_current for key, _ in options):
            options.append((normalized_current, f"Invalid: {normalized_current}"))
        return options

    def _get_scene_transition_spawn_options(self, world: "World", entity_name: str) -> List[tuple[str, str]]:
        action = self._get_scene_transition_action_payload(world, entity_name)
        target_scene_path = str(action.get("target_scene_path", "") or "").strip() if action is not None else ""
        options: List[tuple[str, str]] = [("", "No spawn")]
        for item in self._list_scene_entry_points_for_target(target_scene_path):
            label = item["label"] or item["entry_id"]
            options.append((item["entry_id"], f"{label} ({item['entity_name']})"))
        current_entry = str(action.get("target_entry_id", "") or "").strip() if action is not None else ""
        if current_entry and all(key != current_entry for key, _ in options):
            options.append((current_entry, f"Invalid: {current_entry}"))
        return options

    def _list_scene_entry_points_for_target(self, target_scene_path: str) -> List[Dict[str, str]]:
        normalized_target = str(target_scene_path or "").strip()
        if not normalized_target:
            return []
        source_path = self._current_scene_source_path()
        cache_key = (str(source_path or ""), normalized_target)
        now = time.monotonic()
        if self._scene_entry_point_cache_key == cache_key and (now - self._scene_entry_point_cache_time) < 1.0:
            return copy.deepcopy(self._scene_entry_point_cache)
        results = list_scene_entry_points(source_path, normalized_target)
        self._scene_entry_point_cache = copy.deepcopy(results)
        self._scene_entry_point_cache_key = cache_key
        self._scene_entry_point_cache_time = now
        return copy.deepcopy(results)

    def _get_scene_transition_validation_messages(self, world: "World", entity_name: str) -> List[tuple[str, str]]:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return []
        preset = self._detect_scene_transition_preset(entity)
        action = self._get_scene_transition_action_payload(world, entity_name)
        target_scene_path = str(action.get("target_scene_path", "") or "").strip() if action is not None else ""
        messages: List[tuple[str, str]] = []

        collider = entity.get_component(Collider)
        if preset == "ui_button" and entity.get_component(UIButton) is None:
            messages.append(("warning", "UI Button trigger requires a UIButton component"))
        if preset == "interact_near":
            if collider is None:
                messages.append(("warning", "Interact Near requires a Collider component"))
            elif not collider.is_trigger:
                messages.append(("warning", "Interact Near requires Collider.is_trigger = true"))
        if preset == "trigger_enter":
            if collider is None:
                messages.append(("warning", "Trigger Enter requires a Collider component"))
            elif not collider.is_trigger:
                messages.append(("warning", "Trigger Enter requires Collider.is_trigger = true"))
        if preset == "collision" and collider is None:
            messages.append(("warning", "Collision requires a Collider component"))
        if preset == "player_death" and not self._is_player_like_entity(entity):
            messages.append(("warning", "Player Death is usually expected on a player-like entity"))
        if preset != "none" and not target_scene_path:
            messages.append(("error", "Target scene is required"))

        if preset != "none" and self._scene_manager is not None and self._scene_manager.current_scene is not None:
            scene_payload = self._scene_manager.current_scene.to_dict()
            scene_errors = validate_scene_transition_references(
                scene_payload,
                scene_path=self._current_scene_source_path(),
            )
            entity_index = self._scene_entity_index(entity_name)
            for error in scene_errors:
                if entity_index is not None and f"$.entities[{entity_index}]" not in error:
                    continue
                messages.append(("error", error.split(": ", 1)[-1]))

        deduped: List[tuple[str, str]] = []
        seen: Set[tuple[str, str]] = set()
        for item in messages:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    def _scene_entity_index(self, entity_name: str) -> Optional[int]:
        if self._scene_manager is None or self._scene_manager.current_scene is None:
            return None
        entities = self._scene_manager.current_scene.to_dict().get("entities", [])
        if not isinstance(entities, list):
            return None
        for index, entity in enumerate(entities):
            if isinstance(entity, dict) and str(entity.get("name", "") or "") == entity_name:
                return index
        return None

    def _current_scene_source_path(self) -> Optional[str]:
        if self._scene_manager is None or self._scene_manager.current_scene is None:
            return None
        source_path = getattr(self._scene_manager.current_scene, "source_path", None)
        return str(source_path) if source_path else None

    def _default_scene_transition_target_path(self) -> str:
        source_path = self._current_scene_source_path()
        if source_path:
            try:
                source = Path(source_path).resolve()
                project_root = source.parent.parent
                return source.relative_to(project_root).as_posix()
            except (ValueError, OSError):
                pass
        available_scenes = self._list_available_scene_paths()
        return available_scenes[0] if available_scenes else ""

    def _is_player_like_entity(self, entity: Entity) -> bool:
        if entity.get_component(PlayerController2D) is not None:
            return True
        return str(entity.tag or "").strip().lower() in {"player", "hero"}

    def _ensure_scene_transition_action(self, world: "World", entity_name: str) -> bool:
        if self._current_component_payload(world, entity_name, "SceneTransitionAction") is not None:
            return True
        return self._upsert_component_payload(
            world,
            entity_name,
            "SceneTransitionAction",
            {
                "enabled": True,
                "target_scene_path": self._default_scene_transition_target_path(),
                "target_entry_id": "",
            },
        )

    def _set_ui_button_scene_transition(self, world: "World", entity_name: str) -> bool:
        action_payload = self._current_component_payload(world, entity_name, "UIButton")
        if action_payload is None:
            return False
        action_payload["on_click"] = {"type": "run_scene_transition"}
        return self.replace_component_payload(world, entity_name, "UIButton", action_payload)

    def _reset_ui_button_scene_transition(self, world: "World", entity_name: str) -> bool:
        action_payload = self._current_component_payload(world, entity_name, "UIButton")
        if action_payload is None:
            return False
        on_click = dict(action_payload.get("on_click", {}) or {})
        if str(on_click.get("type", "") or "").strip() != "run_scene_transition":
            return False
        action_payload["on_click"] = {"type": "emit_event", "name": "ui.button_clicked"}
        return self.replace_component_payload(world, entity_name, "UIButton", action_payload)

    def _remove_scene_transition_trigger_components(self, world: "World", entity_name: str) -> None:
        for component_name in ("SceneTransitionOnContact", "SceneTransitionOnInteract", "SceneTransitionOnPlayerDeath"):
            self._remove_component_if_present(world, entity_name, component_name)

    def _remove_component_if_present(self, world: "World", entity_name: str, component_name: str) -> bool:
        payload = self._current_component_payload(world, entity_name, component_name)
        if payload is None:
            return False
        if self._scene_manager is not None:
            return self._scene_manager.remove_component_from_entity(entity_name, component_name)
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return False
        component = self._find_component(entity, component_name)
        if component is None:
            return False
        entity.remove_component(type(component))
        return True

    def _get_scene_link_payload(self, world: "World", entity_name: str) -> Optional[Dict[str, Any]]:
        return self._current_component_payload(world, entity_name, "SceneLink")

    def _ensure_scene_link(self, world: "World", entity_name: str) -> bool:
        if self._get_scene_link_payload(world, entity_name) is not None:
            return True
        return self._upsert_component_payload(
            world,
            entity_name,
            "SceneLink",
            {
                "enabled": True,
                "target_path": "",
                "flow_key": "",
                "preview_label": "",
                "link_mode": "",
                "target_entry_id": "",
            },
        )

    def _get_scene_link_mode_options(self, world: "World", entity_name: str) -> List[tuple[str, str]]:
        entity = world.get_entity_by_name(entity_name)
        options: List[tuple[str, str]] = [("", "Select trigger")]
        if entity is None:
            return options
        if entity.get_component(UIButton) is not None:
            options.append(("ui_button", "UI Button"))
        if entity.get_component(Collider) is not None:
            options.append(("interact_near", "Interact Near"))
            options.append(("trigger_enter", "Touch / Trigger"))
            options.append(("collision", "Collision"))
        return options

    def _set_scene_link_mode(self, world: "World", entity_name: str, mode: str) -> bool:
        normalized_mode = str(mode or "").strip()
        if not self._ensure_scene_link(world, entity_name):
            return False
        updated = self.update_component_payload(
            world,
            entity_name,
            "SceneLink",
            lambda payload, normalized_mode=normalized_mode: payload.update({"link_mode": normalized_mode}),
        )
        if not updated:
            return False
        return self._sync_scene_link_runtime(world, entity_name)

    def _set_scene_link_target_scene(self, world: "World", entity_name: str, scene_path: str) -> bool:
        normalized_path = str(scene_path or "").strip()
        if not self._ensure_scene_link(world, entity_name):
            return False
        current_link = self._get_scene_link_payload(world, entity_name) or {}
        current_entry_id = str(current_link.get("target_entry_id", "") or "").strip()
        valid_entry_ids = {item["entry_id"] for item in self._list_scene_entry_points_for_target(normalized_path)}
        next_entry_id = current_entry_id if current_entry_id in valid_entry_ids else ""
        updated = self.update_component_payload(
            world,
            entity_name,
            "SceneLink",
            lambda payload, normalized_path=normalized_path, next_entry_id=next_entry_id: payload.update(
                {"target_path": normalized_path, "target_entry_id": next_entry_id}
            ),
        )
        if not updated:
            return False
        return self._sync_scene_link_runtime(world, entity_name)

    def _set_scene_link_target_spawn(self, world: "World", entity_name: str, entry_id: str) -> bool:
        normalized_entry_id = str(entry_id or "").strip()
        if not self._ensure_scene_link(world, entity_name):
            return False
        updated = self.update_component_payload(
            world,
            entity_name,
            "SceneLink",
            lambda payload, normalized_entry_id=normalized_entry_id: payload.update({"target_entry_id": normalized_entry_id}),
        )
        if not updated:
            return False
        return self._sync_scene_link_runtime(world, entity_name)

    def _set_scene_link_target_entity(self, world: "World", entity_name: str, target_entity_name: str) -> bool:
        normalized_target = str(target_entity_name or "").strip()
        if not self._ensure_scene_link(world, entity_name):
            return False
        return self.update_component_payload(
            world,
            entity_name,
            "SceneLink",
            lambda payload, normalized_target=normalized_target: payload.update({"target_entity_name": normalized_target}),
        )

    def _get_scene_link_spawn_options(self, world: "World", entity_name: str) -> List[tuple[str, str]]:
        link = self._get_scene_link_payload(world, entity_name)
        target_scene_path = str(link.get("target_path", "") or "").strip() if link is not None else ""
        options: List[tuple[str, str]] = [("", "No spawn")]
        for item in self._list_scene_entry_points_for_target(target_scene_path):
            label = item["label"] or item["entry_id"]
            options.append((item["entry_id"], f"{label} ({item['entity_name']})"))
        current_entry = str(link.get("target_entry_id", "") or "").strip() if link is not None else ""
        if current_entry and all(key != current_entry for key, _ in options):
            options.append((current_entry, f"Invalid: {current_entry}"))
        return options

    def _get_scene_link_validation_messages(self, world: "World", entity_name: str) -> List[tuple[str, str]]:
        entity = world.get_entity_by_name(entity_name)
        if entity is None:
            return []
        link = self._get_scene_link_payload(world, entity_name)
        if link is None:
            return []
        link_mode = str(link.get("link_mode", "") or "").strip()
        target_path = str(link.get("target_path", "") or "").strip()
        messages: List[tuple[str, str]] = []
        collider = entity.get_component(Collider)
        if link_mode == "ui_button" and entity.get_component(UIButton) is None:
            messages.append(("warning", "UI Button mode requires a UIButton component"))
        if link_mode == "trigger_enter":
            if collider is None:
                messages.append(("warning", "Touch / Trigger requires a Collider component"))
            elif not collider.is_trigger:
                messages.append(("warning", "Touch / Trigger requires Collider.is_trigger = true"))
        if link_mode == "interact_near":
            if collider is None:
                messages.append(("warning", "Interact Near requires a Collider component"))
            elif not collider.is_trigger:
                messages.append(("warning", "Interact Near requires Collider.is_trigger = true"))
        if link_mode == "collision" and collider is None:
            messages.append(("warning", "Collision requires a Collider component"))
        if link_mode and not target_path:
            messages.append(("error", "Target scene is required"))
        target_entity_name = str(link.get("target_entity_name", "") or "").strip()
        if target_entity_name and self._scene_manager is not None:
            target_entity = self._scene_manager.find_entity_data_for_scene(target_path, target_entity_name)
            if target_entity is None:
                messages.append(("warning", f"Target object '{target_entity_name}' was not found in destination scene"))
        for severity, message in self._get_scene_transition_validation_messages(world, entity_name):
            if (severity, message) not in messages:
                messages.append((severity, message))
        return messages

    def _get_scene_link_connection_type(self, world: "World", entity_name: str) -> str:
        link = self._get_scene_link_payload(world, entity_name)
        if link is None or self._scene_manager is None:
            return "One-way"
        target_path = str(link.get("target_path", "") or "").strip()
        target_entity_name = str(link.get("target_entity_name", "") or "").strip()
        if not target_path or not target_entity_name:
            return "One-way"
        target_link = self._scene_manager.get_component_data_for_scene(target_path, target_entity_name, "SceneLink")
        if not isinstance(target_link, dict):
            return "One-way"
        current_scene = getattr(getattr(self._scene_manager, "current_scene", None), "source_path", "") or ""
        reciprocal_path = str(target_link.get("target_path", "") or "").strip()
        reciprocal_entity = str(target_link.get("target_entity_name", "") or "").strip()
        return "Two-way" if reciprocal_path == str(current_scene) and reciprocal_entity == entity_name else "One-way"

    def _sync_scene_link_runtime(self, world: "World", entity_name: str) -> bool:
        entity = world.get_entity_by_name(entity_name)
        link = self._get_scene_link_payload(world, entity_name)
        if entity is None or link is None:
            return False
        link_mode = str(link.get("link_mode", "") or "").strip()
        target_path = str(link.get("target_path", "") or "").strip()
        target_entry_id = str(link.get("target_entry_id", "") or "").strip()

        if not link_mode or not target_path:
            self._remove_scene_transition_trigger_components(world, entity_name)
            self._reset_ui_button_scene_transition(world, entity_name)
            self._remove_component_if_present(world, entity_name, "SceneTransitionAction")
            return True

        if link_mode == "ui_button" and entity.get_component(UIButton) is None:
            return False
        if link_mode in {"interact_near", "trigger_enter"}:
            collider = entity.get_component(Collider)
            if collider is None or not collider.is_trigger:
                return False
        if link_mode == "collision" and entity.get_component(Collider) is None:
            return False

        if not self._ensure_scene_transition_action(world, entity_name):
            return False
        updated = self.update_component_payload(
            world,
            entity_name,
            "SceneTransitionAction",
            lambda payload, target_path=target_path, target_entry_id=target_entry_id: payload.update(
                {"target_scene_path": target_path, "target_entry_id": target_entry_id}
            ),
        )
        if not updated:
            return False

        self._remove_scene_transition_trigger_components(world, entity_name)
        if link_mode == "ui_button":
            return self._set_ui_button_scene_transition(world, entity_name)

        self._reset_ui_button_scene_transition(world, entity_name)
        if link_mode == "interact_near":
            return self._upsert_component_payload(
                world,
                entity_name,
                "SceneTransitionOnInteract",
                {"enabled": True, "require_player": True},
            )
        return self._upsert_component_payload(
            world,
            entity_name,
            "SceneTransitionOnContact",
            {
                "enabled": True,
                "mode": "collision" if link_mode == "collision" else "trigger_enter",
                "require_player": True,
            },
        )

    def _upsert_component_payload(
        self,
        world: "World",
        entity_name: str,
        component_name: str,
        component_data: Dict[str, Any],
    ) -> bool:
        if self._scene_manager is not None and self._scene_manager.current_scene is not None:
            entity_data = self._scene_manager.current_scene.find_entity(entity_name)
            scene_payload = None
            if entity_data is not None:
                components = entity_data.get("components", {})
                if isinstance(components, dict) and component_name in components:
                    scene_payload = copy.deepcopy(components[component_name])
            if scene_payload is None:
                return self._scene_manager.add_component_to_entity(entity_name, component_name, component_data)
            scene_payload.update(copy.deepcopy(component_data))
            return self.replace_component_payload(world, entity_name, component_name, scene_payload)

        payload = self._current_component_payload(world, entity_name, component_name)
        if payload is None:
            entity = world.get_entity_by_name(entity_name)
            if entity is None:
                return False
            component = self.registry.create(component_name, component_data)
            if component is None:
                return False
            entity.add_component(component)
            return True
        merged = copy.deepcopy(payload)
        merged.update(copy.deepcopy(component_data))
        return self.replace_component_payload(world, entity_name, component_name, merged)

    def _draw_nullable_float_row(
        self,
        label: str,
        value: Optional[float],
        prop_id: str,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
        on_commit: CommitCallback,
    ) -> int:
        display_value = "" if value is None else str(value)
        return self._draw_text_row(label, display_value, prop_id, x, y, width, is_edit, world, on_commit=on_commit)

    def _draw_transform_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        entity_name = self._entity_name_from_id(world, entity_id)
        payload = self._current_component_payload(world, entity_name, "Transform") if entity_name is not None else None
        current_y = y
        enabled = payload.get("enabled", component.enabled) if payload is not None else component.enabled
        x_value = payload.get("x", component.x) if payload is not None else component.x
        y_value = payload.get("y", component.y) if payload is not None else component.y
        rotation = payload.get("rotation", component.rotation) if payload is not None else component.rotation
        scale_x = payload.get("scale_x", component.scale_x) if payload is not None else component.scale_x
        scale_y = payload.get("scale_y", component.scale_y) if payload is not None else component.scale_y
        current_y = self._draw_component_field("Enabled", enabled, entity_id, "Transform", "enabled", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("X", x_value, entity_id, "Transform", "x", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Y", y_value, entity_id, "Transform", "y", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Rotation", rotation, entity_id, "Transform", "rotation", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Scale X", scale_x, entity_id, "Transform", "scale_x", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Scale Y", scale_y, entity_id, "Transform", "scale_y", x, current_y, width, is_edit, world)
        return current_y

    def _draw_sprite_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        current_y = self._draw_component_field("Enabled", component.enabled, entity_id, "Sprite", "enabled", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Texture", component.texture_path, entity_id, "Sprite", "texture_path", x, current_y, width, is_edit, world)
        current_y = self._draw_action_row("Editor", "Open Sprite Editor", x, current_y, width, bool(component.texture_path), lambda: self.open_sprite_editor(component.texture_path))
        current_y = self._draw_component_field("Width", component.width, entity_id, "Sprite", "width", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Height", component.height, entity_id, "Sprite", "height", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Origin X", component.origin_x, entity_id, "Sprite", "origin_x", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Origin Y", component.origin_y, entity_id, "Sprite", "origin_y", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Flip X", component.flip_x, entity_id, "Sprite", "flip_x", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Flip Y", component.flip_y, entity_id, "Sprite", "flip_y", x, current_y, width, is_edit, world)

        entity_name = self._entity_name_from_id(world, entity_id)
        tint = list(component.tint) if component.tint else [255, 255, 255, 255]
        current_y = self._draw_section_title("Tint", x, current_y, width)
        for index, channel in enumerate(("R", "G", "B", "A")):
            prop_id = f"{entity_id}:Sprite:tint:{index}"

            def on_commit(new_value: Any, index: int = index, entity_name: Optional[str] = entity_name) -> bool:
                if entity_name is None:
                    return False

                def update(payload: Dict[str, Any]) -> None:
                    colors = list(payload.get("tint", [255, 255, 255, 255]))
                    while len(colors) < 4:
                        colors.append(255)
                    colors[index] = max(0, min(255, int(new_value)))
                    payload["tint"] = colors

                return self.update_component_payload(world, entity_name, "Sprite", update)

            current_y = self._draw_int_row(channel, int(tint[index]), prop_id, x, current_y, width, is_edit, world, on_commit=on_commit)
        return current_y

    def _draw_collider_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Width", "width"),
            ("Height", "height"),
            ("Offset X", "offset_x"),
            ("Offset Y", "offset_y"),
            ("Trigger", "is_trigger"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "Collider", prop_name, x, current_y, width, is_edit, world)
        return current_y

    def _draw_rigidbody_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Velocity X", "velocity_x"),
            ("Velocity Y", "velocity_y"),
            ("Gravity", "gravity_scale"),
            ("Grounded", "is_grounded"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "RigidBody", prop_name, x, current_y, width, is_edit, world)
        return current_y

    def _draw_animator_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        current_y = self._draw_component_field("Enabled", component.enabled, entity_id, "Animator", "enabled", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Sprite Sheet", component.sprite_sheet, entity_id, "Animator", "sprite_sheet", x, current_y, width, is_edit, world)
        current_y = self._draw_action_row("Editor", "Open Sprite Editor", x, current_y, width, bool(component.sprite_sheet), lambda: self.open_sprite_editor(component.sprite_sheet))
        current_y = self._draw_component_field("Frame Width", component.frame_width, entity_id, "Animator", "frame_width", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Frame Height", component.frame_height, entity_id, "Animator", "frame_height", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Default", component.default_state, entity_id, "Animator", "default_state", x, current_y, width, is_edit, world)
        current_y = self._draw_readonly_row("Current", component.current_state, x, current_y, width)
        current_y = self._draw_readonly_row("Frame", str(component.current_frame), x, current_y, width)
        current_y = self._draw_readonly_row("Finished", str(component.is_finished), x, current_y, width)

        entity_name = self._entity_name_from_id(world, entity_id)
        current_y = self._draw_section_title("States", x, current_y, width)
        if entity_name is not None:
            add_rect = rl.Rectangle(x + self.LABEL_WIDTH + 5, current_y + 1, width - self.LABEL_WIDTH - 10, self.LINE_HEIGHT - 2)
            if rl.gui_button(add_rect, "Add State"):
                self.update_component_payload(world, entity_name, "Animator", self._add_animator_state)
        current_y += self.LINE_HEIGHT

        animations = component.animations or {}
        for state_name, animation in animations.items():
            current_y = self._draw_animator_state_editor(component, entity_id, entity_name, state_name, animation, x, current_y, width, is_edit, world)
        return current_y

    def _draw_animator_state_editor(
        self,
        component: Any,
        entity_id: int,
        entity_name: Optional[str],
        state_name: str,
        animation: Any,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
    ) -> int:
        del component
        current_y = self._draw_section_title(f"State: {state_name}", x, y, width)
        if entity_name is not None:
            field_x = x + self.LABEL_WIDTH + 5
            make_default_rect = rl.Rectangle(field_x, current_y + 1, 84, self.LINE_HEIGHT - 2)
            remove_rect = rl.Rectangle(field_x + 88, current_y + 1, 62, self.LINE_HEIGHT - 2)
            if rl.gui_button(make_default_rect, "Default"):
                self.update_component_payload(world, entity_name, "Animator", lambda payload, state_name=state_name: self._set_animator_default_state(payload, state_name))
            if rl.gui_button(remove_rect, "Remove"):
                self.update_component_payload(world, entity_name, "Animator", lambda payload, state_name=state_name: self._remove_animator_state(payload, state_name))
        current_y += self.LINE_HEIGHT

        if entity_name is None:
            return current_y

        def update_state(field_name: str, new_value: Any) -> bool:
            return self.update_component_payload(
                world,
                entity_name,
                "Animator",
                lambda payload, field_name=field_name, new_value=new_value, state_name=state_name: self._set_animator_state_field(payload, state_name, field_name, new_value),
            )

        current_y = self._draw_float_row("FPS", float(animation.fps), f"{entity_id}:Animator:{state_name}:fps", x, current_y, width, is_edit, world, on_commit=lambda value: update_state("fps", float(value)))
        current_y = self._draw_bool_row("Loop", bool(animation.loop), f"{entity_id}:Animator:{state_name}:loop", x, current_y, width, is_edit, world, on_toggle=lambda value: update_state("loop", bool(value)))
        current_y = self._draw_text_row("On Complete", animation.on_complete or "", f"{entity_id}:Animator:{state_name}:on_complete", x, current_y, width, is_edit, world, on_commit=lambda value: update_state("on_complete", value or None))

        current_y = self._draw_animator_list_editor(entity_id, entity_name, state_name, "slice_names", [str(item) for item in animation.slice_names], x, current_y, width, is_edit, world)
        current_y = self._draw_animator_list_editor(entity_id, entity_name, state_name, "frames", [int(item) for item in animation.frames], x, current_y, width, is_edit, world)
        return current_y

    def _draw_animator_list_editor(
        self,
        entity_id: int,
        entity_name: str,
        state_name: str,
        field_name: str,
        items: List[Any],
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
    ) -> int:
        current_y = self._draw_section_title(field_name.replace("_", " ").title(), x, y, width)
        add_rect = rl.Rectangle(x + self.LABEL_WIDTH + 5, current_y + 1, width - self.LABEL_WIDTH - 10, self.LINE_HEIGHT - 2)
        if rl.gui_button(add_rect, "Add Item"):
            default_value: Any = "" if field_name == "slice_names" else 0
            self.update_component_payload(
                world,
                entity_name,
                "Animator",
                lambda payload, state_name=state_name, field_name=field_name, default_value=default_value: self._append_animator_list_item(payload, state_name, field_name, default_value),
            )
        current_y += self.LINE_HEIGHT

        for index, item in enumerate(items):
            row_height = self.LINE_HEIGHT
            value_x = x + self.LABEL_WIDTH + 5
            label = f"#{index}"
            rl.gui_label(rl.Rectangle(x + 5, current_y, self.LABEL_WIDTH - 10, row_height), label)

            value_w = width - self.LABEL_WIDTH - 86
            prop_id = f"{entity_id}:Animator:{state_name}:{field_name}:{index}"

            def commit_value(new_value: Any, index: int = index) -> bool:
                cast_value = str(new_value) if field_name == "slice_names" else int(new_value)
                return self.update_component_payload(
                    world,
                    entity_name,
                    "Animator",
                    lambda payload, state_name=state_name, field_name=field_name, index=index, cast_value=cast_value: self._set_animator_list_item(payload, state_name, field_name, index, cast_value),
                )

            if field_name == "slice_names":
                self._draw_text_field(str(item), prop_id, value_x, current_y, value_w, row_height, is_edit, world, on_commit=commit_value)
            else:
                self._draw_int_field(int(item), prop_id, value_x, current_y, value_w, row_height, is_edit, world, on_commit=commit_value)

            up_rect = rl.Rectangle(value_x + value_w + 2, current_y + 1, 24, row_height - 2)
            down_rect = rl.Rectangle(value_x + value_w + 28, current_y + 1, 24, row_height - 2)
            delete_rect = rl.Rectangle(value_x + value_w + 54, current_y + 1, 24, row_height - 2)
            if rl.gui_button(up_rect, "<") and index > 0:
                self.update_component_payload(
                    world,
                    entity_name,
                    "Animator",
                    lambda payload, state_name=state_name, field_name=field_name, index=index: self._move_animator_list_item(payload, state_name, field_name, index, index - 1),
                )
            if rl.gui_button(down_rect, ">") and index < len(items) - 1:
                self.update_component_payload(
                    world,
                    entity_name,
                    "Animator",
                    lambda payload, state_name=state_name, field_name=field_name, index=index: self._move_animator_list_item(payload, state_name, field_name, index, index + 1),
                )
            if rl.gui_button(delete_rect, "x"):
                self.update_component_payload(
                    world,
                    entity_name,
                    "Animator",
                    lambda payload, state_name=state_name, field_name=field_name, index=index: self._remove_animator_list_item(payload, state_name, field_name, index),
                )
            current_y += row_height
        return current_y

    def _draw_camera2d_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Offset X", "offset_x"),
            ("Offset Y", "offset_y"),
            ("Zoom", "zoom"),
            ("Rotation", "rotation"),
            ("Primary", "is_primary"),
            ("Follow", "follow_entity"),
            ("Framing", "framing_mode"),
            ("Dead Zone W", "dead_zone_width"),
            ("Dead Zone H", "dead_zone_height"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "Camera2D", prop_name, x, current_y, width, is_edit, world)

        entity_name = self._entity_name_from_id(world, entity_id)
        for label, prop_name in (
            ("Clamp Left", "clamp_left"),
            ("Clamp Right", "clamp_right"),
            ("Clamp Top", "clamp_top"),
            ("Clamp Bottom", "clamp_bottom"),
        ):
            prop_id = f"{entity_id}:Camera2D:{prop_name}"

            def on_commit(new_value: Any, prop_name: str = prop_name, entity_name: Optional[str] = entity_name) -> bool:
                if entity_name is None:
                    return False
                parsed = None if str(new_value).strip() == "" else float(new_value)
                return self.update_component_payload(
                    world,
                    entity_name,
                    "Camera2D",
                    lambda payload, prop_name=prop_name, parsed=parsed: payload.__setitem__(prop_name, parsed),
                )

            current_y = self._draw_nullable_float_row(label, getattr(component, prop_name), prop_id, x, current_y, width, is_edit, world, on_commit=on_commit)

        current_y = self._draw_component_field("Recenter", component.recenter_on_play, entity_id, "Camera2D", "recenter_on_play", x, current_y, width, is_edit, world)
        return current_y

    def _draw_tilemap_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        entity_name = self._entity_name_from_id(world, entity_id)
        current_y = self._draw_component_field("Enabled", component.enabled, entity_id, "Tilemap", "enabled", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Cell Width", component.cell_width, entity_id, "Tilemap", "cell_width", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Cell Height", component.cell_height, entity_id, "Tilemap", "cell_height", x, current_y, width, is_edit, world)

        tileset_path = str(getattr(component, "tileset_path", "") or getattr(component, "tileset", {}).get("path", "") or "")
        tileset_prop_id = f"{entity_id}:Tilemap:tileset_path"

        def commit_tileset(new_value: Any) -> bool:
            if entity_name is None:
                return False
            normalized = str(new_value or "").strip()
            return self.update_component_payload(
                world,
                entity_name,
                "Tilemap",
                lambda payload, normalized=normalized: self._set_tilemap_tileset_reference(payload, normalized),
            )

        current_y = self._draw_text_row("Tileset", tileset_path, tileset_prop_id, x, current_y, width, is_edit, world, on_commit=commit_tileset)
        current_y = self._draw_component_field("Tile W", component.tileset_tile_width, entity_id, "Tilemap", "tileset_tile_width", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Tile H", component.tileset_tile_height, entity_id, "Tilemap", "tileset_tile_height", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Columns", component.tileset_columns, entity_id, "Tilemap", "tileset_columns", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Spacing", component.tileset_spacing, entity_id, "Tilemap", "tileset_spacing", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Margin", component.tileset_margin, entity_id, "Tilemap", "tileset_margin", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Default Layer", component.default_layer_name, entity_id, "Tilemap", "default_layer_name", x, current_y, width, is_edit, world)

        if entity_name is None:
            return current_y
        resolved_entity_name = entity_name

        payload = self._current_component_payload(world, resolved_entity_name, "Tilemap") or {}
        active_layer_name = self._resolve_tilemap_layer_name(
            payload,
            self._tilemap_authoring.layer_name if self._tilemap_authoring.entity_name == resolved_entity_name else None,
        )
        layer_options = [
            (str(layer.get("name", "")).strip(), str(layer.get("name", "")).strip())
            for layer in payload.get("layers", [])
            if isinstance(layer, dict) and str(layer.get("name", "")).strip()
        ]
        if not layer_options:
            layer_options = [(component.default_layer_name, component.default_layer_name)]
        brush_active = bool(self._tilemap_authoring.enabled and self._tilemap_authoring.entity_name == resolved_entity_name)

        def toggle_tilemap_tool(enabled: Any, entity_name: str = resolved_entity_name) -> bool:
            if enabled:
                return self.activate_tilemap_tool(world, entity_name)
            self.deactivate_tilemap_tool()
            return True

        current_y = self._draw_bool_row(
            "Brush Active",
            brush_active,
            f"{entity_id}:Tilemap:brush_active",
            x,
            current_y,
            width,
            is_edit,
            world,
            on_toggle=toggle_tilemap_tool,
        )
        def select_tilemap_active_layer(value: str, entity_name: str = resolved_entity_name) -> bool:
            return self.set_tilemap_active_layer(world, entity_name, value)

        current_y = self._draw_choice_row(
            "Edit Layer",
            layer_options,
            active_layer_name,
            x,
            current_y,
            width,
            is_edit,
            on_select=select_tilemap_active_layer,
        )
        current_y = self._draw_choice_row(
            "Brush Mode",
            [
                ("paint", "Paint"),
                ("erase", "Erase"),
                ("pick", "Pick"),
                ("box_fill", "Box Fill"),
                ("flood_fill", "Flood Fill"),
                ("stamp", "Stamp"),
            ],
            self._normalize_tilemap_tool_mode(self._tilemap_authoring.mode),
            x,
            current_y,
            width,
            is_edit,
            on_select=lambda value: self.set_tilemap_tool_mode(value),
        )

        self._synchronize_tilemap_tool_selection(world, resolved_entity_name)
        palette_entries = self.list_tilemap_palette_entries(world, resolved_entity_name, active_layer_name)
        source_path = self._resolve_tilemap_palette_source(payload, active_layer_name).get("path", "")
        current_y = self._draw_readonly_row("Paint Source", source_path or "(none)", x, current_y, width)
        if palette_entries:
            selected_tile = self._tilemap_authoring.tile_id or str(palette_entries[0].get("tile_id", ""))
            current_y = self._draw_readonly_row("Selected Tile", selected_tile or "(none)", x, current_y, width)
            def select_tilemap_palette_tile(
                value: str,
                entity_name: str = resolved_entity_name,
                source_path: str = source_path,
            ) -> bool:
                return self.set_tilemap_selected_tile(world, entity_name, value, source=source_path)

            current_y = self._draw_tilemap_palette_grid(
                palette_entries,
                selected_tile,
                x,
                current_y,
                width,
                is_edit,
                on_select=select_tilemap_palette_tile,
            )
        else:
            current_y = self._draw_readonly_row("Selected Tile", "(unresolved)", x, current_y, width)
        preview = self.get_tilemap_preview_snapshot(world) if brush_active and self._tilemap_authoring.entity_name == resolved_entity_name else None
        if preview is not None:
            current_y = self._draw_readonly_row("Brush Preview", str(preview.get("status_label", "")), x, current_y, width)
        elif brush_active:
            current_y = self._draw_readonly_row("Brush Preview", "Move cursor into Scene View", x, current_y, width)

        current_y = self._draw_section_title("Layers", x, current_y, width)
        add_rect = rl.Rectangle(x + self.LABEL_WIDTH + 5, current_y + 1, width - self.LABEL_WIDTH - 10, self.LINE_HEIGHT - 2)
        self._register_cursor_rect(add_rect)
        if rl.gui_button(add_rect, "Add Layer") and is_edit:
            self.update_component_payload(world, entity_name, "Tilemap", self._append_tilemap_layer)
        current_y += self.LINE_HEIGHT

        for layer in payload.get("layers", []):
            if not isinstance(layer, dict):
                continue
            layer_name = str(layer.get("name", "")).strip() or "Layer"
            current_y = self._draw_section_title(f"Layer: {layer_name}", x, current_y, width)
            current_y = self._draw_bool_row(
                "Visible",
                bool(layer.get("visible", True)),
                f"{entity_id}:Tilemap:{layer_name}:visible",
                x,
                current_y,
                width,
                is_edit,
                world,
                on_toggle=lambda new_value, entity_name=entity_name, layer_name=layer_name: self.update_component_payload(
                    world,
                    entity_name,
                    "Tilemap",
                    lambda payload, layer_name=layer_name, new_value=new_value: self._set_tilemap_layer_field(payload, layer_name, "visible", bool(new_value)),
                ),
            )
            current_y = self._draw_float_row(
                "Opacity",
                float(layer.get("opacity", 1.0)),
                f"{entity_id}:Tilemap:{layer_name}:opacity",
                x,
                current_y,
                width,
                is_edit,
                world,
                on_commit=lambda new_value, entity_name=entity_name, layer_name=layer_name: self.update_component_payload(
                    world,
                    entity_name,
                    "Tilemap",
                    lambda payload, layer_name=layer_name, new_value=new_value: self._set_tilemap_layer_field(payload, layer_name, "opacity", max(0.0, min(1.0, float(new_value)))),
                ),
            )
            current_y = self._draw_bool_row(
                "Locked",
                bool(layer.get("locked", False)),
                f"{entity_id}:Tilemap:{layer_name}:locked",
                x,
                current_y,
                width,
                is_edit,
                world,
                on_toggle=lambda new_value, entity_name=entity_name, layer_name=layer_name: self.update_component_payload(
                    world,
                    entity_name,
                    "Tilemap",
                    lambda payload, layer_name=layer_name, new_value=new_value: self._set_tilemap_layer_field(payload, layer_name, "locked", bool(new_value)),
                ),
            )
            current_y = self._draw_float_row(
                "Offset X",
                float(layer.get("offset_x", 0.0)),
                f"{entity_id}:Tilemap:{layer_name}:offset_x",
                x,
                current_y,
                width,
                is_edit,
                world,
                on_commit=lambda new_value, entity_name=entity_name, layer_name=layer_name: self.update_component_payload(
                    world,
                    entity_name,
                    "Tilemap",
                    lambda payload, layer_name=layer_name, new_value=new_value: self._set_tilemap_layer_field(payload, layer_name, "offset_x", float(new_value)),
                ),
            )
            current_y = self._draw_float_row(
                "Offset Y",
                float(layer.get("offset_y", 0.0)),
                f"{entity_id}:Tilemap:{layer_name}:offset_y",
                x,
                current_y,
                width,
                is_edit,
                world,
                on_commit=lambda new_value, entity_name=entity_name, layer_name=layer_name: self.update_component_payload(
                    world,
                    entity_name,
                    "Tilemap",
                    lambda payload, layer_name=layer_name, new_value=new_value: self._set_tilemap_layer_field(payload, layer_name, "offset_y", float(new_value)),
                ),
            )
            current_y = self._draw_text_row(
                "Source",
                normalize_asset_reference(layer.get("tilemap_source")).get("path", ""),
                f"{entity_id}:Tilemap:{layer_name}:tilemap_source",
                x,
                current_y,
                width,
                is_edit,
                world,
                on_commit=lambda new_value, entity_name=entity_name, layer_name=layer_name: self.update_component_payload(
                    world,
                    entity_name,
                    "Tilemap",
                    lambda payload, layer_name=layer_name, new_value=new_value: self._set_tilemap_layer_source(payload, layer_name, str(new_value or "").strip()),
                ),
            )
        return current_y

    def _draw_audio_source_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Asset", "asset_path"),
            ("Volume", "volume"),
            ("Pitch", "pitch"),
            ("Loop", "loop"),
            ("Play Awake", "play_on_awake"),
            ("Spatial", "spatial_blend"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "AudioSource", prop_name, x, current_y, width, is_edit, world)
        current_y = self._draw_readonly_row("Playing", str(component.is_playing), x, current_y, width)
        return current_y

    def _draw_input_map_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Move Left", "move_left"),
            ("Move Right", "move_right"),
            ("Move Up", "move_up"),
            ("Move Down", "move_down"),
            ("Action 1", "action_1"),
            ("Action 2", "action_2"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "InputMap", prop_name, x, current_y, width, is_edit, world)
        return current_y

    def _draw_player_controller_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Move Speed", "move_speed"),
            ("Jump Vel", "jump_velocity"),
            ("Air Control", "air_control"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "PlayerController2D", prop_name, x, current_y, width, is_edit, world)
        return current_y

    def _draw_script_behaviour_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        current_y = self._draw_component_field("Enabled", component.enabled, entity_id, "ScriptBehaviour", "enabled", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Module", component.module_path, entity_id, "ScriptBehaviour", "module_path", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Run In Edit", component.run_in_edit_mode, entity_id, "ScriptBehaviour", "run_in_edit_mode", x, current_y, width, is_edit, world)

        entity_name = self._entity_name_from_id(world, entity_id)
        current_y = self._draw_section_title("Public Data", x, current_y, width)
        if entity_name is not None:
            add_rect = rl.Rectangle(x + self.LABEL_WIDTH + 5, current_y + 1, width - self.LABEL_WIDTH - 10, self.LINE_HEIGHT - 2)
            if rl.gui_button(add_rect, "Add Entry"):
                self.update_component_payload(world, entity_name, "ScriptBehaviour", self._add_script_public_data_entry)
        current_y += self.LINE_HEIGHT

        public_data = dict(component.public_data or {})
        for key, value in public_data.items():
            current_y = self._draw_script_public_data_row(entity_id, entity_name, key, value, x, current_y, width, is_edit, world)
        return current_y

    def _draw_scene_entry_point_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        current_y = self._draw_component_field("Enabled", component.enabled, entity_id, "SceneEntryPoint", "enabled", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Entry ID", component.entry_id, entity_id, "SceneEntryPoint", "entry_id", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Label", component.label, entity_id, "SceneEntryPoint", "label", x, current_y, width, is_edit, world)
        return current_y

    def _draw_scene_link_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        entity_name = self._entity_name_from_id(world, entity_id)
        current_y = self._draw_component_field("Enabled", component.enabled, entity_id, "SceneLink", "enabled", x, current_y, width, is_edit, world)
        link_mode = str(getattr(component, "link_mode", "") or "").strip()
        target_path = str(getattr(component, "target_path", "") or "").strip()
        target_entity_name = str(getattr(component, "target_entity_name", "") or "").strip()
        target_entry_id = str(getattr(component, "target_entry_id", "") or "").strip()
        preview_label = str(getattr(component, "preview_label", "") or "").strip()
        flow_key = str(getattr(component, "flow_key", "") or "").strip()

        if entity_name is None:
            return current_y

        mode_options = self._get_scene_link_mode_options(world, entity_name)
        selected_mode = link_mode if any(key == link_mode for key, _ in mode_options) else mode_options[0][0]
        current_y = self._draw_choice_row(
            "Trigger",
            mode_options,
            selected_mode,
            x,
            current_y,
            width,
            is_edit,
            on_select=lambda value: self._set_scene_link_mode(world, entity_name, value),
        )

        scene_options = self._get_scene_transition_scene_options(target_path)
        selected_scene = target_path if any(key == target_path for key, _ in scene_options) else scene_options[0][0]
        current_y = self._draw_choice_row(
            "Target Scene",
            scene_options,
            selected_scene,
            x,
            current_y,
            width,
            is_edit,
            on_select=lambda value: self._set_scene_link_target_scene(world, entity_name, value),
        )

        spawn_options = self._get_scene_link_spawn_options(world, entity_name)
        selected_spawn = target_entry_id if any(key == target_entry_id for key, _ in spawn_options) else spawn_options[0][0]
        current_y = self._draw_choice_row(
            "Target Spawn",
            spawn_options,
            selected_spawn,
            x,
            current_y,
            width,
            is_edit,
            on_select=lambda value: self._set_scene_link_target_spawn(world, entity_name, value),
        )

        current_y = self._draw_component_field("Target Obj", target_entity_name, entity_id, "SceneLink", "target_entity_name", x, current_y, width, is_edit, world)
        current_y = self._draw_readonly_row("Connection", self._get_scene_link_connection_type(world, entity_name), x, current_y, width)
        current_y = self._draw_component_field("Preview", preview_label, entity_id, "SceneLink", "preview_label", x, current_y, width, is_edit, world)
        current_y = self._draw_component_field("Flow Key", flow_key, entity_id, "SceneLink", "flow_key", x, current_y, width, is_edit, world)
        current_y = self._draw_readonly_row("Custom", "Custom with AI...", x, current_y, width)

        for severity, message in self._get_scene_link_validation_messages(world, entity_name):
            current_y = self._draw_message_row(severity, message, x, current_y, width)
        return current_y

    def _list_available_scene_paths(self) -> List[str]:
        if self._scene_manager is None:
            return []
        current_scene = getattr(self._scene_manager, "current_scene", None)
        source_path = getattr(current_scene, "source_path", None)
        if not source_path:
            return []
        project_root = Path(source_path).resolve().parent.parent
        levels_root = project_root / "levels"
        if not levels_root.exists():
            return []
        cache_root = levels_root.as_posix()
        now = time.monotonic()
        if self._scene_path_cache_root == cache_root and (now - self._scene_path_cache_time) < 2.0:
            return list(self._scene_path_cache)
        self._scene_path_cache = sorted(path.relative_to(project_root).as_posix() for path in levels_root.rglob("*.json"))
        self._scene_path_cache_root = cache_root
        self._scene_path_cache_time = now
        return list(self._scene_path_cache)

    def _draw_canvas_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Render", "render_mode"),
            ("Ref Width", "reference_width"),
            ("Ref Height", "reference_height"),
            ("Match", "match_mode"),
            ("Sort Order", "sort_order"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "Canvas", prop_name, x, current_y, width, is_edit, world)
        return current_y

    def _draw_rect_transform_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Anchor Min X", "anchor_min_x"),
            ("Anchor Min Y", "anchor_min_y"),
            ("Anchor Max X", "anchor_max_x"),
            ("Anchor Max Y", "anchor_max_y"),
            ("Pivot X", "pivot_x"),
            ("Pivot Y", "pivot_y"),
            ("Anchored X", "anchored_x"),
            ("Anchored Y", "anchored_y"),
            ("Width", "width"),
            ("Height", "height"),
            ("Rotation", "rotation"),
            ("Scale X", "scale_x"),
            ("Scale Y", "scale_y"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "RectTransform", prop_name, x, current_y, width, is_edit, world)
        return current_y

    def _draw_ui_text_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Text", "text"),
            ("Font Size", "font_size"),
            ("Align", "alignment"),
            ("Wrap", "wrap"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "UIText", prop_name, x, current_y, width, is_edit, world)
        current_y = self._draw_readonly_row("Color", str(tuple(component.color)), x, current_y, width)
        return current_y

    def _draw_ui_button_editor(self, component: Any, entity_id: int, x: int, y: int, width: int, is_edit: bool, world: "World") -> int:
        current_y = y
        for label, prop_name in (
            ("Enabled", "enabled"),
            ("Interactable", "interactable"),
            ("Label", "label"),
            ("Pressed Scale", "transition_scale_pressed"),
        ):
            current_y = self._draw_component_field(label, getattr(component, prop_name), entity_id, "UIButton", prop_name, x, current_y, width, is_edit, world)

        entity_name = self._entity_name_from_id(world, entity_id)
        action = dict(component.on_click or {})
        action_type = str(action.get("type", ""))
        current_y = self._draw_component_field("Action", action_type, entity_id, "UIButton", "on_click_type", x, current_y, width, False, world)
        current_y = self._draw_readonly_row("Colors", f"n={tuple(component.normal_color)} h={tuple(component.hover_color)}", x, current_y, width)

        if entity_name is None:
            return current_y

        action_prop_id = f"{entity_id}:UIButton:on_click:type"
        target_key = "target" if action_type == "load_scene_flow" else "path" if action_type == "load_scene" else "name"
        target_value = str(action.get(target_key, ""))
        target_prop_id = f"{entity_id}:UIButton:on_click:{target_key}"

        def commit_action_type(new_value: Any) -> bool:
            return self.update_component_payload(
                world,
                entity_name,
                "UIButton",
                lambda payload, new_value=new_value: self._set_ui_button_action_type(payload, str(new_value)),
            )

        def commit_target_value(new_value: Any, target_key: str = target_key) -> bool:
            return self.update_component_payload(
                world,
                entity_name,
                "UIButton",
                lambda payload, new_value=new_value, target_key=target_key: self._set_ui_button_action_value(payload, target_key, str(new_value)),
            )

        current_y = self._draw_text_row("Action Type", action_type, action_prop_id, x, current_y, width, is_edit, world, on_commit=commit_action_type)
        if action_type == "run_scene_transition":
            current_y = self._draw_readonly_row("Action Value", "Managed by Scene Transition", x, current_y, width)
        else:
            current_y = self._draw_text_row("Action Value", target_value, target_prop_id, x, current_y, width, is_edit, world, on_commit=commit_target_value)
        return current_y

    def _draw_script_public_data_row(
        self,
        entity_id: int,
        entity_name: Optional[str],
        key: str,
        value: Any,
        x: int,
        y: int,
        width: int,
        is_edit: bool,
        world: "World",
    ) -> int:
        row_height = self.LINE_HEIGHT
        key_x = x + 5
        key_w = self.LABEL_WIDTH + 10
        value_x = key_x + key_w + 4
        value_w = width - key_w - 42
        delete_x = value_x + value_w + 4

        key_prop_id = f"{entity_id}:ScriptBehaviour:key:{key}"
        value_prop_id = f"{entity_id}:ScriptBehaviour:value:{key}"

        def rename_key(new_key: Any) -> bool:
            if entity_name is None:
                return False
            target_key = str(new_key).strip()
            if not target_key:
                return False
            return self.update_component_payload(
                world,
                entity_name,
                "ScriptBehaviour",
                lambda payload, old_key=key, target_key=target_key: self._rename_script_public_data_key(payload, old_key, target_key),
            )

        self._draw_text_field(key, key_prop_id, key_x, y, key_w, row_height, is_edit, world, on_commit=rename_key)

        if entity_name is not None:
            if isinstance(value, bool):
                self._draw_bool_field(
                    value,
                    value_prop_id,
                    value_x,
                    y,
                    value_w,
                    row_height,
                    is_edit,
                    world,
                    on_toggle=lambda new_value, key=key: self.update_component_payload(
                        world,
                        entity_name,
                        "ScriptBehaviour",
                        lambda payload, key=key, new_value=new_value: self._set_script_public_data_value(payload, key, bool(new_value)),
                    ),
                )
            elif isinstance(value, int) and not isinstance(value, bool):
                self._draw_int_field(
                    int(value),
                    value_prop_id,
                    value_x,
                    y,
                    value_w,
                    row_height,
                    is_edit,
                    world,
                    on_commit=lambda new_value, key=key: self.update_component_payload(
                        world,
                        entity_name,
                        "ScriptBehaviour",
                        lambda payload, key=key, new_value=new_value: self._set_script_public_data_value(payload, key, int(new_value)),
                    ),
                )
            elif isinstance(value, float):
                self._draw_float_field(
                    float(value),
                    value_prop_id,
                    value_x,
                    y,
                    value_w,
                    row_height,
                    is_edit,
                    world,
                    on_commit=lambda new_value, key=key: self.update_component_payload(
                        world,
                        entity_name,
                        "ScriptBehaviour",
                        lambda payload, key=key, new_value=new_value: self._set_script_public_data_value(payload, key, float(new_value)),
                    ),
                )
            elif isinstance(value, str):
                self._draw_text_field(
                    value,
                    value_prop_id,
                    value_x,
                    y,
                    value_w,
                    row_height,
                    is_edit,
                    world,
                    on_commit=lambda new_value, key=key: self.update_component_payload(
                        world,
                        entity_name,
                        "ScriptBehaviour",
                        lambda payload, key=key, new_value=new_value: self._set_script_public_data_value(payload, key, str(new_value)),
                    ),
                )
            else:
                self._draw_readonly_field(str(value), value_x, y + 1, value_w, row_height - 2)

            delete_rect = rl.Rectangle(delete_x, y + 1, 24, row_height - 2)
            if rl.gui_button(delete_rect, "x"):
                self.update_component_payload(
                    world,
                    entity_name,
                    "ScriptBehaviour",
                    lambda payload, key=key: self._remove_script_public_data_key(payload, key),
                )
        return y + row_height

    def _add_animator_state(self, payload: Dict[str, Any]) -> None:
        animations = payload.setdefault("animations", {})
        suffix = 1
        while f"state_{suffix}" in animations:
            suffix += 1
        state_name = f"state_{suffix}"
        animations[state_name] = {
            "frames": [0],
            "slice_names": [],
            "fps": 8.0,
            "loop": True,
            "on_complete": None,
        }
        if not payload.get("default_state"):
            payload["default_state"] = state_name
        if not payload.get("current_state"):
            payload["current_state"] = state_name

    def _set_animator_default_state(self, payload: Dict[str, Any], state_name: str) -> None:
        payload["default_state"] = state_name
        if payload.get("current_state") not in payload.get("animations", {}):
            payload["current_state"] = state_name

    def _remove_animator_state(self, payload: Dict[str, Any], state_name: str) -> None:
        animations = payload.setdefault("animations", {})
        if state_name not in animations:
            return
        del animations[state_name]
        if payload.get("default_state") == state_name:
            payload["default_state"] = next(iter(animations.keys()), "")
        if payload.get("current_state") == state_name:
            payload["current_state"] = payload.get("default_state", "")
        for animation in animations.values():
            if animation.get("on_complete") == state_name:
                animation["on_complete"] = None

    def _set_animator_state_field(self, payload: Dict[str, Any], state_name: str, field_name: str, value: Any) -> None:
        animations = payload.setdefault("animations", {})
        if state_name not in animations:
            return
        animations[state_name][field_name] = value

    def _append_animator_list_item(self, payload: Dict[str, Any], state_name: str, field_name: str, value: Any) -> None:
        animations = payload.setdefault("animations", {})
        state = animations.setdefault(state_name, {})
        items = list(state.get(field_name, []))
        items.append(value)
        state[field_name] = items

    def _set_animator_list_item(self, payload: Dict[str, Any], state_name: str, field_name: str, index: int, value: Any) -> None:
        animations = payload.setdefault("animations", {})
        state = animations.setdefault(state_name, {})
        items = list(state.get(field_name, []))
        while len(items) <= index:
            items.append("" if field_name == "slice_names" else 0)
        items[index] = value
        state[field_name] = items

    def _move_animator_list_item(self, payload: Dict[str, Any], state_name: str, field_name: str, from_index: int, to_index: int) -> None:
        animations = payload.setdefault("animations", {})
        state = animations.setdefault(state_name, {})
        items = list(state.get(field_name, []))
        if from_index < 0 or to_index < 0 or from_index >= len(items) or to_index >= len(items):
            return
        item = items.pop(from_index)
        items.insert(to_index, item)
        state[field_name] = items

    def _remove_animator_list_item(self, payload: Dict[str, Any], state_name: str, field_name: str, index: int) -> None:
        animations = payload.setdefault("animations", {})
        state = animations.setdefault(state_name, {})
        items = list(state.get(field_name, []))
        if 0 <= index < len(items):
            del items[index]
        state[field_name] = items

    def _add_script_public_data_entry(self, payload: Dict[str, Any]) -> None:
        public_data = payload.setdefault("public_data", {})
        suffix = 1
        while f"key_{suffix}" in public_data:
            suffix += 1
        public_data[f"key_{suffix}"] = ""

    def _rename_script_public_data_key(self, payload: Dict[str, Any], old_key: str, new_key: str) -> None:
        public_data = payload.setdefault("public_data", {})
        if old_key not in public_data or (new_key != old_key and new_key in public_data):
            return
        value = public_data.pop(old_key)
        rebuilt: Dict[str, Any] = {}
        rebuilt[new_key] = value
        for existing_key, existing_value in public_data.items():
            rebuilt[existing_key] = existing_value
        payload["public_data"] = rebuilt

    def _set_script_public_data_value(self, payload: Dict[str, Any], key: str, value: Any) -> None:
        public_data = payload.setdefault("public_data", {})
        if key in public_data:
            public_data[key] = value

    def _remove_script_public_data_key(self, payload: Dict[str, Any], key: str) -> None:
        public_data = payload.setdefault("public_data", {})
        public_data.pop(key, None)

    def _set_ui_button_action_type(self, payload: Dict[str, Any], action_type: str) -> None:
        normalized = str(action_type).strip() or "emit_event"
        action: Dict[str, Any] = {"type": normalized}
        if normalized == "load_scene_flow":
            action["target"] = "next_scene"
        elif normalized == "load_scene":
            action["path"] = ""
        elif normalized == "run_scene_transition":
            action = {"type": "run_scene_transition"}
        else:
            action["type"] = "emit_event"
            action["name"] = "ui.button_clicked"
        payload["on_click"] = action

    def _set_ui_button_action_value(self, payload: Dict[str, Any], key: str, value: str) -> None:
        action = dict(payload.get("on_click", {}))
        action[str(key)] = str(value)
        payload["on_click"] = action

    def _remove_component(self, world: "World", entity_id: int, component_name: str) -> bool:
        entity = world.get_entity(entity_id)
        if entity is None:
            return False
        if self._scene_manager is not None:
            removed = self._scene_manager.remove_component_from_entity(entity.name, component_name)
            if removed:
                print(f"[INSPECTOR] Removed {component_name} from {entity.name}")
            return removed

        component = self._find_component(entity, component_name)
        if component is None:
            return False
        entity.remove_component(type(component))
        print(f"[INSPECTOR] Removed {component_name} from {entity.name}")
        return True

    def _add_component(self, world: "World", entity_id: int, component_name: str) -> bool:
        entity = world.get_entity(entity_id)
        if entity is None:
            return False
        if self._scene_manager is not None:
            added = self._scene_manager.add_component_to_entity(entity.name, component_name, {"enabled": True})
            if added:
                print(f"[INSPECTOR] Component {component_name} added to {entity.name}")
            return added

        new_component = self.registry.create(component_name, {"enabled": True})
        if new_component is None:
            return False
        entity.add_component(new_component)
        print(f"[INSPECTOR] Component {component_name} added to {entity.name}")
        return True
