from __future__ import annotations

import time
from typing import Any, Optional

import pyray as rl

from engine.components.collider import Collider
from engine.components.uibutton import UIButton
from engine.editor.console_panel import log_err
from engine.editor.cursor_manager import CursorVisualState
from engine.scenes.scene_transition_support import collect_project_scene_links, list_scene_entry_points


class SceneFlowPanel:
    """Authoring-first scene link panel."""

    BG_COLOR = rl.Color(32, 32, 32, 255)
    HEADER_COLOR = rl.Color(56, 56, 56, 255)
    BORDER_COLOR = rl.Color(25, 25, 25, 255)
    SECTION_BG = rl.Color(36, 36, 36, 255)
    SECTION_BODY_BG = rl.Color(40, 40, 40, 255)
    ROW_ALT_COLOR = rl.Color(38, 38, 38, 255)
    ROW_HOVER_COLOR = rl.Color(60, 60, 60, 255)
    TEXT_COLOR = rl.Color(210, 210, 210, 255)
    TEXT_DIM = rl.Color(140, 140, 140, 255)
    STATUS_OK = rl.Color(72, 122, 82, 255)
    STATUS_WARN = rl.Color(138, 116, 52, 255)
    STATUS_ERR = rl.Color(140, 64, 64, 255)
    TAB_LINE = rl.Color(58, 121, 187, 255)

    TOOLBAR_HEIGHT = 24
    HEADER_HEIGHT = 24
    EDITOR_MIN_WIDTH = 320
    SUMMARY_HEIGHT = 0
    SUMMARY_ROW_HEIGHT = 20
    SECTION_HEADER_HEIGHT = 20
    LIST_HEADER_HEIGHT = 36
    LIST_ROW_HEIGHT = 34
    PANEL_PADDING = 6
    SUMMARY_MIN_BODY_HEIGHT = 40
    ACTION_BUTTON_WIDTH = 42
    ACTION_BUTTON_GAP = 6

    def __init__(self) -> None:
        self.project_service: Any = None
        self.scene_manager: Any = None
        self.only_problems: bool = False
        self.current_scene_only: bool = True
        self.summary_scroll: float = 0.0
        self.list_scroll: float = 0.0
        self.request_open_source: Optional[dict[str, str]] = None
        self.request_open_target: Optional[dict[str, str]] = None
        self._snapshot: dict[str, list[dict[str, Any]]] = {"rows": [], "issues": []}
        self._last_refresh_time: float = 0.0
        self._selected_row_key: str = ""
        self._last_render_error: str = ""
        self._cursor_interactive_rects: list[rl.Rectangle] = []
        self._panel_rect = rl.Rectangle(0, 0, 0, 0)
        self._toolbar_rect = rl.Rectangle(0, 0, 0, 0)
        self._list_rect = rl.Rectangle(0, 0, 0, 0)
        self._list_header_rect = rl.Rectangle(0, 0, 0, 0)
        self._list_body_rect = rl.Rectangle(0, 0, 0, 0)
        self._editor_rect = rl.Rectangle(0, 0, 0, 0)
        self._editor_header_rect = rl.Rectangle(0, 0, 0, 0)
        self._editor_body_rect = rl.Rectangle(0, 0, 0, 0)
        self._detail_columns: dict[str, rl.Rectangle] = {}

    def set_project_service(self, project_service: Any) -> None:
        self.project_service = project_service
        self.refresh(force=True)

    def set_scene_manager(self, scene_manager: Any) -> None:
        self.scene_manager = scene_manager
        self.refresh(force=True)

    def refresh(self, *, force: bool = False) -> dict[str, list[dict[str, Any]]]:
        now = time.monotonic()
        if not force and (now - self._last_refresh_time) < 0.25:
            return self._snapshot
        self._snapshot = collect_project_scene_links(self.project_service, self.scene_manager)
        self._last_refresh_time = now
        return self._snapshot

    def render(self, x: int, y: int, width: int, height: int) -> None:
        self._cursor_interactive_rects = []
        self._detail_columns = {}
        panel_rect = rl.Rectangle(float(x), float(y), float(max(0, width)), float(max(0, height)))
        self._panel_rect = panel_rect
        rl.draw_rectangle_rec(panel_rect, self.BG_COLOR)
        try:
            snapshot = self.refresh()
            self._layout_panel_rects(panel_rect)
            self._clamp_scroll_ranges(snapshot)
            self._handle_scroll()
            self._ensure_visible_selection(snapshot)
            self._draw_toolbar(self._toolbar_rect)
            self._draw_rows_list(snapshot, self._list_rect)
            self._draw_link_editor(snapshot, self._editor_rect)
            self._last_render_error = ""
        except Exception as exc:
            self._last_render_error = str(exc)
            log_err(f"Scene Flow render error: {exc}")
            self._draw_toolbar(rl.Rectangle(panel_rect.x + self.PANEL_PADDING, panel_rect.y + self.PANEL_PADDING, max(0.0, panel_rect.width - (self.PANEL_PADDING * 2)), self.TOOLBAR_HEIGHT))
            self._draw_error_fallback(panel_rect, self._last_render_error)
        rl.draw_rectangle_lines_ex(panel_rect, 1, self.BORDER_COLOR)

    def _clamp_scroll_ranges(self, snapshot: dict[str, list[dict[str, Any]]]) -> None:
        details_rows = len(self._filtered_items(snapshot))
        details_content = max(0.0, float(details_rows * self.LIST_ROW_HEIGHT))
        self.list_scroll = min(max(0.0, details_content - self._list_body_rect.height), max(0.0, self.list_scroll))

    def get_cursor_intent(self, mouse_pos: Optional[rl.Vector2] = None) -> CursorVisualState:
        mouse = rl.get_mouse_position() if mouse_pos is None else mouse_pos
        for rect in self._cursor_interactive_rects:
            if rl.check_collision_point_rec(mouse, rect):
                return CursorVisualState.INTERACTIVE
        return CursorVisualState.DEFAULT

    def _layout_panel_rects(self, panel_rect: rl.Rectangle) -> None:
        inner_x = panel_rect.x + self.PANEL_PADDING
        inner_y = panel_rect.y + self.PANEL_PADDING
        inner_width = max(0.0, panel_rect.width - (self.PANEL_PADDING * 2))
        inner_height = max(0.0, panel_rect.height - (self.PANEL_PADDING * 2))

        toolbar_height = min(float(self.TOOLBAR_HEIGHT), inner_height)
        self._toolbar_rect = rl.Rectangle(inner_x, inner_y, inner_width, toolbar_height)

        body_y = inner_y + toolbar_height + self.PANEL_PADDING
        body_height = max(0.0, inner_height - toolbar_height - self.PANEL_PADDING)
        list_width = max(260.0, inner_width * 0.56)
        editor_width = max(self.EDITOR_MIN_WIDTH, inner_width - list_width - self.PANEL_PADDING)
        if list_width + editor_width + self.PANEL_PADDING > inner_width:
            editor_width = max(220.0, inner_width * 0.38)
            list_width = max(220.0, inner_width - editor_width - self.PANEL_PADDING)

        self._list_rect = rl.Rectangle(inner_x, body_y, max(0.0, list_width), body_height)
        self._list_header_rect = rl.Rectangle(self._list_rect.x, self._list_rect.y, self._list_rect.width, min(float(self.LIST_HEADER_HEIGHT), self._list_rect.height))
        self._list_body_rect = rl.Rectangle(
            self._list_rect.x,
            self._list_rect.y + self._list_header_rect.height,
            self._list_rect.width,
            max(0.0, self._list_rect.height - self._list_header_rect.height),
        )

        editor_x = self._list_rect.x + self._list_rect.width + self.PANEL_PADDING
        self._editor_rect = rl.Rectangle(editor_x, body_y, max(0.0, inner_width - self._list_rect.width - self.PANEL_PADDING), body_height)
        self._editor_header_rect = rl.Rectangle(self._editor_rect.x, self._editor_rect.y, self._editor_rect.width, min(float(self.HEADER_HEIGHT), self._editor_rect.height))
        self._editor_body_rect = rl.Rectangle(
            self._editor_rect.x,
            self._editor_rect.y + self._editor_header_rect.height,
            self._editor_rect.width,
            max(0.0, self._editor_rect.height - self._editor_header_rect.height),
        )
        self._detail_columns = self._compute_detail_columns(self._list_header_rect)

    def _draw_toolbar(self, rect: rl.Rectangle) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        x = int(rect.x)
        y = int(rect.y)
        width = int(rect.width)
        rl.draw_rectangle_rec(rect, self.HEADER_COLOR)
        rl.draw_line(x, y + int(rect.height) - 1, x + width, y + int(rect.height) - 1, self.BORDER_COLOR)
        rl.draw_text("Scene Flow", x + 10, y + 6, 11, self.TEXT_COLOR)

        control_specs = [("only", 102.0), ("current", 120.0), ("refresh", 64.0)]
        available_width = max(120.0, rect.width - 132.0)
        desired_width = sum(width for _, width in control_specs) + (self.ACTION_BUTTON_GAP * (len(control_specs) - 1))
        scale = min(1.0, available_width / desired_width) if desired_width > 0 else 1.0
        control_widths = {
            name: max(54.0 if name == "refresh" else 72.0, desired * scale)
            for name, desired in control_specs
        }
        total_control_width = sum(control_widths.values()) + (self.ACTION_BUTTON_GAP * (len(control_specs) - 1))
        start_x = max(rect.x + 10.0, rect.x + rect.width - total_control_width - 10.0)
        only_rect = rl.Rectangle(start_x, rect.y + 2.0, control_widths["only"], 20.0)
        current_rect = rl.Rectangle(only_rect.x + only_rect.width + self.ACTION_BUTTON_GAP, rect.y + 2.0, control_widths["current"], 20.0)
        refresh_rect = rl.Rectangle(current_rect.x + current_rect.width + self.ACTION_BUTTON_GAP, rect.y + 2.0, control_widths["refresh"], 20.0)
        self._register_cursor_rect(refresh_rect)
        self._register_cursor_rect(only_rect)
        self._register_cursor_rect(current_rect)
        self.only_problems = rl.gui_toggle(only_rect, "Only problems", self.only_problems)
        self.current_scene_only = rl.gui_toggle(current_rect, "Current scene only", self.current_scene_only)
        if rl.gui_button(refresh_rect, "Refresh"):
            self.refresh(force=True)

    def _draw_rows_list(self, snapshot: dict[str, list[dict[str, Any]]], rect: rl.Rectangle) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        rl.draw_rectangle_rec(rect, self.SECTION_BG)
        rl.draw_rectangle_rec(self._list_header_rect, self.HEADER_COLOR)
        items = self._filtered_items(snapshot)
        all_authoring_rows = [item for item in snapshot.get("rows", []) if bool(item.get("is_authoring_row", False))]
        title_y = int(self._list_header_rect.y + 4)
        columns_y = int(self._list_header_rect.y + 20)
        rl.draw_text("Scene Links", int(self._list_header_rect.x + 10), title_y, 11, self.TEXT_COLOR)
        rl.draw_text(
            f"{len(items)} visible / {len(all_authoring_rows)} total",
            int(self._list_header_rect.x + self._list_header_rect.width - 130),
            title_y,
            10,
            self.TEXT_DIM,
        )
        for label, column_rect in self._detail_columns.items():
            rl.draw_text(label, int(column_rect.x + 6), columns_y, 10, self.TEXT_COLOR)
        rl.draw_rectangle_rec(self._list_body_rect, self.SECTION_BODY_BG)
        rl.draw_rectangle_lines_ex(rect, 1, self.BORDER_COLOR)
        if not items:
            rl.draw_text("No SceneLink entities found in this view.", int(self._list_body_rect.x + 12), int(self._list_body_rect.y + 12), 11, self.TEXT_DIM)
            if all_authoring_rows and self.current_scene_only:
                rl.draw_text("This scene has no visible links with the current filter. Disable Current scene only to inspect the full project.", int(self._list_body_rect.x + 12), int(self._list_body_rect.y + 28), 11, self.TEXT_DIM)
            else:
                rl.draw_text("Select an entity and use Add from selected, or disable Current scene only.", int(self._list_body_rect.x + 12), int(self._list_body_rect.y + 28), 11, self.TEXT_DIM)
            return

        row_y = int(self._list_body_rect.y - self.list_scroll)
        visible_bottom = self._list_body_rect.y + self._list_body_rect.height
        for index, item in enumerate(items):
            row_rect = rl.Rectangle(self._list_body_rect.x + 4.0, float(row_y), max(0.0, self._list_body_rect.width - 8.0), float(self.LIST_ROW_HEIGHT - 2))
            if row_rect.y + row_rect.height < self._list_body_rect.y:
                row_y += self.LIST_ROW_HEIGHT
                continue
            if row_rect.y > visible_bottom:
                break
            row_key = self._row_key(item)
            hover = rl.check_collision_point_rec(rl.get_mouse_position(), row_rect)
            selected = row_key == self._selected_row_key
            row_color = self.ROW_HOVER_COLOR if hover or selected else self.ROW_ALT_COLOR if index % 2 == 0 else self.BG_COLOR
            rl.draw_rectangle_rec(row_rect, row_color)
            self._register_cursor_rect(row_rect)

            action_area_width = float((self.ACTION_BUTTON_WIDTH * 2) + self.ACTION_BUTTON_GAP + 4)
            content_width = max(0.0, row_rect.width - action_area_width)
            columns = self._compute_detail_columns(rl.Rectangle(row_rect.x, row_rect.y, content_width, row_rect.height))
            status_rect = columns["Status"]
            self._draw_cell_text(columns["From Scene"], str(item.get("source_scene_name", "")), row_rect.y + 5, self.TEXT_COLOR)
            self._draw_cell_text(columns["Entity"], str(item.get("source_entity_name", "") or "-"), row_rect.y + 5, self.TEXT_COLOR)
            self._draw_cell_text(columns["Trigger"], str(item.get("trigger_label", "") or "-"), row_rect.y + 5, self.TEXT_COLOR)
            self._draw_cell_text(columns["To Scene"], str(item.get("target_scene_name", "") or item.get("target_scene_path", "") or "-"), row_rect.y + 5, self.TEXT_COLOR)
            self._draw_cell_text(columns["Spawn"], str(item.get("target_entry_id", "") or "-"), row_rect.y + 5, self.TEXT_COLOR)
            self._draw_status_badge(int(status_rect.x + 4), int(row_rect.y + 3), max(42, int(status_rect.width - 8)), 16, str(item.get("status", "ok")).upper(), str(item.get("status", "ok")))
            meta = "SceneLink" if item.get("has_scene_link", False) else "runtime-only"
            rl.draw_text(self._truncate(meta, 28), int(row_rect.x + 6), int(row_rect.y + 20), 10, self.TEXT_DIM)

            source_rect = rl.Rectangle(row_rect.x + row_rect.width - ((self.ACTION_BUTTON_WIDTH * 2) + self.ACTION_BUTTON_GAP + 4), row_rect.y + 6, self.ACTION_BUTTON_WIDTH, 18)
            target_rect = rl.Rectangle(source_rect.x + self.ACTION_BUTTON_WIDTH + self.ACTION_BUTTON_GAP, row_rect.y + 6, self.ACTION_BUTTON_WIDTH, 18)
            self._register_cursor_rect(source_rect)
            if bool(item.get("can_open_target", False)):
                self._register_cursor_rect(target_rect)
            if hover and rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
                self._selected_row_key = row_key
            if rl.gui_button(source_rect, "Src"):
                self.request_open_source = {
                    "scene_ref": str(item.get("source_scene_ref", "") or item.get("source_scene_path", "") or item.get("source_scene_key", "") or ""),
                    "entity_name": str(item.get("source_entity_name", "") or ""),
                }
            if bool(item.get("can_open_target", False)) and rl.gui_button(target_rect, "Dst"):
                self.request_open_target = {"scene_ref": str(item.get("target_scene_ref", "") or item.get("target_scene_path", "") or "")}
            row_y += self.LIST_ROW_HEIGHT

    def _draw_link_editor(self, snapshot: dict[str, list[dict[str, Any]]], rect: rl.Rectangle) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        rl.draw_rectangle_rec(rect, self.SECTION_BG)
        rl.draw_rectangle_rec(self._editor_header_rect, self.HEADER_COLOR)
        rl.draw_text("Connection Editor", int(self._editor_header_rect.x + 10), int(self._editor_header_rect.y + 6), 10, self.TEXT_COLOR)
        rl.draw_rectangle_rec(self._editor_body_rect, self.SECTION_BODY_BG)
        rl.draw_rectangle_lines_ex(rect, 1, self.BORDER_COLOR)

        active_scene = self.scene_manager.get_active_scene_summary() if self.scene_manager is not None and hasattr(self.scene_manager, "get_active_scene_summary") else {}
        edit_world = self.scene_manager.get_edit_world() if self.scene_manager is not None and hasattr(self.scene_manager, "get_edit_world") else None
        selected_entity_name = str(getattr(edit_world, "selected_entity_name", "") or "").strip() if edit_world is not None else ""
        row = self._resolve_editor_row(snapshot)
        body_x = int(self._editor_body_rect.x + 10)
        body_y = int(self._editor_body_rect.y + 10)

        if row is None:
            rl.draw_text("Select a SceneLink row or pick an entity in the scene.", body_x, body_y, 11, self.TEXT_COLOR)
            if selected_entity_name:
                rl.draw_text(f"Selected in scene: {selected_entity_name}", body_x, body_y + 18, 11, self.TEXT_DIM)
                add_rect = rl.Rectangle(self._editor_body_rect.x + 10, self._editor_body_rect.y + 42, 136, 20)
                self._register_cursor_rect(add_rect)
                runtime_payload = self._current_component_payload(selected_entity_name, "SceneTransitionAction")
                if rl.gui_button(add_rect, "Add from selected" if runtime_payload is None else "Adopt runtime"):
                    self._create_or_adopt_scene_link(selected_entity_name, runtime_payload)
                    self.refresh(force=True)
            else:
                rl.draw_text("No entity selected. Pick an object in the scene to create a new SceneLink.", body_x, body_y + 18, 11, self.TEXT_DIM)
            return

        row_scene_ref = str(row.get("source_scene_ref", "") or row.get("source_scene_path", "") or row.get("source_scene_key", "") or "")
        entity_name = str(row.get("source_entity_name", "") or "")
        is_active_scene_row = row_scene_ref == str(active_scene.get("path", "") or active_scene.get("key", "") or "")
        rl.draw_text(f"Scene: {row.get('source_scene_name', '')}", body_x, body_y, 11, self.TEXT_COLOR)
        rl.draw_text(f"Entity: {entity_name}", body_x, body_y + 18, 11, self.TEXT_COLOR)

        if not is_active_scene_row:
            rl.draw_text("Open the source scene to edit this link.", body_x, body_y + 44, 11, self.TEXT_DIM)
            open_rect = rl.Rectangle(self._editor_body_rect.x + 10, self._editor_body_rect.y + 68, 110, 20)
            self._register_cursor_rect(open_rect)
            if rl.gui_button(open_rect, "Open source"):
                self.request_open_source = {"scene_ref": row_scene_ref, "entity_name": entity_name}
            return

        if edit_world is None:
            rl.draw_text("No edit world available.", body_x, body_y + 44, 11, self.TEXT_DIM)
            return
        entity = edit_world.get_entity_by_name(entity_name)
        if entity is None:
            rl.draw_text("Entity is not available in the active edit world.", body_x, body_y + 44, 11, self.TEXT_DIM)
            return

        link_payload = self._current_component_payload(entity_name, "SceneLink")
        runtime_payload = self._current_component_payload(entity_name, "SceneTransitionAction")
        if link_payload is None:
            adopt_rect = rl.Rectangle(self._editor_body_rect.x + 10, self._editor_body_rect.y + 44, 120, 20)
            self._register_cursor_rect(adopt_rect)
            if rl.gui_button(adopt_rect, "Adopt runtime"):
                self._create_or_adopt_scene_link(entity_name, runtime_payload)
                self.refresh(force=True)
            return

        mode_options = self._get_mode_options(entity)
        current_mode = str(link_payload.get("link_mode", "") or "").strip()
        target_scene = str(link_payload.get("target_path", "") or "").strip()
        target_entry_id = str(link_payload.get("target_entry_id", "") or "").strip()
        row1 = self._editor_body_rect.y + 48
        row2 = row1 + 24
        row3 = row2 + 24
        field_width = max(140.0, self._editor_body_rect.width - 106.0)
        rl.draw_text("Trigger", body_x, int(row1 + 4), 10, self.TEXT_COLOR)
        rl.draw_text("Target", body_x, int(row2 + 4), 10, self.TEXT_COLOR)
        rl.draw_text("Spawn", body_x, int(row3 + 4), 10, self.TEXT_COLOR)
        self._draw_cycle_field(rl.Rectangle(self._editor_body_rect.x + 80, row1, field_width, 18), mode_options, current_mode, lambda value: self._set_scene_link_mode(entity_name, value))
        self._draw_cycle_field(rl.Rectangle(self._editor_body_rect.x + 80, row2, field_width, 18), self._scene_options(target_scene), target_scene, lambda value: self._set_scene_link_target_scene(entity_name, value))
        self._draw_cycle_field(rl.Rectangle(self._editor_body_rect.x + 80, row3, field_width, 18), self._spawn_options(target_scene, target_entry_id), target_entry_id, lambda value: self._set_scene_link_target_spawn(entity_name, value))

        focus_rect = rl.Rectangle(self._editor_body_rect.x + 10, self._editor_body_rect.y + self._editor_body_rect.height - 24, 86, 18)
        target_rect = rl.Rectangle(focus_rect.x + 92, focus_rect.y, 86, 18)
        self._register_cursor_rect(focus_rect)
        self._register_cursor_rect(target_rect)
        if rl.gui_button(focus_rect, "Focus entity"):
            self.request_open_source = {"scene_ref": row_scene_ref, "entity_name": entity_name}
        if rl.gui_button(target_rect, "Open target") and target_scene:
            self.request_open_target = {"scene_ref": target_scene}

        warning_y = int(self._editor_body_rect.y + self._editor_body_rect.height - 48)
        for message in self._get_link_messages(entity, link_payload, snapshot)[:3]:
            rl.draw_text(self._truncate(message, max(30, int(self._editor_body_rect.width / 7.0))), body_x, warning_y, 10, self.TEXT_DIM)
            warning_y += 12

    def _draw_error_fallback(self, panel_rect: rl.Rectangle, message: str) -> None:
        body_rect = rl.Rectangle(panel_rect.x + self.PANEL_PADDING, panel_rect.y + self.TOOLBAR_HEIGHT + (self.PANEL_PADDING * 2), max(0.0, panel_rect.width - (self.PANEL_PADDING * 2)), max(0.0, panel_rect.height - self.TOOLBAR_HEIGHT - (self.PANEL_PADDING * 3)))
        rl.draw_rectangle_rec(body_rect, rl.Color(54, 34, 34, 255))
        rl.draw_rectangle_lines_ex(body_rect, 1, self.STATUS_ERR)
        rl.draw_text("Flow could not render this frame.", int(body_rect.x + 12), int(body_rect.y + 12), 12, self.TEXT_COLOR)
        rl.draw_text(self._truncate(message, max(40, int(body_rect.width / 6.5))), int(body_rect.x + 12), int(body_rect.y + 32), 10, self.TEXT_DIM)

    def _draw_cycle_field(
        self,
        rect: rl.Rectangle,
        options: list[tuple[str, str]],
        current_key: str,
        on_select: Any,
    ) -> None:
        if rect.width <= 0 or rect.height <= 0 or not options:
            return
        keys = [key for key, _ in options]
        current_index = keys.index(current_key) if current_key in keys else 0
        left_rect = rl.Rectangle(rect.x, rect.y, 18, rect.height)
        value_rect = rl.Rectangle(rect.x + 20, rect.y, max(0.0, rect.width - 40), rect.height)
        right_rect = rl.Rectangle(rect.x + rect.width - 18, rect.y, 18, rect.height)
        self._register_cursor_rect(left_rect)
        self._register_cursor_rect(value_rect)
        self._register_cursor_rect(right_rect)
        rl.draw_rectangle_rec(value_rect, rl.Color(42, 42, 42, 255))
        rl.draw_text(options[current_index][1], int(value_rect.x + 4), int(value_rect.y + 4), 10, self.TEXT_COLOR)
        if rl.gui_button(left_rect, "<") and current_index > 0:
            on_select(options[current_index - 1][0])
            self.refresh(force=True)
        if rl.gui_button(right_rect, ">") and current_index < len(options) - 1:
            on_select(options[current_index + 1][0])
            self.refresh(force=True)

    def _handle_scroll(self) -> None:
        mouse = rl.get_mouse_position()
        wheel = rl.get_mouse_wheel_move()
        if wheel == 0:
            return
        if rl.check_collision_point_rec(mouse, self._list_rect):
            self.list_scroll = max(0.0, self.list_scroll - (wheel * 28.0))

    def _ensure_visible_selection(self, snapshot: dict[str, list[dict[str, Any]]]) -> None:
        items = self._filtered_items(snapshot)
        if not items:
            self._selected_row_key = ""
            return
        keys = [self._row_key(item) for item in items]
        if self._selected_row_key in keys:
            return
        edit_world = self.scene_manager.get_edit_world() if self.scene_manager is not None and hasattr(self.scene_manager, "get_edit_world") else None
        selected_entity = str(getattr(edit_world, "selected_entity_name", "") or "").strip() if edit_world is not None else ""
        active_path, active_key = self._active_scene_identity()
        if selected_entity:
            for item in items:
                same_scene = str(item.get("source_scene_path", "") or "") == active_path or str(item.get("source_scene_key", "") or "") == active_key
                if same_scene and str(item.get("source_entity_name", "") or "") == selected_entity:
                    self._selected_row_key = self._row_key(item)
                    return
        self._selected_row_key = keys[0]

    def _resolve_editor_row(self, snapshot: dict[str, list[dict[str, Any]]]) -> Optional[dict[str, Any]]:
        items = self._filtered_items(snapshot)
        for item in items:
            if self._row_key(item) == self._selected_row_key:
                return item
        return items[0] if items else None

    def _row_key(self, item: dict[str, Any]) -> str:
        return f"{str(item.get('source_scene_ref', '') or item.get('source_scene_path', '') or item.get('source_scene_key', ''))}::{str(item.get('source_entity_name', '') or '')}"

    def _current_component_payload(self, entity_name: str, component_name: str) -> Optional[dict[str, Any]]:
        if self.scene_manager is None or not hasattr(self.scene_manager, "current_scene") or self.scene_manager.current_scene is None:
            return None
        entity_data = self.scene_manager.current_scene.find_entity(entity_name)
        if not isinstance(entity_data, dict):
            return None
        components = entity_data.get("components", {})
        if not isinstance(components, dict):
            return None
        payload = components.get(component_name)
        return dict(payload) if isinstance(payload, dict) else None

    def _upsert_component(self, entity_name: str, component_name: str, payload: dict[str, Any]) -> bool:
        current = self._current_component_payload(entity_name, component_name)
        if current is None:
            return bool(self.scene_manager.add_component_to_entity(entity_name, component_name, dict(payload)))
        return bool(self.scene_manager.replace_component_data(entity_name, component_name, dict(payload)))

    def _remove_component(self, entity_name: str, component_name: str) -> bool:
        if self._current_component_payload(entity_name, component_name) is None:
            return False
        return bool(self.scene_manager.remove_component_from_entity(entity_name, component_name))

    def _create_or_adopt_scene_link(self, entity_name: str, runtime_payload: Optional[dict[str, Any]]) -> bool:
        entity = self.scene_manager.get_edit_world().get_entity_by_name(entity_name) if self.scene_manager is not None and hasattr(self.scene_manager, "get_edit_world") else None
        if entity is None:
            return False
        mode = ""
        if entity.get_component(UIButton) is not None:
            button_payload = self._current_component_payload(entity_name, "UIButton") or {}
            on_click = dict(button_payload.get("on_click", {}) or {})
            if str(on_click.get("type", "") or "").strip() == "run_scene_transition":
                mode = "ui_button"
        contact_payload = self._current_component_payload(entity_name, "SceneTransitionOnContact") or {}
        if not mode and contact_payload:
            mode = "collision" if str(contact_payload.get("mode", "") or "").strip() == "collision" else "trigger_enter"
        target_path = str((runtime_payload or {}).get("target_scene_path", "") or "")
        target_entry_id = str((runtime_payload or {}).get("target_entry_id", "") or "")
        return self._upsert_component(
            entity_name,
            "SceneLink",
            {
                "enabled": True,
                "target_path": target_path,
                "flow_key": "",
                "preview_label": "",
                "link_mode": mode,
                "target_entry_id": target_entry_id,
            },
        )

    def _set_scene_link_mode(self, entity_name: str, mode: str) -> bool:
        link = self._current_component_payload(entity_name, "SceneLink") or {}
        link.update({"enabled": True, "link_mode": str(mode or "").strip()})
        if not self._upsert_component(entity_name, "SceneLink", link):
            return False
        return self._sync_runtime_from_scene_link(entity_name)

    def _set_scene_link_target_scene(self, entity_name: str, scene_path: str) -> bool:
        normalized_path = str(scene_path or "").strip()
        link = self._current_component_payload(entity_name, "SceneLink") or {}
        current_entry_id = str(link.get("target_entry_id", "") or "").strip()
        valid_entry_ids = {item["entry_id"] for item in self._list_entry_points_for_target(normalized_path)}
        link.update(
            {
                "enabled": True,
                "target_path": normalized_path,
                "target_entry_id": current_entry_id if current_entry_id in valid_entry_ids else "",
            }
        )
        if not self._upsert_component(entity_name, "SceneLink", link):
            return False
        return self._sync_runtime_from_scene_link(entity_name)

    def _set_scene_link_target_spawn(self, entity_name: str, entry_id: str) -> bool:
        link = self._current_component_payload(entity_name, "SceneLink") or {}
        link.update({"enabled": True, "target_entry_id": str(entry_id or "").strip()})
        if not self._upsert_component(entity_name, "SceneLink", link):
            return False
        return self._sync_runtime_from_scene_link(entity_name)

    def _sync_runtime_from_scene_link(self, entity_name: str) -> bool:
        edit_world = self.scene_manager.get_edit_world() if self.scene_manager is not None and hasattr(self.scene_manager, "get_edit_world") else None
        entity = edit_world.get_entity_by_name(entity_name) if edit_world is not None else None
        link = self._current_component_payload(entity_name, "SceneLink")
        if entity is None or link is None:
            return False
        mode = str(link.get("link_mode", "") or "").strip()
        target_path = str(link.get("target_path", "") or "").strip()
        target_entry_id = str(link.get("target_entry_id", "") or "").strip()
        if not mode or not target_path:
            self._remove_component(entity_name, "SceneTransitionAction")
            self._remove_component(entity_name, "SceneTransitionOnContact")
            button_payload = self._current_component_payload(entity_name, "UIButton")
            if button_payload is not None:
                on_click = dict(button_payload.get("on_click", {}) or {})
                if str(on_click.get("type", "") or "").strip() == "run_scene_transition":
                    button_payload["on_click"] = {"type": "emit_event", "name": "ui.button_clicked"}
                    self._upsert_component(entity_name, "UIButton", button_payload)
            return True
        if mode == "ui_button" and entity.get_component(UIButton) is None:
            return False
        if mode == "trigger_enter":
            collider = entity.get_component(Collider)
            if collider is None or not collider.is_trigger:
                return False
        if mode == "collision" and entity.get_component(Collider) is None:
            return False
        self._upsert_component(
            entity_name,
            "SceneTransitionAction",
            {"enabled": True, "target_scene_path": target_path, "target_entry_id": target_entry_id},
        )
        self._remove_component(entity_name, "SceneTransitionOnContact")
        button_payload = self._current_component_payload(entity_name, "UIButton")
        if mode == "ui_button":
            if button_payload is None:
                return False
            button_payload["on_click"] = {"type": "run_scene_transition"}
            return self._upsert_component(entity_name, "UIButton", button_payload)
        if button_payload is not None:
            on_click = dict(button_payload.get("on_click", {}) or {})
            if str(on_click.get("type", "") or "").strip() == "run_scene_transition":
                button_payload["on_click"] = {"type": "emit_event", "name": "ui.button_clicked"}
                self._upsert_component(entity_name, "UIButton", button_payload)
        return self._upsert_component(
            entity_name,
            "SceneTransitionOnContact",
            {"enabled": True, "mode": "collision" if mode == "collision" else "trigger_enter", "require_player": True},
        )

    def _scene_options(self, current_target: str) -> list[tuple[str, str]]:
        options = [("", "Select scene")]
        for row in self._list_available_scenes():
            options.append((row, row))
        if current_target and all(key != current_target for key, _ in options):
            options.append((current_target, f"Invalid: {current_target}"))
        return options

    def _spawn_options(self, target_scene: str, current_entry: str) -> list[tuple[str, str]]:
        options = [("", "No spawn")]
        for item in self._list_entry_points_for_target(target_scene):
            label = item["label"] or item["entry_id"]
            options.append((item["entry_id"], f"{label} ({item['entity_name']})"))
        if current_entry and all(key != current_entry for key, _ in options):
            options.append((current_entry, f"Invalid: {current_entry}"))
        return options

    def _list_available_scenes(self) -> list[str]:
        if self.project_service is None or not getattr(self.project_service, "has_project", False):
            return []
        return [str(item.get("path", "") or "") for item in self.project_service.list_project_scenes() if str(item.get("path", "") or "").strip()]

    def _list_entry_points_for_target(self, target_scene_path: str) -> list[dict[str, str]]:
        source_path = ""
        if self.scene_manager is not None and hasattr(self.scene_manager, "current_scene") and self.scene_manager.current_scene is not None:
            source_path = str(getattr(self.scene_manager.current_scene, "source_path", "") or "")
        return list_scene_entry_points(source_path or None, str(target_scene_path or "").strip())

    def _get_mode_options(self, entity: Any) -> list[tuple[str, str]]:
        options = [("", "Select trigger")]
        if entity.get_component(UIButton) is not None:
            options.append(("ui_button", "UI Button"))
        collider = entity.get_component(Collider)
        if collider is not None:
            options.append(("trigger_enter", "Touch / Trigger"))
            options.append(("collision", "Collision"))
        return options

    def _get_link_messages(self, entity: Any, link_payload: dict[str, Any], snapshot: dict[str, list[dict[str, Any]]]) -> list[str]:
        mode = str(link_payload.get("link_mode", "") or "").strip()
        target_path = str(link_payload.get("target_path", "") or "").strip()
        messages: list[str] = []
        collider = entity.get_component(Collider)
        if mode == "ui_button" and entity.get_component(UIButton) is None:
            messages.append("UI Button mode requires UIButton.")
        if mode == "trigger_enter":
            if collider is None:
                messages.append("Touch / Trigger requires Collider.")
            elif not collider.is_trigger:
                messages.append("Touch / Trigger requires Collider.is_trigger = true.")
        if mode == "collision" and collider is None:
            messages.append("Collision requires Collider.")
        if mode and not target_path:
            messages.append("Target scene is required.")
        for row in snapshot.get("rows", []):
            if str(row.get("source_entity_name", "")) != str(entity.name):
                continue
            for message in row.get("messages", []):
                if message not in messages:
                    messages.append(message)
        return messages

    def _filtered_items(self, snapshot: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        active_path, active_key = self._active_scene_identity()
        rows = [{"kind": "row", **item} for item in snapshot.get("rows", []) if bool(item.get("is_authoring_row", False))]
        if self.only_problems:
            rows = [item for item in rows if str(item.get("status", "")) != "ok"]
        if self.current_scene_only:
            rows = [
                item
                for item in rows
                if str(item.get("source_scene_path", "") or "") == active_path
                or str(item.get("source_scene_key", "") or "") == active_key
            ]
        return rows

    def _active_scene_identity(self) -> tuple[str, str]:
        if self.scene_manager is None or not hasattr(self.scene_manager, "get_active_scene_summary"):
            return "", ""
        summary = self.scene_manager.get_active_scene_summary()
        return str(summary.get("path", "") or ""), str(summary.get("key", "") or "")

    def _draw_status_badge(self, x: int, y: int, width: int, height: int, label: str, status: str) -> None:
        color = self.STATUS_OK
        if status == "warning":
            color = self.STATUS_WARN
        elif status == "error":
            color = self.STATUS_ERR
        rl.draw_rectangle(x, y, width, height, color)
        rl.draw_text(label, x + 6, y + 4, 10, rl.Color(245, 245, 245, 255))

    def _compute_detail_columns(self, rect: rl.Rectangle) -> dict[str, rl.Rectangle]:
        labels = ["From Scene", "Entity", "Trigger", "To Scene", "Spawn", "Status"]
        if rect.width <= 0 or rect.height <= 0:
            return {label: rl.Rectangle(rect.x, rect.y, 0, rect.height) for label in labels}
        weights = {
            "From Scene": 0.21,
            "Entity": 0.15,
            "Trigger": 0.16,
            "To Scene": 0.23,
            "Spawn": 0.11,
            "Status": 0.14,
        }
        min_widths = {
            "From Scene": 96.0,
            "Entity": 72.0,
            "Trigger": 84.0,
            "To Scene": 96.0,
            "Spawn": 56.0,
            "Status": 60.0,
        }
        available_width = rect.width
        total_min_width = sum(min_widths.values())
        scale = min(1.0, available_width / total_min_width) if total_min_width > 0 else 1.0
        x_cursor = rect.x
        remaining = available_width
        result: dict[str, rl.Rectangle] = {}
        for index, label in enumerate(labels):
            if index == len(labels) - 1:
                col_width = max(0.0, remaining)
            else:
                proportional = available_width * weights[label]
                minimum = min_widths[label] * scale
                col_width = max(minimum, proportional)
                col_width = min(col_width, remaining)
            result[label] = rl.Rectangle(x_cursor, rect.y, col_width, rect.height)
            x_cursor += col_width
            remaining = max(0.0, rect.x + rect.width - x_cursor)
        return result

    def _draw_cell_text(self, rect: rl.Rectangle, value: str, y: float, color: rl.Color) -> None:
        available_chars = max(4, int(max(0.0, rect.width - 10.0) / 6.5))
        rl.draw_text(self._truncate(value, available_chars), int(rect.x + 6), int(y), 10, color)

    def _register_cursor_rect(self, rect: rl.Rectangle) -> None:
        self._cursor_interactive_rects.append(rl.Rectangle(rect.x, rect.y, rect.width, rect.height))

    @staticmethod
    def _truncate(value: str, max_len: int) -> str:
        text = str(value or "")
        if len(text) <= max_len:
            return text
        if max_len <= 3:
            return text[:max_len]
        return f"{text[:max_len - 3]}..."
