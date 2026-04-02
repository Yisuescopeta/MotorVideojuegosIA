from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any, Optional

import pyray as rl

from engine.editor.console_panel import log_err, log_warn
from engine.editor.cursor_manager import CursorVisualState
from engine.editor.render_safety import gui_toggle_bool
from engine.scenes.scene_transition_support import collect_flow_graph_data, list_scene_entry_points


class SceneFlowPanel:
    """Visual SceneLink authoring panel with sidebar + canvas."""

    BG_COLOR = rl.Color(32, 32, 32, 255)
    PANEL_BG = rl.Color(36, 36, 36, 255)
    PANEL_BG_ALT = rl.Color(42, 42, 42, 255)
    HEADER_COLOR = rl.Color(54, 54, 54, 255)
    BORDER_COLOR = rl.Color(24, 24, 24, 255)
    TEXT_COLOR = rl.Color(218, 218, 218, 255)
    TEXT_DIM = rl.Color(145, 145, 145, 255)
    ACCENT = rl.Color(58, 121, 187, 255)
    WARNING = rl.Color(210, 160, 72, 255)
    ERROR = rl.Color(205, 92, 92, 255)
    OK = rl.Color(88, 154, 108, 255)
    ONE_WAY = rl.Color(255, 109, 18, 255)
    TWO_WAY = rl.Color(201, 43, 140, 255)
    MODAL_OVERLAY = rl.Color(0, 0, 0, 120)
    NODE_BG = rl.Color(46, 46, 46, 255)
    TARGET_NODE_BG = rl.Color(44, 44, 44, 255)
    SELECTED_BG = rl.Color(60, 72, 96, 255)
    LIST_ROW_BG = rl.Color(41, 41, 41, 255)
    LIST_ROW_ALT = rl.Color(37, 37, 37, 255)
    LIST_ROW_HOVER = rl.Color(60, 60, 60, 255)

    TOOLBAR_HEIGHT = 24
    PANEL_PADDING = 8
    ADD_BUTTON_HEIGHT = 32
    SIDEBAR_CARD_HEIGHT = 56
    NODE_WIDTH = 176
    NODE_HEIGHT = 56
    CONNECTOR_RADIUS = 6

    def __init__(self) -> None:
        self.project_service: Any = None
        self.scene_manager: Any = None
        self.current_scene_only: bool = True
        self.connection_mode: str = "one_way"
        self.request_open_source: Optional[dict[str, str]] = None
        self.request_open_target: Optional[dict[str, str]] = None
        self._snapshot: dict[str, list[dict[str, Any]]] = {
            "sidebar_items": [],
            "runtime_only_items": [],
            "canvas_nodes": [],
            "canvas_edges": [],
            "issues": [],
        }
        self._last_refresh_time: float = 0.0
        self._last_render_error: str = ""
        self._cursor_interactive_rects: list[rl.Rectangle] = []
        self._row_rects: dict[str, rl.Rectangle] = {}
        self._node_rects: dict[str, rl.Rectangle] = {}
        self._detail_columns: dict[str, rl.Rectangle] = {}
        self._selected_sidebar_key: str = ""
        self._selected_node_key: str = ""
        self._drag_sidebar_item_key: str = ""
        self._drag_node_key: str = ""
        self._drag_offset = rl.Vector2(0.0, 0.0)
        self._connecting_from_node_key: str = ""
        self._list_scroll: float = 0.0
        self._panel_rect = rl.Rectangle(0, 0, 0, 0)
        self._toolbar_rect = rl.Rectangle(0, 0, 0, 0)
        self._sidebar_rect = rl.Rectangle(0, 0, 0, 0)
        self._sidebar_list_rect = rl.Rectangle(0, 0, 0, 0)
        self._sidebar_footer_rect = rl.Rectangle(0, 0, 0, 0)
        self._canvas_rect = rl.Rectangle(0, 0, 0, 0)
        self._list_rect = rl.Rectangle(0, 0, 0, 0)
        self._list_header_rect = rl.Rectangle(0, 0, 0, 0)
        self._list_body_rect = rl.Rectangle(0, 0, 0, 0)
        self._editor_rect = rl.Rectangle(0, 0, 0, 0)
        self._editor_header_rect = rl.Rectangle(0, 0, 0, 0)
        self._editor_body_rect = rl.Rectangle(0, 0, 0, 0)
        self._modal_open: bool = False
        self._modal_scene_ref: str = ""
        self._modal_selected_entity_name: str = ""

    def set_project_service(self, project_service: Any) -> None:
        self.project_service = project_service
        self.refresh(force=True)

    def set_scene_manager(self, scene_manager: Any) -> None:
        self.scene_manager = scene_manager
        self.refresh(force=True)

    def refresh(self, *, force: bool = False) -> dict[str, list[dict[str, Any]]]:
        now = time.monotonic()
        if not force and (now - self._last_refresh_time) < 0.2:
            return self._snapshot
        snapshot = collect_flow_graph_data(self.project_service, self.scene_manager)
        snapshot["rows"] = list(snapshot.get("sidebar_items", []))
        self._snapshot = snapshot
        self._last_refresh_time = now
        return self._snapshot

    def get_cursor_intent(self, mouse_pos: Optional[rl.Vector2] = None) -> CursorVisualState:
        mouse = rl.get_mouse_position() if mouse_pos is None else mouse_pos
        for rect in self._cursor_interactive_rects:
            if rl.check_collision_point_rec(mouse, rect):
                return CursorVisualState.INTERACTIVE
        return CursorVisualState.DEFAULT

    def render(self, x: int, y: int, width: int, height: int) -> None:
        self._cursor_interactive_rects = []
        self._row_rects = {}
        self._node_rects = {}
        self._panel_rect = rl.Rectangle(float(x), float(y), float(max(0, width)), float(max(0, height)))
        rl.draw_rectangle_rec(self._panel_rect, self.BG_COLOR)
        try:
            snapshot = self.refresh()
            self._layout_rects()
            self._handle_wheel()
            self._draw_toolbar(snapshot)
            self._draw_sidebar(snapshot)
            self._draw_canvas(snapshot)
            if self._modal_open:
                self._draw_add_modal()
            self._finalize_drag(snapshot)
            self._last_render_error = ""
        except Exception as exc:
            self._last_render_error = str(exc)
            log_err(f"Scene Flow render error: {exc}")
            self._draw_error_fallback(str(exc))
        rl.draw_rectangle_lines_ex(self._panel_rect, 1, self.BORDER_COLOR)

    def _layout_rects(self) -> None:
        inner_x = self._panel_rect.x + self.PANEL_PADDING
        inner_y = self._panel_rect.y + self.PANEL_PADDING
        inner_w = max(0.0, self._panel_rect.width - (self.PANEL_PADDING * 2))
        inner_h = max(0.0, self._panel_rect.height - (self.PANEL_PADDING * 2))
        self._toolbar_rect = rl.Rectangle(inner_x, inner_y, inner_w, min(self.TOOLBAR_HEIGHT, inner_h))
        body_y = self._toolbar_rect.y + self._toolbar_rect.height + self.PANEL_PADDING
        body_h = max(0.0, inner_h - self._toolbar_rect.height - self.PANEL_PADDING)
        sidebar_w = min(max(240.0, inner_w * 0.28), 340.0)
        self._sidebar_rect = rl.Rectangle(inner_x, body_y, sidebar_w, body_h)
        self._sidebar_footer_rect = rl.Rectangle(
            self._sidebar_rect.x,
            self._sidebar_rect.y + self._sidebar_rect.height - self.ADD_BUTTON_HEIGHT,
            self._sidebar_rect.width,
            self.ADD_BUTTON_HEIGHT,
        )
        self._sidebar_list_rect = rl.Rectangle(
            self._sidebar_rect.x,
            self._sidebar_rect.y,
            self._sidebar_rect.width,
            max(0.0, self._sidebar_rect.height - self.ADD_BUTTON_HEIGHT - self.PANEL_PADDING),
        )
        self._canvas_rect = rl.Rectangle(
            self._sidebar_rect.x + self._sidebar_rect.width + self.PANEL_PADDING,
            body_y,
            max(0.0, inner_w - self._sidebar_rect.width - self.PANEL_PADDING),
            body_h,
        )
        self._list_rect = self._sidebar_rect
        self._list_header_rect = rl.Rectangle(self._sidebar_list_rect.x, self._sidebar_list_rect.y, self._sidebar_list_rect.width, 24)
        self._list_body_rect = rl.Rectangle(self._sidebar_list_rect.x, self._sidebar_list_rect.y + 24, self._sidebar_list_rect.width, max(0.0, self._sidebar_list_rect.height - 24))
        self._editor_rect = self._canvas_rect
        self._editor_header_rect = rl.Rectangle(self._canvas_rect.x, self._canvas_rect.y, self._canvas_rect.width, 24)
        self._editor_body_rect = rl.Rectangle(self._canvas_rect.x, self._canvas_rect.y + 24, self._canvas_rect.width, max(0.0, self._canvas_rect.height - 24))

    def _draw_toolbar(self, snapshot: dict[str, list[dict[str, Any]]]) -> None:
        rect = self._toolbar_rect
        rl.draw_rectangle_rec(rect, self.HEADER_COLOR)
        rl.draw_line(int(rect.x), int(rect.y + rect.height - 1), int(rect.x + rect.width), int(rect.y + rect.height - 1), self.BORDER_COLOR)
        rl.draw_text("Scene Flow", int(rect.x + 10), int(rect.y + 6), 11, self.TEXT_COLOR)
        issues = len(snapshot.get("issues", []))
        rl.draw_text(f"{len(snapshot.get('sidebar_items', []))} links", int(rect.x + 92), int(rect.y + 6), 10, self.TEXT_DIM)
        if issues:
            rl.draw_text(f"{issues} issue(s)", int(rect.x + 156), int(rect.y + 6), 10, self.WARNING)

        toggle_rect = rl.Rectangle(rect.x + rect.width - 278, rect.y + 2, 118, 20)
        mode_rect = rl.Rectangle(rect.x + rect.width - 154, rect.y + 2, 92, 20)
        refresh_rect = rl.Rectangle(rect.x + rect.width - 58, rect.y + 2, 50, 20)
        self._register_cursor_rect(toggle_rect)
        self._register_cursor_rect(mode_rect)
        self._register_cursor_rect(refresh_rect)
        self.current_scene_only = gui_toggle_bool(toggle_rect, "Current scene", self.current_scene_only)
        if rl.gui_button(mode_rect, "Mode: Two" if self.connection_mode == "two_way" else "Mode: One"):
            self.connection_mode = "one_way" if self.connection_mode == "two_way" else "two_way"
        if rl.gui_button(refresh_rect, "Refresh"):
            self.refresh(force=True)

    def _filtered_sidebar_items(self, snapshot: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        items = list(snapshot.get("sidebar_items", []))
        if not self.current_scene_only:
            return items
        active_path, active_key = self._active_scene_identity()
        return [
            item
            for item in items
            if str(item.get("source_scene_path", "") or "") == active_path
            or str(item.get("source_scene_key", "") or "") == active_key
            or str(item.get("source_scene_ref", "") or "") in {active_path, active_key}
        ]

    def _filtered_items(self, snapshot: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        return self._filtered_sidebar_items(snapshot)

    def _draw_sidebar(self, snapshot: dict[str, list[dict[str, Any]]]) -> None:
        rl.draw_rectangle_rec(self._sidebar_rect, self.PANEL_BG)
        rl.draw_rectangle_rec(self._sidebar_list_rect, self.PANEL_BG_ALT)
        rl.draw_rectangle_lines_ex(self._sidebar_rect, 1, self.BORDER_COLOR)
        rl.draw_text("Scene Links", int(self._sidebar_list_rect.x + 10), int(self._sidebar_list_rect.y + 8), 11, self.TEXT_COLOR)
        rl.draw_text("SceneLink Objects", int(self._sidebar_list_rect.x + 92), int(self._sidebar_list_rect.y + 8), 11, self.TEXT_DIM)

        items = self._filtered_sidebar_items(snapshot)
        self._ensure_selected_item(items)
        mouse = rl.get_mouse_position()
        content_y = self._sidebar_list_rect.y + 28.0 - self._list_scroll
        visible_bottom = self._sidebar_list_rect.y + self._sidebar_list_rect.height

        if not items:
            rl.draw_text("No SceneLink objects found.", int(self._sidebar_list_rect.x + 12), int(self._sidebar_list_rect.y + 34), 11, self.TEXT_DIM)
            rl.draw_text("No SceneLink entities found in this view.", int(self._sidebar_list_rect.x + 12), int(self._sidebar_list_rect.y + 50), 11, self.TEXT_DIM)
            rl.draw_text("Use Add SceneLink... to include an object.", int(self._sidebar_list_rect.x + 12), int(self._sidebar_list_rect.y + 66), 11, self.TEXT_DIM)
        for index, item in enumerate(items):
            rect = rl.Rectangle(
                self._sidebar_list_rect.x + 8,
                content_y,
                max(0.0, self._sidebar_list_rect.width - 16),
                self.SIDEBAR_CARD_HEIGHT,
            )
            content_y += self.SIDEBAR_CARD_HEIGHT + 6
            if rect.y + rect.height < self._sidebar_list_rect.y + 26:
                continue
            if rect.y > visible_bottom:
                break
            sidebar_key = str(item.get("sidebar_key", "") or "")
            self._row_rects[sidebar_key] = rect
            self._register_cursor_rect(rect)
            hover = rl.check_collision_point_rec(mouse, rect)
            selected = sidebar_key == self._selected_sidebar_key
            bg = self.SELECTED_BG if selected else self.LIST_ROW_HOVER if hover else self.LIST_ROW_BG if index % 2 == 0 else self.LIST_ROW_ALT
            rl.draw_rectangle_rec(rect, bg)
            rl.draw_rectangle_lines_ex(rect, 1, self.BORDER_COLOR)
            status_color = self._status_color(str(item.get("status", "ok")))
            rl.draw_rectangle(int(rect.x), int(rect.y), 4, int(rect.height), status_color)
            rl.draw_text(self._truncate(str(item.get("source_entity_name", "") or ""), 22), int(rect.x + 10), int(rect.y + 8), 11, self.TEXT_COLOR)
            rl.draw_text(self._truncate(str(item.get("source_scene_name", "") or ""), 22), int(rect.x + 10), int(rect.y + 24), 10, self.TEXT_DIM)
            rl.draw_text(self._truncate(str(item.get("trigger_label", "") or "No trigger"), 16), int(rect.x + 10), int(rect.y + 38), 10, self.TEXT_DIM)
            state_text = "connected" if bool(item.get("connected", False)) else "incomplete"
            rl.draw_text(state_text, int(rect.x + rect.width - 66), int(rect.y + 8), 10, status_color)

            if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._selected_sidebar_key = sidebar_key
                self._selected_node_key = str(item.get("node_key", "") or "")
                self.request_open_source = {
                    "scene_ref": str(item.get("source_scene_ref", "") or item.get("source_scene_path", "") or item.get("source_scene_key", "") or ""),
                    "entity_name": str(item.get("source_entity_name", "") or ""),
                }
                self._drag_sidebar_item_key = sidebar_key

        rl.draw_rectangle_rec(self._sidebar_footer_rect, self.PANEL_BG)
        rl.draw_line(int(self._sidebar_footer_rect.x), int(self._sidebar_footer_rect.y - 1), int(self._sidebar_footer_rect.x + self._sidebar_footer_rect.width), int(self._sidebar_footer_rect.y - 1), self.BORDER_COLOR)
        button_rect = rl.Rectangle(self._sidebar_footer_rect.x + 8, self._sidebar_footer_rect.y + 4, max(0.0, self._sidebar_footer_rect.width - 16), self.ADD_BUTTON_HEIGHT - 8)
        self._register_cursor_rect(button_rect)
        if rl.gui_button(button_rect, "Add SceneLink..."):
            self._modal_open = True
            self._seed_modal_scene()

    def _draw_canvas(self, snapshot: dict[str, list[dict[str, Any]]]) -> None:
        rl.draw_rectangle_rec(self._canvas_rect, self.PANEL_BG_ALT)
        rl.draw_rectangle_lines_ex(self._canvas_rect, 1, self.BORDER_COLOR)
        rl.draw_text("Connections Canvas", int(self._canvas_rect.x + 10), int(self._canvas_rect.y + 8), 11, self.TEXT_COLOR)
        rl.draw_text("Connection Editor", int(self._canvas_rect.x + 138), int(self._canvas_rect.y + 8), 11, self.TEXT_DIM)
        rl.draw_text("One-way", int(self._canvas_rect.x + self._canvas_rect.width - 132), int(self._canvas_rect.y + 8), 10, self.ONE_WAY)
        rl.draw_text("Two-way", int(self._canvas_rect.x + self._canvas_rect.width - 68), int(self._canvas_rect.y + 8), 10, self.TWO_WAY)

        filtered_items = self._filtered_sidebar_items(snapshot)
        visible_rows = {str(item.get("node_key", "") or ""): item for item in filtered_items}
        source_scene_refs = {
            str(item.get("source_scene_ref", "") or item.get("source_scene_path", "") or item.get("source_scene_key", "") or "")
            for item in filtered_items
        }
        visible_nodes: list[dict[str, Any]] = []
        for node in snapshot.get("canvas_nodes", []):
            node_key = str(node.get("node_key", "") or "")
            if node.get("kind") == "entity" and node_key not in visible_rows:
                continue
            if node.get("kind") == "target":
                edge_exists = any(
                    str(edge.get("target_node_key", "") or "") == node_key
                    and str(edge.get("source_scene_ref", "") or "") in source_scene_refs
                    for edge in snapshot.get("canvas_edges", [])
                )
                if not edge_exists:
                    continue
            visible_nodes.append(dict(node))

        self._place_default_nodes(visible_nodes)
        visible_node_keys = {str(node.get("node_key", "") or "") for node in visible_nodes}
        edges = [
            edge
            for edge in snapshot.get("canvas_edges", [])
            if str(edge.get("source_node_key", "") or "") in visible_node_keys
            and str(edge.get("target_node_key", "") or "") in visible_node_keys
        ]
        for edge in edges:
            self._draw_edge(edge)
        for node in visible_nodes:
            self._draw_node(node)
        self._handle_canvas_interactions(visible_nodes, snapshot)
        if not visible_nodes:
            rl.draw_text("Add SceneLink objects on the left and connect them here.", int(self._canvas_rect.x + 16), int(self._canvas_rect.y + 40), 12, self.TEXT_DIM)
            rl.draw_text("Select a node or card to edit its properties in the inspector.", int(self._canvas_rect.x + 16), int(self._canvas_rect.y + 58), 11, self.TEXT_DIM)

    def _draw_add_modal(self) -> None:
        rl.draw_rectangle_rec(self._panel_rect, self.MODAL_OVERLAY)
        modal_w = min(560.0, self._panel_rect.width - 48.0)
        modal_h = min(360.0, self._panel_rect.height - 48.0)
        modal_x = self._panel_rect.x + (self._panel_rect.width - modal_w) / 2
        modal_y = self._panel_rect.y + (self._panel_rect.height - modal_h) / 2
        modal = rl.Rectangle(modal_x, modal_y, modal_w, modal_h)
        rl.draw_rectangle_rec(modal, self.PANEL_BG)
        rl.draw_rectangle_lines_ex(modal, 1, self.BORDER_COLOR)
        rl.draw_rectangle(int(modal.x), int(modal.y), int(modal.width), 24, self.HEADER_COLOR)
        rl.draw_text("Add SceneLink", int(modal.x + 10), int(modal.y + 6), 11, self.TEXT_COLOR)

        scenes = self._available_scene_refs()
        if not self._modal_scene_ref and scenes:
            self._modal_scene_ref = scenes[0]
        scene_rect = rl.Rectangle(modal.x + 10, modal.y + 36, 220, modal.height - 82)
        object_rect = rl.Rectangle(scene_rect.x + scene_rect.width + 10, modal.y + 36, modal.width - scene_rect.width - 30, modal.height - 82)
        rl.draw_rectangle_rec(scene_rect, self.PANEL_BG_ALT)
        rl.draw_rectangle_rec(object_rect, self.PANEL_BG_ALT)
        rl.draw_text("Scenes", int(scene_rect.x + 8), int(scene_rect.y + 8), 10, self.TEXT_COLOR)
        rl.draw_text("Objects", int(object_rect.x + 8), int(object_rect.y + 8), 10, self.TEXT_COLOR)

        y = scene_rect.y + 28
        for scene_ref in scenes:
            item_rect = rl.Rectangle(scene_rect.x + 8, y, scene_rect.width - 16, 24)
            y += 28
            selected = scene_ref == self._modal_scene_ref
            self._register_cursor_rect(item_rect)
            rl.draw_rectangle_rec(item_rect, self.SELECTED_BG if selected else self.LIST_ROW_ALT)
            rl.draw_text(self._truncate(self._scene_label(scene_ref), 24), int(item_rect.x + 8), int(item_rect.y + 6), 10, self.TEXT_COLOR)
            if rl.check_collision_point_rec(rl.get_mouse_position(), item_rect) and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._modal_scene_ref = scene_ref
                self._modal_selected_entity_name = ""

        object_y = object_rect.y + 28
        for entity in self._modal_scene_entities():
            item_rect = rl.Rectangle(object_rect.x + 8, object_y, object_rect.width - 16, 24)
            object_y += 28
            entity_name = str(entity.get("name", "") or "")
            selected = entity_name == self._modal_selected_entity_name
            self._register_cursor_rect(item_rect)
            rl.draw_rectangle_rec(item_rect, self.SELECTED_BG if selected else self.LIST_ROW_ALT)
            suffix = " (already linked)" if bool(entity.get("has_scene_link", False)) else ""
            rl.draw_text(self._truncate(f"{entity_name}{suffix}", 40), int(item_rect.x + 8), int(item_rect.y + 6), 10, self.TEXT_COLOR if not entity.get("has_scene_link", False) else self.TEXT_DIM)
            if rl.check_collision_point_rec(rl.get_mouse_position(), item_rect) and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._modal_selected_entity_name = entity_name

        cancel_rect = rl.Rectangle(modal.x + modal.width - 146, modal.y + modal.height - 34, 64, 22)
        confirm_rect = rl.Rectangle(modal.x + modal.width - 74, modal.y + modal.height - 34, 64, 22)
        self._register_cursor_rect(cancel_rect)
        self._register_cursor_rect(confirm_rect)
        if rl.gui_button(cancel_rect, "Cancel"):
            self._modal_open = False
        if self._modal_scene_ref and self._modal_selected_entity_name and rl.gui_button(confirm_rect, "Add"):
            if self._create_or_adopt_scene_link(self._modal_selected_entity_name, None, scene_ref=self._modal_scene_ref):
                self._modal_open = False
                self.refresh(force=True)

    def _finalize_drag(self, snapshot: dict[str, list[dict[str, Any]]]) -> None:
        if not self._drag_sidebar_item_key:
            return
        mouse = rl.get_mouse_position()
        row = next((item for item in self._filtered_sidebar_items(snapshot) if str(item.get("sidebar_key", "")) == self._drag_sidebar_item_key), None)
        if row is not None:
            ghost = rl.Rectangle(mouse.x - (self.NODE_WIDTH / 2), mouse.y - (self.NODE_HEIGHT / 2), self.NODE_WIDTH, self.NODE_HEIGHT)
            rl.draw_rectangle_lines_ex(ghost, 2, self.ACCENT)
            rl.draw_text(self._truncate(str(row.get("source_entity_name", "") or ""), 18), int(ghost.x + 8), int(ghost.y + 18), 11, self.TEXT_COLOR)
            if rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
                if rl.check_collision_point_rec(mouse, self._canvas_rect):
                    self._persist_entity_node_position(
                        str(row.get("source_scene_ref", "") or row.get("source_scene_path", "") or row.get("source_scene_key", "") or ""),
                        str(row.get("source_entity_name", "") or ""),
                        mouse.x - self.NODE_WIDTH / 2,
                        mouse.y - self.NODE_HEIGHT / 2,
                    )
                    self.refresh(force=True)
                self._drag_sidebar_item_key = ""

    def _draw_error_fallback(self, message: str) -> None:
        rl.draw_rectangle_rec(self._toolbar_rect, self.HEADER_COLOR)
        rl.draw_text("Scene Flow", int(self._toolbar_rect.x + 10), int(self._toolbar_rect.y + 6), 11, self.TEXT_COLOR)
        body = rl.Rectangle(
            self._panel_rect.x + self.PANEL_PADDING,
            self._toolbar_rect.y + self._toolbar_rect.height + self.PANEL_PADDING,
            max(0.0, self._panel_rect.width - (self.PANEL_PADDING * 2)),
            max(0.0, self._panel_rect.height - self._toolbar_rect.height - (self.PANEL_PADDING * 3)),
        )
        rl.draw_rectangle_rec(body, rl.Color(64, 38, 38, 255))
        rl.draw_rectangle_lines_ex(body, 1, self.ERROR)
        rl.draw_text("Flow could not render this frame.", int(body.x + 12), int(body.y + 12), 12, self.TEXT_COLOR)
        rl.draw_text(self._truncate(message, 96), int(body.x + 12), int(body.y + 32), 10, self.TEXT_DIM)

    def _seed_modal_scene(self) -> None:
        scenes = self._available_scene_refs()
        self._modal_scene_ref = scenes[0] if scenes else ""
        self._modal_selected_entity_name = ""

    def _available_scene_refs(self) -> list[str]:
        refs: list[str] = []
        if self.project_service is not None and getattr(self.project_service, "has_project", False):
            for scene_info in self.project_service.list_project_scenes():
                path = str(scene_info.get("path", "") or "")
                abs_path = str(scene_info.get("absolute_path", "") or "")
                refs.append(path or abs_path)
        if self.scene_manager is not None and hasattr(self.scene_manager, "list_open_scenes"):
            for scene_info in self.scene_manager.list_open_scenes():
                ref = str(scene_info.get("path", "") or scene_info.get("key", "") or "")
                if ref and ref not in refs:
                    refs.append(ref)
        return refs

    def _active_scene_identity(self) -> tuple[str, str]:
        if self.scene_manager is None or not hasattr(self.scene_manager, "get_active_scene_summary"):
            return "", ""
        summary = self.scene_manager.get_active_scene_summary()
        return str(summary.get("path", "") or ""), str(summary.get("key", "") or "")

    def _handle_wheel(self) -> None:
        if not rl.check_collision_point_rec(rl.get_mouse_position(), self._sidebar_list_rect):
            return
        wheel = rl.get_mouse_wheel_move()
        if wheel == 0:
            return
        self._list_scroll = max(0.0, self._list_scroll - (wheel * 24.0))

    def _ensure_selected_item(self, items: list[dict[str, Any]]) -> None:
        keys = {str(item.get("sidebar_key", "") or "") for item in items}
        if self._selected_sidebar_key in keys:
            return
        self._selected_sidebar_key = str(items[0].get("sidebar_key", "") or "") if items else ""
        self._selected_node_key = str(items[0].get("node_key", "") or "") if items else ""

    def _status_color(self, status: str) -> rl.Color:
        if status == "error":
            return self.ERROR
        if status == "warning":
            return self.WARNING
        return self.OK

    def _modal_scene_entities(self) -> list[dict[str, Any]]:
        if self.scene_manager is None or not self._modal_scene_ref:
            return []
        entry = self.scene_manager.ensure_scene_open(self._modal_scene_ref, activate=False)
        if entry is None:
            return []
        return self.scene_manager.list_scene_entities(self._modal_scene_ref)

    def _scene_label(self, scene_ref: str) -> str:
        if scene_ref.endswith(".json"):
            return Path(scene_ref).stem
        return scene_ref

    def _persist_entity_node_position(self, scene_ref: str, entity_name: str, x: float, y: float) -> None:
        if self.scene_manager is None:
            return
        state = self.scene_manager.get_scene_view_state(scene_ref) or {}
        flow_layout = dict(state.get("flow_layout", {}) or {})
        nodes = dict(flow_layout.get("nodes", {}) or {})
        nodes[entity_name] = {"x": self._clamp_x(x), "y": self._clamp_y(y)}
        flow_layout["nodes"] = nodes
        state["flow_layout"] = flow_layout
        self.scene_manager.set_scene_view_state(scene_ref, state)

    def _persist_target_node_position(self, source_scene_ref: str, target_key: str, x: float, y: float) -> None:
        if self.scene_manager is None:
            return
        state = self.scene_manager.get_scene_view_state(source_scene_ref) or {}
        flow_layout = dict(state.get("flow_layout", {}) or {})
        targets = dict(flow_layout.get("targets", {}) or {})
        targets[target_key] = {"x": self._clamp_x(x), "y": self._clamp_y(y)}
        flow_layout["targets"] = targets
        state["flow_layout"] = flow_layout
        self.scene_manager.set_scene_view_state(source_scene_ref, state)

    def _persist_node_position(self, node: dict[str, Any], x: float, y: float) -> None:
        if str(node.get("kind", "")) == "entity":
            self._persist_entity_node_position(str(node.get("scene_ref", "") or ""), str(node.get("entity_name", "") or ""), x, y)
            return
        self._persist_target_node_position(
            str(node.get("source_scene_ref", "") or node.get("scene_ref", "") or ""),
            str(node.get("node_key", "") or ""),
            x,
            y,
        )

    def _sidebar_key_for_node(self, node_key: str, snapshot: dict[str, list[dict[str, Any]]]) -> str:
        for item in snapshot.get("sidebar_items", []):
            if str(item.get("node_key", "") or "") == node_key:
                return str(item.get("sidebar_key", "") or "")
        return ""

    def _apply_connection(self, source_node_key: str, target_node: dict[str, Any], snapshot: dict[str, list[dict[str, Any]]]) -> None:
        source_row = next((item for item in snapshot.get("sidebar_items", []) if str(item.get("node_key", "") or "") == source_node_key), None)
        if source_row is None or self.scene_manager is None:
            return
        source_scene_ref = str(source_row.get("source_scene_ref", "") or source_row.get("source_scene_path", "") or source_row.get("source_scene_key", "") or "")
        source_entity_name = str(source_row.get("source_entity_name", "") or "")
        target_scene_ref = str(target_node.get("scene_ref", "") or "")
        target_entity_name = str(target_node.get("entity_name", "") or "") if str(target_node.get("kind", "")) == "entity" else ""
        target_scene_path = target_scene_ref if target_scene_ref.endswith(".json") else ""
        if not target_scene_path and self.project_service is not None and target_scene_ref:
            for scene_info in self.project_service.list_project_scenes():
                candidate = str(scene_info.get("path", "") or "")
                absolute = str(scene_info.get("absolute_path", "") or "")
                if target_scene_ref in {candidate, absolute, Path(absolute).resolve().as_posix() if absolute else ""}:
                    target_scene_path = candidate or absolute
                    break
        if not target_scene_path and target_scene_ref.endswith(".json"):
            target_scene_path = target_scene_ref
        self._set_scene_link_target(
            source_entity_name,
            target_scene_path,
            target_entity_name,
            str(source_row.get("target_entry_id", "") or ""),
            scene_ref=source_scene_ref,
        )
        if self.connection_mode == "two_way" and target_entity_name and target_scene_path:
            if not self._create_or_adopt_scene_link(target_entity_name, None, scene_ref=target_scene_ref):
                log_warn(f"Scene Flow: could not create reciprocal SceneLink for '{target_entity_name}'")
            else:
                reciprocal_scene_path = source_scene_ref if source_scene_ref.endswith(".json") else str(source_row.get("source_scene_path", "") or "")
                self._set_scene_link_target(target_entity_name, reciprocal_scene_path, source_entity_name, "", scene_ref=target_scene_ref)

    def _scene_link_payload(self, scene_ref: Optional[str], entity_name: str) -> Optional[dict[str, Any]]:
        if self.scene_manager is None:
            return None
        target_scene = str(scene_ref or self._active_scene_identity()[0] or self._active_scene_identity()[1] or "")
        payload = self.scene_manager.get_component_data_for_scene(target_scene, entity_name, "SceneLink")
        return dict(payload) if isinstance(payload, dict) else None

    def _create_or_adopt_scene_link(self, entity_name: str, runtime_payload: Optional[dict[str, Any]], *, scene_ref: Optional[str] = None) -> bool:
        if self.scene_manager is None:
            return False
        target_scene = str(scene_ref or self._active_scene_identity()[0] or self._active_scene_identity()[1] or "")
        entity_data = self.scene_manager.find_entity_data_for_scene(target_scene, entity_name)
        if entity_data is None:
            return False
        components = entity_data.get("components", {}) if isinstance(entity_data, dict) else {}
        button_payload = components.get("UIButton") if isinstance(components, dict) else None
        contact_payload = components.get("SceneTransitionOnContact") if isinstance(components, dict) else None
        interact_payload = components.get("SceneTransitionOnInteract") if isinstance(components, dict) else None
        mode = ""
        if isinstance(button_payload, dict):
            on_click = dict(button_payload.get("on_click", {}) or {})
            if str(on_click.get("type", "") or "").strip() == "run_scene_transition":
                mode = "ui_button"
        if not mode and isinstance(interact_payload, dict):
            mode = "interact_near"
        if not mode and isinstance(contact_payload, dict):
            mode = "collision" if str(contact_payload.get("mode", "") or "").strip() == "collision" else "trigger_enter"
        return bool(
            self.scene_manager.upsert_component_for_scene(
                target_scene,
                entity_name,
                "SceneLink",
                {
                    "enabled": True,
                    "target_path": str((runtime_payload or {}).get("target_scene_path", "") or ""),
                    "target_entity_name": "",
                    "flow_key": "",
                    "preview_label": "",
                    "link_mode": mode,
                    "target_entry_id": str((runtime_payload or {}).get("target_entry_id", "") or ""),
                },
            )
        )

    def _set_scene_link_mode(self, entity_name: str, mode: str, *, scene_ref: Optional[str] = None) -> bool:
        link = self._scene_link_payload(scene_ref, entity_name)
        if link is None:
            return False
        link["link_mode"] = str(mode or "").strip()
        if not self.scene_manager.upsert_component_for_scene(str(scene_ref or ""), entity_name, "SceneLink", link):
            return False
        return self._sync_runtime_from_scene_link(entity_name, scene_ref=scene_ref)

    def _set_scene_link_target_scene(self, entity_name: str, scene_path: str, *, scene_ref: Optional[str] = None) -> bool:
        link = self._scene_link_payload(scene_ref, entity_name)
        if link is None:
            return False
        normalized_path = str(scene_path or "").strip()
        link["target_path"] = normalized_path
        valid_entry_ids = {item["entry_id"] for item in self._list_entry_points_for_target(normalized_path)}
        current_entry_id = str(link.get("target_entry_id", "") or "").strip()
        if current_entry_id not in valid_entry_ids:
            link["target_entry_id"] = ""
        if not self.scene_manager.upsert_component_for_scene(str(scene_ref or ""), entity_name, "SceneLink", link):
            return False
        return self._sync_runtime_from_scene_link(entity_name, scene_ref=scene_ref)

    def _set_scene_link_target_spawn(self, entity_name: str, entry_id: str, *, scene_ref: Optional[str] = None) -> bool:
        link = self._scene_link_payload(scene_ref, entity_name)
        if link is None:
            return False
        link["target_entry_id"] = str(entry_id or "").strip()
        if not self.scene_manager.upsert_component_for_scene(str(scene_ref or ""), entity_name, "SceneLink", link):
            return False
        return self._sync_runtime_from_scene_link(entity_name, scene_ref=scene_ref)

    def _set_scene_link_target(
        self,
        entity_name: str,
        target_scene_path: str,
        target_entity_name: str,
        target_entry_id: str,
        *,
        scene_ref: Optional[str] = None,
    ) -> bool:
        link = self._scene_link_payload(scene_ref, entity_name)
        if link is None:
            return False
        link["target_path"] = str(target_scene_path or "").strip()
        link["target_entity_name"] = str(target_entity_name or "").strip()
        link["target_entry_id"] = str(target_entry_id or "").strip()
        if not self.scene_manager.upsert_component_for_scene(str(scene_ref or ""), entity_name, "SceneLink", link):
            return False
        return self._sync_runtime_from_scene_link(entity_name, scene_ref=scene_ref)

    def _sync_runtime_from_scene_link(self, entity_name: str, *, scene_ref: Optional[str] = None) -> bool:
        if self.scene_manager is None:
            return False
        target_scene = str(scene_ref or self._active_scene_identity()[0] or self._active_scene_identity()[1] or "")
        entity_data = self.scene_manager.find_entity_data_for_scene(target_scene, entity_name)
        link = self.scene_manager.get_component_data_for_scene(target_scene, entity_name, "SceneLink")
        if entity_data is None or not isinstance(link, dict):
            return False
        components = entity_data.get("components", {}) if isinstance(entity_data, dict) else {}
        link_mode = str(link.get("link_mode", "") or "").strip()
        target_path = str(link.get("target_path", "") or "").strip()
        target_entry_id = str(link.get("target_entry_id", "") or "").strip()
        button_payload = dict(components.get("UIButton", {}) or {}) if isinstance(components, dict) and isinstance(components.get("UIButton"), dict) else None
        collider_payload = dict(components.get("Collider", {}) or {}) if isinstance(components, dict) and isinstance(components.get("Collider"), dict) else None

        if not link_mode or not target_path:
            self.scene_manager.remove_component_for_scene(target_scene, entity_name, "SceneTransitionAction", record_history=False)
            self.scene_manager.remove_component_for_scene(target_scene, entity_name, "SceneTransitionOnContact", record_history=False)
            self.scene_manager.remove_component_for_scene(target_scene, entity_name, "SceneTransitionOnInteract", record_history=False)
            if button_payload is not None:
                on_click = dict(button_payload.get("on_click", {}) or {})
                if str(on_click.get("type", "") or "").strip() == "run_scene_transition":
                    button_payload["on_click"] = {"type": "emit_event", "name": "ui.button_clicked"}
                    self.scene_manager.upsert_component_for_scene(target_scene, entity_name, "UIButton", button_payload, record_history=False)
            return True

        if link_mode == "ui_button" and button_payload is None:
            return False
        if link_mode in {"interact_near", "trigger_enter"}:
            if collider_payload is None or not bool(collider_payload.get("is_trigger", False)):
                return False
        if link_mode == "collision" and collider_payload is None:
            return False

        if not self.scene_manager.upsert_component_for_scene(
            target_scene,
            entity_name,
            "SceneTransitionAction",
            {"enabled": True, "target_scene_path": target_path, "target_entry_id": target_entry_id},
            record_history=False,
        ):
            return False

        self.scene_manager.remove_component_for_scene(target_scene, entity_name, "SceneTransitionOnContact", record_history=False)
        self.scene_manager.remove_component_for_scene(target_scene, entity_name, "SceneTransitionOnInteract", record_history=False)

        if link_mode == "ui_button":
            if button_payload is None:
                return False
            button_payload["on_click"] = {"type": "run_scene_transition"}
            return bool(self.scene_manager.upsert_component_for_scene(target_scene, entity_name, "UIButton", button_payload, record_history=False))

        if button_payload is not None:
            on_click = dict(button_payload.get("on_click", {}) or {})
            if str(on_click.get("type", "") or "").strip() == "run_scene_transition":
                button_payload["on_click"] = {"type": "emit_event", "name": "ui.button_clicked"}
                self.scene_manager.upsert_component_for_scene(target_scene, entity_name, "UIButton", button_payload, record_history=False)

        if link_mode == "interact_near":
            return bool(
                self.scene_manager.upsert_component_for_scene(
                    target_scene,
                    entity_name,
                    "SceneTransitionOnInteract",
                    {"enabled": True, "require_player": True},
                    record_history=False,
                )
            )
        return bool(
            self.scene_manager.upsert_component_for_scene(
                target_scene,
                entity_name,
                "SceneTransitionOnContact",
                {
                    "enabled": True,
                    "mode": "collision" if link_mode == "collision" else "trigger_enter",
                    "require_player": True,
                },
                record_history=False,
            )
        )

    def _list_entry_points_for_target(self, target_scene_path: str) -> list[dict[str, str]]:
        source_path, _active_key = self._active_scene_identity()
        return list_scene_entry_points(source_path or None, str(target_scene_path or "").strip())

    def _draw_edge(self, edge: dict[str, Any]) -> None:
        source_rect = self._node_rects.get(str(edge.get("source_node_key", "") or ""))
        target_rect = self._node_rects.get(str(edge.get("target_node_key", "") or ""))
        if source_rect is None or target_rect is None:
            return
        color = self.TWO_WAY if str(edge.get("connection_type", "")) == "two_way" else self.ONE_WAY
        start = rl.Vector2(source_rect.x + source_rect.width, source_rect.y + (source_rect.height / 2))
        end = rl.Vector2(target_rect.x, target_rect.y + (target_rect.height / 2))
        if str(edge.get("connection_type", "")) == "two_way":
            self._draw_arrow(start, end, color, offset=5.0)
            self._draw_arrow(end, start, color, offset=-5.0)
        else:
            self._draw_arrow(start, end, color, offset=0.0)

    def _draw_arrow(self, start: rl.Vector2, end: rl.Vector2, color: rl.Color, *, offset: float) -> None:
        dx = end.x - start.x
        dy = end.y - start.y
        length = math.hypot(dx, dy)
        if length <= 0.001:
            return
        nx = dx / length
        ny = dy / length
        ox = -ny * offset
        oy = nx * offset
        sx = start.x + ox
        sy = start.y + oy
        ex = end.x + ox
        ey = end.y + oy
        rl.draw_line_ex(rl.Vector2(sx, sy), rl.Vector2(ex, ey), 3.0, color)
        arrow_size = 8.0
        left = rl.Vector2(ex - (nx * arrow_size) - (ny * (arrow_size * 0.45)), ey - (ny * arrow_size) + (nx * (arrow_size * 0.45)))
        right = rl.Vector2(ex - (nx * arrow_size) + (ny * (arrow_size * 0.45)), ey - (ny * arrow_size) - (nx * (arrow_size * 0.45)))
        rl.draw_triangle(rl.Vector2(ex, ey), left, right, color)

    def _draw_node(self, node: dict[str, Any]) -> None:
        rect = self._resolve_node_rect(node)
        node_key = str(node.get("node_key", "") or "")
        self._node_rects[node_key] = rect
        selected = node_key == self._selected_node_key
        bg = self.SELECTED_BG if selected else self.NODE_BG if str(node.get("kind", "")) == "entity" else self.TARGET_NODE_BG
        border = self._status_color(str(node.get("status", "ok")))
        rl.draw_rectangle_rec(rect, bg)
        rl.draw_rectangle_lines_ex(rect, 2, border if selected else self.BORDER_COLOR)
        rl.draw_text(self._truncate(str(node.get("label", "") or ""), 20), int(rect.x + 8), int(rect.y + 10), 11, self.TEXT_COLOR)
        rl.draw_text(self._truncate(str(node.get("scene_name", "") or ""), 24), int(rect.x + 8), int(rect.y + 28), 10, self.TEXT_DIM)
        handle = self._connector_rect(rect)
        rl.draw_circle(int(handle.x + handle.width / 2), int(handle.y + handle.height / 2), self.CONNECTOR_RADIUS, self.ACCENT)
        self._register_cursor_rect(rect)
        self._register_cursor_rect(handle)

    def _handle_canvas_interactions(self, nodes: list[dict[str, Any]], snapshot: dict[str, list[dict[str, Any]]]) -> None:
        mouse = rl.get_mouse_position()
        for node in nodes:
            rect = self._node_rects.get(str(node.get("node_key", "") or ""))
            if rect is None:
                continue
            connector = self._connector_rect(rect)
            node_key = str(node.get("node_key", "") or "")
            if rl.check_collision_point_rec(mouse, connector) and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._connecting_from_node_key = node_key
                self._selected_node_key = node_key
                return
            if rl.check_collision_point_rec(mouse, rect) and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._selected_node_key = node_key
                self._selected_sidebar_key = self._sidebar_key_for_node(node_key, snapshot)
                self._drag_node_key = node_key
                self._drag_offset = rl.Vector2(mouse.x - rect.x, mouse.y - rect.y)
                if str(node.get("kind", "")) == "entity":
                    self.request_open_source = {
                        "scene_ref": str(node.get("scene_ref", "") or ""),
                        "entity_name": str(node.get("entity_name", "") or ""),
                    }
                elif str(node.get("scene_ref", "") or ""):
                    self.request_open_target = {"scene_ref": str(node.get("scene_ref", "") or "")}
                return

        if self._drag_node_key and rl.is_mouse_button_down(rl.MOUSE_BUTTON_LEFT):
            node = next((item for item in nodes if str(item.get("node_key", "")) == self._drag_node_key), None)
            if node is not None:
                self._persist_node_position(node, mouse.x - self._drag_offset.x, mouse.y - self._drag_offset.y)
                self.refresh(force=True)
            return

        if self._drag_node_key and rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
            self._drag_node_key = ""

        if self._connecting_from_node_key and rl.is_mouse_button_released(rl.MOUSE_BUTTON_LEFT):
            target = next(
                (
                    item
                    for item in nodes
                    if str(item.get("node_key", "") or "") != self._connecting_from_node_key
                    and rl.check_collision_point_rec(mouse, self._node_rects.get(str(item.get("node_key", "") or ""), rl.Rectangle(0, 0, 0, 0)))
                ),
                None,
            )
            if target is not None:
                self._apply_connection(self._connecting_from_node_key, target, snapshot)
                self.refresh(force=True)
            self._connecting_from_node_key = ""
            return

        if self._connecting_from_node_key:
            source_rect = self._node_rects.get(self._connecting_from_node_key)
            if source_rect is not None:
                source = rl.Vector2(source_rect.x + source_rect.width, source_rect.y + source_rect.height / 2)
                self._draw_arrow(source, mouse, self.ACCENT, offset=0.0)

    def _resolve_node_rect(self, node: dict[str, Any]) -> rl.Rectangle:
        x = float(node.get("_draw_x", node.get("x", 0.0)) or 0.0)
        y = float(node.get("_draw_y", node.get("y", 0.0)) or 0.0)
        return rl.Rectangle(x, y, self.NODE_WIDTH, self.NODE_HEIGHT)

    def _connector_rect(self, rect: rl.Rectangle) -> rl.Rectangle:
        size = float(self.CONNECTOR_RADIUS * 2)
        return rl.Rectangle(rect.x + rect.width - (size + 6), rect.y + (rect.height / 2) - self.CONNECTOR_RADIUS, size, size)

    def _place_default_nodes(self, nodes: list[dict[str, Any]]) -> None:
        entity_index = 0
        target_index = 0
        canvas_left = self._canvas_rect.x + 18
        canvas_top = self._canvas_rect.y + 40
        canvas_right = self._canvas_rect.x + self._canvas_rect.width - self.NODE_WIDTH - 18
        for node in nodes:
            if bool(node.get("has_stored_position", False)):
                node["_draw_x"] = self._clamp_x(float(node.get("x", 0.0) or 0.0))
                node["_draw_y"] = self._clamp_y(float(node.get("y", 0.0) or 0.0))
                continue
            if str(node.get("kind", "")) == "entity":
                row = entity_index // 2
                col = entity_index % 2
                node["_draw_x"] = self._clamp_x(canvas_left + (col * 230))
                node["_draw_y"] = self._clamp_y(canvas_top + (row * 92))
                entity_index += 1
            else:
                row = target_index // 2
                col = target_index % 2
                node["_draw_x"] = self._clamp_x(max(canvas_left + 280, canvas_right - (col * 210)))
                node["_draw_y"] = self._clamp_y(canvas_top + (row * 92))
                target_index += 1

    def _clamp_x(self, x: float) -> float:
        return min(max(self._canvas_rect.x + 12, x), self._canvas_rect.x + self._canvas_rect.width - self.NODE_WIDTH - 12)

    def _clamp_y(self, y: float) -> float:
        return min(max(self._canvas_rect.y + 32, y), self._canvas_rect.y + self._canvas_rect.height - self.NODE_HEIGHT - 12)

    def _register_cursor_rect(self, rect: rl.Rectangle) -> None:
        self._cursor_interactive_rects.append(rl.Rectangle(rect.x, rect.y, rect.width, rect.height))

    @staticmethod
    def _truncate(value: str, max_len: int) -> str:
        text = str(value or "")
        if len(text) <= max_len:
            return text
        if max_len <= 3:
            return text[:max_len]
        return f"{text[: max_len - 3]}..."
