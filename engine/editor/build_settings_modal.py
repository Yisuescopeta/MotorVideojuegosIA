from __future__ import annotations

from pathlib import Path
from typing import Any

import pyray as rl


class BuildSettingsModal:
    BG_OVERLAY = rl.Color(0, 0, 0, 170)
    PANEL_BG = rl.Color(38, 38, 38, 255)
    CARD_BG = rl.Color(48, 48, 48, 255)
    BORDER = rl.Color(20, 20, 20, 255)
    TEXT = rl.Color(220, 220, 220, 255)
    DIM = rl.Color(150, 150, 150, 255)
    ACCENT = rl.Color(58, 121, 187, 255)
    SUCCESS = rl.Color(88, 160, 108, 255)
    ERROR = rl.Color(186, 78, 78, 255)
    WARNING = rl.Color(206, 142, 58, 255)

    def __init__(self) -> None:
        self.is_open: bool = False
        self.product_name: str = ""
        self.company_name: str = ""
        self.output_name: str = ""
        self.target_platform: str = "windows_desktop"
        self.startup_scene: str = ""
        self.scenes_in_build: list[str] = []
        self.available_scenes: list[dict[str, str]] = []
        self.development_build: bool = False
        self.include_logs: bool = False
        self.include_profiler: bool = False
        self.status_message: str = ""
        self.status_is_error: bool = False
        self.last_build_report: dict[str, Any] | None = None
        self.request_save: bool = False
        self.request_build: bool = False
        self.request_close: bool = False
        self._focused_field: str = ""
        self._field_rects: dict[str, rl.Rectangle] = {}

    def open(
        self,
        settings_payload: dict[str, Any],
        scene_entries: list[dict[str, Any]],
        *,
        build_report: dict[str, Any] | None = None,
    ) -> None:
        self.apply_settings(settings_payload, scene_entries)
        self.last_build_report = dict(build_report) if isinstance(build_report, dict) else None
        self.status_message = ""
        self.status_is_error = False
        self.request_save = False
        self.request_build = False
        self.request_close = False
        self._focused_field = ""
        self.is_open = True

    def close(self) -> None:
        self.is_open = False
        self.request_close = False
        self.request_save = False
        self.request_build = False
        self._focused_field = ""

    def apply_settings(self, settings_payload: dict[str, Any], scene_entries: list[dict[str, Any]]) -> None:
        payload = dict(settings_payload or {})
        ordered_scenes = [str(item).strip().replace("\\", "/") for item in payload.get("scenes_in_build", []) if str(item).strip()]
        self.product_name = str(payload.get("product_name", "") or "").strip()
        self.company_name = str(payload.get("company_name", "") or "").strip()
        self.output_name = str(payload.get("output_name", "") or "").strip()
        self.target_platform = str(payload.get("target_platform", "windows_desktop") or "windows_desktop").strip()
        self.startup_scene = str(payload.get("startup_scene", "") or "").strip().replace("\\", "/")
        self.scenes_in_build = list(ordered_scenes)
        self.development_build = bool(payload.get("development_build", False))
        self.include_logs = bool(payload.get("include_logs", False))
        self.include_profiler = bool(payload.get("include_profiler", False))
        self.available_scenes = [
            {
                "name": str(item.get("name", "Scene") or "Scene"),
                "path": str(item.get("path", "") or "").strip().replace("\\", "/"),
            }
            for item in scene_entries
            if str(item.get("path", "") or "").strip()
        ]
        self._ensure_scene_consistency()

    def set_build_report(self, payload: dict[str, Any]) -> None:
        self.last_build_report = dict(payload)
        status = str(payload.get("status", "") or "").strip().lower()
        if status == "succeeded":
            self.status_message = f"Build succeeded: {payload.get('output_path', '')}"
            self.status_is_error = False
        else:
            error_items = list(payload.get("errors", [])) if isinstance(payload.get("errors", []), list) else []
            first_error = dict(error_items[0]) if error_items else {}
            message = str(first_error.get("message", "") or payload.get("status", "Build failed")).strip()
            self.status_message = message or "Build failed"
            self.status_is_error = True

    def set_status(self, message: str, *, is_error: bool = False) -> None:
        self.status_message = str(message or "")
        self.status_is_error = bool(is_error)

    def build_settings_payload(self) -> dict[str, Any]:
        return {
            "product_name": self.product_name,
            "company_name": self.company_name,
            "startup_scene": self.startup_scene,
            "scenes_in_build": list(self.scenes_in_build),
            "target_platform": self.target_platform or "windows_desktop",
            "development_build": self.development_build,
            "include_logs": self.include_logs,
            "include_profiler": self.include_profiler,
            "output_name": self.output_name,
        }

    def toggle_scene_in_build(self, scene_path: str) -> None:
        normalized = str(scene_path or "").strip().replace("\\", "/")
        if not normalized:
            return
        if normalized in self.scenes_in_build:
            self.scenes_in_build = [item for item in self.scenes_in_build if item != normalized]
        else:
            self.scenes_in_build.append(normalized)
        self._ensure_scene_consistency()

    def move_scene(self, scene_path: str, direction: int) -> None:
        normalized = str(scene_path or "").strip().replace("\\", "/")
        if normalized not in self.scenes_in_build:
            return
        index = self.scenes_in_build.index(normalized)
        target_index = max(0, min(len(self.scenes_in_build) - 1, index + int(direction)))
        if index == target_index:
            return
        item = self.scenes_in_build.pop(index)
        self.scenes_in_build.insert(target_index, item)
        self._ensure_scene_consistency()

    def set_startup_scene(self, scene_path: str) -> None:
        normalized = str(scene_path or "").strip().replace("\\", "/")
        if normalized in self.scenes_in_build:
            self.startup_scene = normalized

    def consume_save_request(self) -> bool:
        requested = self.request_save
        self.request_save = False
        return requested

    def consume_build_request(self) -> bool:
        requested = self.request_build
        self.request_build = False
        return requested

    def consume_close_request(self) -> bool:
        requested = self.request_close
        self.request_close = False
        return requested

    def handle_input(self) -> None:
        if not self.is_open:
            return
        mouse = rl.get_mouse_position()
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            focused = ""
            for field, rect in self._field_rects.items():
                if rl.check_collision_point_rec(mouse, rect):
                    focused = field
                    break
            self._focused_field = focused
        if rl.is_key_pressed(rl.KEY_ESCAPE):
            self.request_close = True
            self._focused_field = ""
            return
        if not self._focused_field:
            return
        value = getattr(self, self._focused_field, "")
        if rl.is_key_pressed(rl.KEY_BACKSPACE) and value:
            setattr(self, self._focused_field, value[:-1])
        while True:
            codepoint = rl.get_char_pressed()
            if codepoint == 0:
                break
            if codepoint in (10, 13):
                continue
            try:
                char = chr(codepoint)
            except ValueError:
                continue
            if char.isprintable() and len(value) < 64:
                value += char
        setattr(self, self._focused_field, value)
        if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
            self.request_save = True

    def render(self, screen_width: int, screen_height: int) -> None:
        if not self.is_open:
            return

        rl.draw_rectangle(0, 0, screen_width, screen_height, self.BG_OVERLAY)
        modal = rl.Rectangle(screen_width / 2 - 420, screen_height / 2 - 260, 840, 520)
        rl.draw_rectangle_rec(modal, self.PANEL_BG)
        rl.draw_rectangle_lines_ex(modal, 1, self.BORDER)
        rl.draw_text("Build Settings", int(modal.x + 18), int(modal.y + 16), 18, self.TEXT)
        rl.draw_text("Unity-style in spirit: explicit scenes, startup scene, development toggles, and Build Player.", int(modal.x + 18), int(modal.y + 40), 10, self.DIM)

        left = rl.Rectangle(modal.x + 16, modal.y + 72, 320, 364)
        center = rl.Rectangle(modal.x + 348, modal.y + 72, 240, 364)
        right = rl.Rectangle(modal.x + 600, modal.y + 72, 224, 364)
        for rect in (left, center, right):
            rl.draw_rectangle_rec(rect, self.CARD_BG)
            rl.draw_rectangle_lines_ex(rect, 1, self.BORDER)

        self._field_rects = {}
        self._render_basics(left)
        self._render_scene_list(center)
        self._render_build_result(right)

        if self.status_message:
            rl.draw_text(
                self.status_message,
                int(modal.x + 18),
                int(modal.y + modal.height - 56),
                10,
                self.ERROR if self.status_is_error else self.ACCENT,
            )

        close_rect = rl.Rectangle(modal.x + modal.width - 256, modal.y + modal.height - 34, 72, 22)
        save_rect = rl.Rectangle(modal.x + modal.width - 176, modal.y + modal.height - 34, 72, 22)
        build_rect = rl.Rectangle(modal.x + modal.width - 96, modal.y + modal.height - 34, 80, 22)
        if rl.gui_button(close_rect, "Close"):
            self.request_close = True
        if rl.gui_button(save_rect, "Save"):
            self.request_save = True
        if rl.gui_button(build_rect, "Build"):
            self.request_build = True

    def _render_basics(self, rect: rl.Rectangle) -> None:
        rl.draw_text("Build Basics", int(rect.x + 12), int(rect.y + 12), 12, self.TEXT)
        current_y = int(rect.y + 40)
        current_y = self._draw_text_field(rect, current_y, "Product", "product_name", self.product_name, "Project")
        current_y = self._draw_text_field(rect, current_y, "Company", "company_name", self.company_name, "DefaultCompany")
        current_y = self._draw_text_field(rect, current_y, "Output", "output_name", self.output_name, "game_build")

        rl.draw_text("Target", int(rect.x + 12), current_y + 5, 10, self.TEXT)
        rl.draw_text("windows_desktop", int(rect.x + 112), current_y + 5, 10, self.TEXT)
        current_y += 28

        self._draw_toggle_button(rect, current_y, "Development Build", self.development_build, self._toggle_development_build)
        current_y += 28
        self._draw_toggle_button(rect, current_y, "Include Logs", self.include_logs, lambda: setattr(self, "include_logs", not self.include_logs))
        current_y += 28
        self._draw_toggle_button(
            rect,
            current_y,
            "Include Profiler",
            self.include_profiler,
            self._toggle_profiler,
        )
        current_y += 34
        rl.draw_text("Startup Scene", int(rect.x + 12), current_y, 10, self.TEXT)
        startup_label = self.startup_scene or "(select a scene in build)"
        rl.draw_text(startup_label, int(rect.x + 12), current_y + 16, 10, self.DIM if not self.startup_scene else self.TEXT)

    def _render_scene_list(self, rect: rl.Rectangle) -> None:
        rl.draw_text("Scenes In Build", int(rect.x + 12), int(rect.y + 12), 12, self.TEXT)
        current_y = int(rect.y + 40)
        for scene in self._ordered_scene_entries():
            row_rect = rl.Rectangle(rect.x + 8, current_y, rect.width - 16, 42)
            rl.draw_rectangle_rec(row_rect, self.PANEL_BG)
            rl.draw_rectangle_lines_ex(row_rect, 1, self.BORDER)
            path = scene["path"]
            in_build = path in self.scenes_in_build
            is_startup = path == self.startup_scene

            rl.draw_text(scene["name"], int(row_rect.x + 8), int(row_rect.y + 6), 10, self.TEXT)
            rl.draw_text(path, int(row_rect.x + 8), int(row_rect.y + 22), 9, self.DIM)

            toggle_rect = rl.Rectangle(row_rect.x + row_rect.width - 210, row_rect.y + 9, 52, 22)
            startup_rect = rl.Rectangle(row_rect.x + row_rect.width - 152, row_rect.y + 9, 56, 22)
            up_rect = rl.Rectangle(row_rect.x + row_rect.width - 88, row_rect.y + 9, 22, 22)
            down_rect = rl.Rectangle(row_rect.x + row_rect.width - 62, row_rect.y + 9, 22, 22)

            if rl.gui_button(toggle_rect, "Remove" if in_build else "Add"):
                self.toggle_scene_in_build(path)
            if in_build and rl.gui_button(startup_rect, "Startup" if is_startup else "Set"):
                self.set_startup_scene(path)
            elif not in_build:
                rl.draw_rectangle_rec(startup_rect, rl.Color(40, 40, 40, 255))
                rl.draw_text("Set", int(startup_rect.x + 16), int(startup_rect.y + 6), 10, self.DIM)
            if in_build and rl.gui_button(up_rect, "^"):
                self.move_scene(path, -1)
            if in_build and rl.gui_button(down_rect, "v"):
                self.move_scene(path, 1)
            current_y += 48
            if current_y > rect.y + rect.height - 48:
                break

        if not self.available_scenes:
            rl.draw_text("No project scenes found.", int(rect.x + 12), int(rect.y + 42), 10, self.DIM)

    def _render_build_result(self, rect: rl.Rectangle) -> None:
        rl.draw_text("Build Result", int(rect.x + 12), int(rect.y + 12), 12, self.TEXT)
        if not self.last_build_report:
            rl.draw_text("No player build has been run yet.", int(rect.x + 12), int(rect.y + 42), 10, self.DIM)
            return
        payload = dict(self.last_build_report)
        status = str(payload.get("status", "") or "").strip()
        status_color = self.SUCCESS if status == "succeeded" else self.ERROR
        rl.draw_text(f"Status: {status or 'unknown'}", int(rect.x + 12), int(rect.y + 42), 10, status_color)
        rl.draw_text(f"Target: {payload.get('target_platform', '')}", int(rect.x + 12), int(rect.y + 60), 10, self.TEXT)
        rl.draw_text(f"Startup: {payload.get('startup_scene', '')}", int(rect.x + 12), int(rect.y + 78), 10, self.TEXT)
        rl.draw_text("Output", int(rect.x + 12), int(rect.y + 102), 10, self.TEXT)
        rl.draw_text(str(payload.get("output_path", "") or "(none)"), int(rect.x + 12), int(rect.y + 118), 10, self.DIM)

        warnings = list(payload.get("warnings", [])) if isinstance(payload.get("warnings", []), list) else []
        errors = list(payload.get("errors", [])) if isinstance(payload.get("errors", []), list) else []
        rl.draw_text(f"Warnings: {len(warnings)}", int(rect.x + 12), int(rect.y + 146), 10, self.WARNING if warnings else self.TEXT)
        rl.draw_text(f"Errors: {len(errors)}", int(rect.x + 12), int(rect.y + 162), 10, self.ERROR if errors else self.TEXT)

        line_y = int(rect.y + 190)
        for item in (errors[:3] or warnings[:3]):
            entry = dict(item)
            message = str(entry.get("message", "") or entry.get("code", "") or "").strip()
            if len(message) > 32:
                message = message[:29] + "..."
            rl.draw_text(f"- {message}", int(rect.x + 12), line_y, 10, self.TEXT)
            line_y += 16

        report_path = str(payload.get("report_path", "") or "").strip()
        if report_path:
            rl.draw_text("Report", int(rect.x + 12), int(rect.y + rect.height - 52), 10, self.TEXT)
            rl.draw_text(report_path, int(rect.x + 12), int(rect.y + rect.height - 36), 9, self.DIM)

    def _draw_text_field(self, rect: rl.Rectangle, y: int, label: str, field_name: str, value: str, placeholder: str) -> int:
        rl.draw_text(label, int(rect.x + 12), y + 5, 10, self.TEXT)
        field_rect = rl.Rectangle(rect.x + 112, y, rect.width - 124, 22)
        self._field_rects[field_name] = field_rect
        is_focused = self._focused_field == field_name
        rl.draw_rectangle_rec(field_rect, rl.Color(32, 32, 32, 255))
        rl.draw_rectangle_lines_ex(field_rect, 1, self.ACCENT if is_focused else self.BORDER)
        display = value if value else placeholder
        color = self.TEXT if value else self.DIM
        rl.draw_text(display, int(field_rect.x + 6), int(field_rect.y + 6), 10, color)
        return y + 28

    def _draw_toggle_button(self, rect: rl.Rectangle, y: int, label: str, enabled: bool, on_click) -> None:
        rl.draw_text(label, int(rect.x + 12), y + 5, 10, self.TEXT)
        toggle_rect = rl.Rectangle(rect.x + rect.width - 84, y, 72, 22)
        if rl.gui_button(toggle_rect, "On" if enabled else "Off"):
            on_click()

    def _ordered_scene_entries(self) -> list[dict[str, str]]:
        by_path = {
            item["path"]: dict(item)
            for item in self.available_scenes
            if item.get("path")
        }
        ordered: list[dict[str, str]] = []
        for path in self.scenes_in_build:
            if path in by_path:
                ordered.append(dict(by_path[path]))
        omitted = [
            dict(item)
            for item in self.available_scenes
            if item["path"] not in self.scenes_in_build
        ]
        omitted.sort(key=lambda item: item["path"].lower())
        ordered.extend(omitted)
        return ordered

    def _ensure_scene_consistency(self) -> None:
        available_paths = {item["path"] for item in self.available_scenes}
        self.scenes_in_build = [path for path in self.scenes_in_build if path in available_paths]
        for item in self.available_scenes:
            path = item["path"]
            if path == self.startup_scene and path in self.scenes_in_build:
                break
        else:
            self.startup_scene = self.scenes_in_build[0] if self.scenes_in_build else ""
        if self.include_profiler and not self.development_build:
            self.include_profiler = False

    def _toggle_profiler(self) -> None:
        if not self.development_build:
            self.development_build = True
        self.include_profiler = not self.include_profiler

    def _toggle_development_build(self) -> None:
        self.development_build = not self.development_build
        if not self.development_build:
            self.include_profiler = False
