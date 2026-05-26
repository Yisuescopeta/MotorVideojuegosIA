"""
engine/editor/export_panel.py - Export panel controller.

Model/controller + pyray view for the editor export panel.
Uses EngineAPI public methods exclusively:
  list_export_presets, list_export_entry_scenes, validate_export_preset,
  build_export, build_export_for_scene, build_all_exports, export_doctor.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Protocol

import pyray as rl
from engine.editor.render_safety import editor_scissor
from engine.editor.ui.widgets import editor_button


class _ExportAPIProtocol(Protocol):
    """Minimal structural interface for EngineAPI export methods."""

    def list_export_presets(self) -> Any: ...
    def validate_export_preset(self, name: Optional[str]) -> Any: ...
    def export_doctor(self) -> Any: ...
    def build_export(self, name: str) -> Any: ...
    def build_export_for_scene(self, name: str, entry_scene: str) -> Any: ...
    def build_all_exports(self) -> Any: ...
    def list_export_entry_scenes(self) -> Any: ...


class ExportPanel:
    """Controller + pyray view for the editor export panel."""

    BG = rl.Color(30, 30, 30, 255)
    BG_MID = rl.Color(38, 38, 38, 255)
    BG_LIGHT = rl.Color(48, 48, 48, 255)
    BORDER = rl.Color(25, 25, 25, 255)
    TEXT = rl.Color(210, 210, 210, 255)
    TEXT_DIM = rl.Color(135, 135, 135, 255)
    TEXT_BRIGHT = rl.Color(235, 235, 235, 255)
    OK = rl.Color(110, 180, 110, 255)
    ERR = rl.Color(220, 90, 90, 255)
    WARN = rl.Color(220, 170, 80, 255)

    TOOLBAR_H = 28
    LINE_H = 14
    FONT_SZ = 10

    def __init__(self) -> None:
        self._api: Optional[_ExportAPIProtocol] = None
        self._presets: list[dict[str, Any]] = []
        self._scene_items: list[dict[str, Any]] = []
        self._logs: list[tuple[str, str]] = []
        self._busy: bool = False
        self._scroll_y: float = 0.0
        self._selected_scene_path: str = ""
        self._selected_preset_name: str = ""
        self._active_scene_path: str = ""
        self._prebuild_save_callback: Optional[Callable[[], bool]] = None

    def bind_api(self, api: _ExportAPIProtocol) -> None:
        self._api = api

    def bind_prebuild_save_callback(self, callback: Callable[[], bool]) -> None:
        self._prebuild_save_callback = callback

    @property
    def api(self) -> _ExportAPIProtocol:
        if self._api is None:
            raise RuntimeError("ExportPanel: bind_api() must be called before use")
        return self._api

    def _require_api(self) -> dict[str, Any] | None:
        if self._api is not None:
            return None
        return {
            "success": False,
            "message": "Export panel is not bound to EngineAPI.",
            "data": {
                "errors": [
                    {
                        "code": "EXPORT_PANEL_API_UNBOUND",
                        "hint": "Reopen the editor or reload the project.",
                    }
                ]
            },
        }

    def list_presets(self) -> dict[str, Any]:
        unbound = self._require_api()
        if unbound is not None:
            unbound["ui_items"] = []
            unbound["ui_total"] = 0
            return unbound
        result = self._unwrap(self.api.list_export_presets())
        items: list[dict[str, Any]] = []
        if result["success"]:
            for preset in result["data"].get("presets", []):
                if not isinstance(preset, dict):
                    continue
                items.append(
                    {
                        "name": preset.get("name", ""),
                        "platform": preset.get("platform", ""),
                        "mode": preset.get("mode", "release"),
                        "output_path": preset.get("output_path", ""),
                        "entry_scene": str(preset.get("entry_scene", "") or "").replace("\\", "/"),
                        "bundle_mode": preset.get("bundle_mode", ""),
                        "version_name": preset.get("version_name", ""),
                    }
                )
        result["ui_items"] = items
        result["ui_total"] = len(items)
        return result

    def list_entry_scenes(self) -> dict[str, Any]:
        unbound = self._require_api()
        if unbound is not None:
            unbound["ui_scene_items"] = []
            unbound["ui_active_scene"] = ""
            return unbound
        result = self._unwrap(self.api.list_export_entry_scenes())
        items: list[dict[str, Any]] = []
        active_scene = ""
        if result["success"] and isinstance(result.get("data"), dict):
            for scene in result["data"].get("scenes", []):
                if not isinstance(scene, dict):
                    continue
                path = str(scene.get("path", "") or "").replace("\\", "/")
                if not path:
                    continue
                items.append(
                    {
                        "name": str(scene.get("name", "") or ""),
                        "path": path,
                        "absolute_path": str(scene.get("absolute_path", "") or ""),
                    }
                )
            active_scene = str(result["data"].get("active_scene", "") or "").replace("\\", "/")
        result["ui_scene_items"] = items
        result["ui_active_scene"] = active_scene
        return result

    def refresh_export_options(self) -> None:
        presets_result = self.list_presets()
        self._presets = presets_result.get("ui_items", [])
        valid_preset_names = {str(item.get("name", "") or "") for item in self._presets}
        if self._selected_preset_name not in valid_preset_names:
            self._selected_preset_name = self._presets[0]["name"] if self._presets else ""

        scenes_result = self.list_entry_scenes()
        self._scene_items = scenes_result.get("ui_scene_items", [])
        self._active_scene_path = str(scenes_result.get("ui_active_scene", "") or "")
        self._selected_scene_path = self._resolve_default_entry_scene()

    def validate_preset(self, name: Optional[str] = None) -> dict[str, Any]:
        unbound = self._require_api()
        if unbound is not None:
            unbound["ui_error_count"] = 1
            unbound["ui_errors"] = unbound["data"].get("errors", [])
            return unbound
        result = self._unwrap(self.api.validate_export_preset(name))
        errors = result["data"].get("errors", []) if isinstance(result.get("data"), dict) else []
        result["ui_error_count"] = len(errors)
        result["ui_errors"] = errors
        return result

    def doctor(self) -> dict[str, Any]:
        unbound = self._require_api()
        if unbound is not None:
            unbound["ui_checks"] = []
            unbound["ui_healthy"] = False
            return unbound
        result = self._unwrap(self.api.export_doctor())
        checks = []
        if isinstance(result.get("data"), dict):
            raw_checks = result["data"].get("checks", {})
            if isinstance(raw_checks, dict):
                for key, value in raw_checks.items():
                    checks.append(
                        {
                            "name": str(key),
                            "label": str(key).replace("_", " "),
                            "status": "ok" if bool(value) else "err",
                            "detail": value,
                        }
                    )
            elif isinstance(raw_checks, list):
                for item in raw_checks:
                    if isinstance(item, dict):
                        checks.append(dict(item))
            for issue in result["data"].get("issues", []) or []:
                checks.append({"name": "issue", "label": "issue", "status": "err", "detail": str(issue)})
            for warning in result["data"].get("warnings", []) or []:
                checks.append({"name": "warning", "label": "warning", "status": "warn", "detail": str(warning)})
        result["ui_checks"] = checks
        result["ui_healthy"] = result["data"].get("healthy", False) if isinstance(result.get("data"), dict) else False
        return result

    def build_export(self, name: str) -> dict[str, Any]:
        unbound = self._require_api()
        if unbound is not None:
            return self._with_empty_build_ui(unbound)
        result = self._unwrap(self.api.build_export(name))
        return self._apply_build_ui_fields(result)

    def build_export_for_scene(self, name: str, entry_scene: str) -> dict[str, Any]:
        unbound = self._require_api()
        if unbound is not None:
            return self._with_empty_build_ui(unbound)
        result = self._unwrap(self.api.build_export_for_scene(name, entry_scene))
        return self._apply_build_ui_fields(result)

    def build_all_exports(self) -> dict[str, Any]:
        unbound = self._require_api()
        if unbound is not None:
            unbound["ui_total"] = 0
            unbound["ui_success_count"] = 0
            unbound["ui_results"] = []
            return unbound
        result = self._unwrap(self.api.build_all_exports())
        data = result.get("data")
        if isinstance(data, dict):
            result["ui_total"] = data.get("total", 0)
            result["ui_success_count"] = data.get("success_count", 0)
            results_raw = data.get("results", [])
            result["ui_results"] = [
                {"preset": item.get("preset", ""), "success": item.get("success", False)}
                for item in results_raw
                if isinstance(item, dict)
            ]
        else:
            result["ui_total"] = 0
            result["ui_success_count"] = 0
            result["ui_results"] = []
        return result

    def _log(self, kind: str, text: str) -> None:
        self._logs.append((kind, text))

    def _clear_log(self) -> None:
        self._logs.clear()

    def render(self, x: int, y: int, width: int, height: int) -> None:
        rl.draw_rectangle(x, y, width, height, self.BG)

        toolbar_rect = rl.Rectangle(float(x), float(y), float(width), float(self.TOOLBAR_H))
        content_y = y + self.TOOLBAR_H
        content_h = height - self.TOOLBAR_H

        rl.draw_rectangle_rec(toolbar_rect, self.BG_MID)
        rl.draw_line(x, content_y, x + width, content_y, self.BORDER)

        self._draw_toolbar(toolbar_rect)
        with editor_scissor(rl.Rectangle(float(x), float(content_y), float(width), float(content_h))):
            self._draw_content(x, content_y, width, content_h)

    def _draw_toolbar(self, rect: rl.Rectangle) -> None:
        bx = int(rect.x) + 6
        by = int(rect.y) + 2
        bw = 56
        bh = 24

        btn_rect = rl.Rectangle(float(bx), float(by), float(bw), float(bh))
        if editor_button((btn_rect.x, btn_rect.y, btn_rect.width, btn_rect.height), "Presets").clicked:
            self._busy = True
            self.refresh_export_options()
            self._log("info", f"Loaded {len(self._presets)} preset(s) and {len(self._scene_items)} scene(s)")
            self._busy = False
        bx += bw + 4

        btn_rect = rl.Rectangle(float(bx), float(by), float(bw), float(bh))
        if editor_button((btn_rect.x, btn_rect.y, btn_rect.width, btn_rect.height), "Build").clicked:
            self._run_build_selected()
        bx += bw + 4

        btn_rect = rl.Rectangle(float(bx), float(by), float(bw + 16), float(bh))
        if editor_button((btn_rect.x, btn_rect.y, btn_rect.width, btn_rect.height), "Build All").clicked:
            self._run_build_all()
        bx += bw + 20

        btn_rect = rl.Rectangle(float(bx), float(by), float(bw), float(bh))
        if editor_button((btn_rect.x, btn_rect.y, btn_rect.width, btn_rect.height), "Doctor").clicked:
            self._run_doctor()
        bx += bw + 4

        btn_rect = rl.Rectangle(float(bx), float(by), float(bw + 10), float(bh))
        if editor_button((btn_rect.x, btn_rect.y, btn_rect.width, btn_rect.height), "Validate").clicked:
            self._run_validate()

        bx = int(rect.x + rect.width - 64)
        btn_rect = rl.Rectangle(float(bx), float(by), 56.0, float(bh))
        if editor_button((btn_rect.x, btn_rect.y, btn_rect.width, btn_rect.height), "Clear").clicked:
            self._clear_log()

        if self._busy:
            rl.draw_text("Working...", int(rect.x + rect.width - 140), by + 6, self.FONT_SZ, self.WARN)

    def _draw_content(self, x: int, y: int, width: int, height: int) -> None:
        cy = int(y) + 4 - int(self._scroll_y)

        if self._presets:
            rl.draw_text("Presets:", x + 6, cy, self.FONT_SZ, self.TEXT_BRIGHT)
            cy += self.LINE_H + 2
            for preset in self._presets:
                is_selected = preset.get("name", "") == self._selected_preset_name
                label = f"{'>' if is_selected else ' '} {preset['name']}  ({preset['platform']}, {preset['mode']})"
                rl.draw_text(label, x + 6, cy, self.FONT_SZ, self.TEXT_BRIGHT if is_selected else self.TEXT)
                cy += self.LINE_H
            cy += 6

        cy = self._draw_entry_scene_selector(x, cy, width)

        if self._logs:
            cy += 2
            for kind, text in self._logs:
                color = {
                    "ok": self.OK,
                    "err": self.ERR,
                    "warn": self.WARN,
                    "info": self.TEXT_DIM,
                }.get(kind, self.TEXT)
                rl.draw_text(text, x + 6, cy, self.FONT_SZ, color)
                cy += self.LINE_H

        self._handle_scroll(height)

    def _draw_entry_scene_selector(self, x: int, y: int, width: int) -> int:
        cy = y
        rl.draw_text("Entry Scene:", x + 6, cy, self.FONT_SZ, self.TEXT_BRIGHT)
        cy += self.LINE_H + 2

        if not self._scene_items:
            rl.draw_text(
                "No scenes found. Create or save a scene before export.",
                x + 6,
                cy,
                self.FONT_SZ,
                self.WARN,
            )
            return cy + self.LINE_H + 6

        bx = x + 6
        by = cy - 2
        bh = 22

        prev_rect = rl.Rectangle(float(bx), float(by), 24.0, float(bh))
        if editor_button((prev_rect.x, prev_rect.y, prev_rect.width, prev_rect.height), "<").clicked:
            self._select_previous_scene()
        bx += 28

        next_rect = rl.Rectangle(float(bx), float(by), 24.0, float(bh))
        if editor_button((next_rect.x, next_rect.y, next_rect.width, next_rect.height), ">").clicked:
            self._select_next_scene()
        bx += 32

        active_button_w = 82
        label_w = max(100, width - (bx - x) - active_button_w - 18)
        label_rect = rl.Rectangle(float(bx), float(by), float(label_w), float(bh))
        rl.draw_rectangle_rec(label_rect, self.BG_LIGHT)
        rl.draw_rectangle_lines_ex(label_rect, 1.0, self.BORDER)
        rl.draw_text(
            self._selected_scene_path or "(none)",
            int(label_rect.x) + 6,
            int(label_rect.y) + 6,
            self.FONT_SZ,
            self.TEXT,
        )

        active_rect = rl.Rectangle(
            float(x + width - active_button_w - 6),
            float(by),
            float(active_button_w),
            float(bh),
        )
        if editor_button((active_rect.x, active_rect.y, active_rect.width, active_rect.height), "Use Active").clicked:
            self._select_active_scene()
        return cy + bh + 8

    def _handle_scroll(self, view_h: int) -> None:
        wheel = rl.get_mouse_wheel_move()
        if wheel != 0:
            self._scroll_y = max(0.0, self._scroll_y - wheel * self.LINE_H * 3)

    def _run_build_selected(self) -> None:
        if not self._presets:
            self._log("warn", "No presets loaded. Click Presets first.")
            return

        name = self._selected_preset_name or self._presets[0]["name"]
        entry_scene = self._selected_scene_path.strip()

        if self._prebuild_save_callback is not None and not self._prebuild_save_callback():
            self._log("err", "Build cancelled: could not save dirty scenes.")
            return
        if not entry_scene:
            self._log("err", "No entry scene selected.")
            return

        self._busy = True
        try:
            result = self.build_export_for_scene(name, entry_scene)
            effective_entry_scene = str(result.get("ui_effective_entry_scene", "") or entry_scene)
            if result["success"]:
                self._log("ok", f"Build OK: {name} ({result.get('ui_duration', 0):.1f}s)")
                self._log("info", f"Entry Scene: {effective_entry_scene}")
                for artifact in result.get("ui_artifacts", []):
                    self._log("info", f"  -> {artifact}")
            else:
                self._log("err", f"Build FAILED: {name} - {result.get('message', '')}")
                self._log("info", f"Entry Scene: {effective_entry_scene}")
                for error in result.get("data", {}).get("errors", []):
                    self._log("err", f"  {self._format_export_error(error)}")
        except Exception as exc:
            self._log("err", f"Build error: {exc}")
        finally:
            self._busy = False

    def _run_build_all(self) -> None:
        if not self._presets:
            self._log("warn", "No presets loaded. Click Presets first.")
            return
        self._busy = True
        try:
            result = self.build_all_exports()
            ok = result.get("ui_success_count", 0)
            total = result.get("ui_total", 0)
            if result["success"]:
                self._log("ok", f"Build All: {ok}/{total} succeeded")
                for item in result.get("ui_results", []):
                    kind = "ok" if item["success"] else "err"
                    self._log(kind, f"  {item['preset']}: {'OK' if item['success'] else 'FAILED'}")
            else:
                self._log("err", f"Build All FAILED - {result.get('message', '')}")
        except Exception as exc:
            self._log("err", f"Build All error: {exc}")
        finally:
            self._busy = False

    def _run_doctor(self) -> None:
        self._busy = True
        try:
            result = self.doctor()
            healthy = result.get("ui_healthy", False)
            self._log("ok" if healthy else "warn", f"Doctor: {'HEALTHY' if healthy else 'ISSUES FOUND'}")
            for check in result.get("ui_checks", []):
                status = check.get("status", "")
                label = check.get("label", "")
                if status == "ok":
                    self._log("ok", f"  [ok] {label}")
                elif status in ("warn", "warning"):
                    self._log("warn", f"  ! {label}: {check.get('detail', '')}")
                else:
                    self._log("err", f"  x {label}: {check.get('detail', '')}")
        except Exception as exc:
            self._log("err", f"Doctor error: {exc}")
        finally:
            self._busy = False

    def _run_validate(self) -> None:
        self._busy = True
        try:
            result = self.validate_preset()
            err_count = result.get("ui_error_count", 0)
            if err_count == 0:
                self._log("ok", "Validation: All presets OK")
            else:
                self._log("warn", f"Validation: {err_count} error(s)")
                for err in result.get("ui_errors", []):
                    self._log("err", f"  {err}")
        except Exception as exc:
            self._log("err", f"Validation error: {exc}")
        finally:
            self._busy = False

    def _select_previous_scene(self) -> None:
        if not self._scene_items:
            self._selected_scene_path = ""
            return
        scene_paths = [str(item.get("path", "") or "") for item in self._scene_items]
        try:
            index = scene_paths.index(self._selected_scene_path)
        except ValueError:
            index = 0
        self._selected_scene_path = scene_paths[(index - 1) % len(scene_paths)]

    def _select_next_scene(self) -> None:
        if not self._scene_items:
            self._selected_scene_path = ""
            return
        scene_paths = [str(item.get("path", "") or "") for item in self._scene_items]
        try:
            index = scene_paths.index(self._selected_scene_path)
        except ValueError:
            index = -1
        self._selected_scene_path = scene_paths[(index + 1) % len(scene_paths)]

    def _select_active_scene(self) -> None:
        result = self.list_entry_scenes()
        self._scene_items = result.get("ui_scene_items", [])
        self._active_scene_path = str(result.get("ui_active_scene", "") or "")
        scene_paths = {str(item.get("path", "") or "") for item in self._scene_items}
        if self._active_scene_path in scene_paths:
            self._selected_scene_path = self._active_scene_path
            return
        self._selected_scene_path = self._resolve_default_entry_scene()

    def _resolve_default_entry_scene(self) -> str:
        scene_paths = [str(item.get("path", "") or "") for item in self._scene_items]
        if self._active_scene_path and self._active_scene_path in scene_paths:
            return self._active_scene_path

        preset_entry_scene = self._selected_preset_entry_scene()
        if preset_entry_scene and preset_entry_scene in scene_paths:
            return preset_entry_scene

        return scene_paths[0] if scene_paths else ""

    def _selected_preset_entry_scene(self) -> str:
        selected_name = self._selected_preset_name
        for preset in self._presets:
            if str(preset.get("name", "") or "") == selected_name:
                return str(preset.get("entry_scene", "") or "").replace("\\", "/")
        if self._presets:
            return str(self._presets[0].get("entry_scene", "") or "").replace("\\", "/")
        return ""

    @staticmethod
    def _with_empty_build_ui(result: dict[str, Any]) -> dict[str, Any]:
        result["ui_artifacts"] = []
        result["ui_duration"] = 0
        result["ui_report"] = None
        result["ui_effective_entry_scene"] = ""
        result["ui_entry_scene_override"] = None
        return result

    @classmethod
    def _apply_build_ui_fields(cls, result: dict[str, Any]) -> dict[str, Any]:
        data = result.get("data")
        if not isinstance(data, dict):
            return cls._with_empty_build_ui(result)
        result["ui_artifacts"] = data.get("artifacts", [])
        result["ui_duration"] = data.get("duration_seconds", 0)
        result["ui_report"] = data.get("report", None)
        result["ui_effective_entry_scene"] = data.get("effective_entry_scene", "")
        result["ui_entry_scene_override"] = data.get("entry_scene_override")
        return result

    @staticmethod
    def _format_export_error(error: Any) -> str:
        if not isinstance(error, dict):
            return str(error)
        code = str(error.get("code", "") or "").strip()
        path = str(error.get("path", "") or "").strip()
        hint = str(error.get("hint", "") or "").strip()
        parts = [part for part in (code, path, hint) if part]
        return " - ".join(parts) if parts else str(error)

    @staticmethod
    def _unwrap(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            success = bool(raw.get("success", False))
            message = str(raw.get("message", ""))
            data = raw.get("data") or {}
            if isinstance(data, dict):
                payload = dict(data)
            else:
                payload = {"raw": data}
            return {"success": success, "message": message, "data": payload}
        return {"success": False, "message": f"Unexpected response type: {type(raw).__name__}", "data": {}}
