"""
engine/editor/export_panel.py - Export panel controller (Phase 11).

Model/controller + pyray view for the editor export panel.
Uses EngineAPI public methods exclusively:
  list_export_presets, validate_export_preset, build_export,
  build_all_exports, export_doctor.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol

import pyray as rl
from engine.editor.render_safety import editor_scissor
from engine.editor.ui.widgets import editor_button


class _ExportAPIProtocol(Protocol):
    """Minimal structural interface for EngineAPI export methods."""

    def list_export_presets(self) -> Any: ...
    def validate_export_preset(self, name: Optional[str]) -> Any: ...
    def export_doctor(self) -> Any: ...
    def build_export(self, name: str) -> Any: ...
    def build_all_exports(self) -> Any: ...


class ExportPanel:
    """Controller + pyray view for the editor export panel.

    Delegates all work to an EngineAPI instance (or compatible fake).
    Call render() to draw the panel in a bottom tab slot.
    """

    # colors
    BG = rl.Color(30, 30, 30, 255)
    BG_MID = rl.Color(38, 38, 38, 255)
    BG_LIGHT = rl.Color(48, 48, 48, 255)
    BORDER = rl.Color(25, 25, 25, 255)
    TEXT = rl.Color(210, 210, 210, 255)
    TEXT_DIM = rl.Color(135, 135, 135, 255)
    TEXT_BRIGHT = rl.Color(235, 235, 235, 255)
    BLUE = rl.Color(44, 93, 135, 255)
    BLUE_HOVER = rl.Color(60, 115, 165, 255)
    OK = rl.Color(110, 180, 110, 255)
    ERR = rl.Color(220, 90, 90, 255)
    WARN = rl.Color(220, 170, 80, 255)
    BUTTON = rl.Color(58, 58, 58, 255)
    BUTTON_HOVER = rl.Color(78, 78, 78, 255)

    TOOLBAR_H = 28
    LINE_H = 14
    FONT_SZ = 10

    def __init__(self) -> None:
        self._api: Optional[_ExportAPIProtocol] = None

        self._presets: list[dict[str, Any]] = []
        self._logs: list[tuple[str, str]] = []  # (type, text)  type: ok/err/warn/info
        self._busy: bool = False
        self._scroll_y: float = 0.0

    # ── dependency injection ──────────────────────────────────────────

    def bind_api(self, api: _ExportAPIProtocol) -> None:
        """Supply the EngineAPI (or a fake implementing the export protocol)."""
        self._api = api

    @property
    def api(self) -> _ExportAPIProtocol:
        if self._api is None:
            raise RuntimeError("ExportPanel: bind_api() must be called before use")
        return self._api

    # ── public controller methods ─────────────────────────────────────

    def list_presets(self) -> dict[str, Any]:
        """Return presets list suitable for UI display."""
        result = self._unwrap(self.api.list_export_presets())
        items = []
        if result["success"]:
            for p in result["data"].get("presets", []):
                items.append({
                    "name": p.get("name", ""),
                    "platform": p.get("platform", ""),
                    "mode": p.get("mode", "release"),
                    "output_path": p.get("output_path", ""),
                    "entry_scene": p.get("entry_scene", ""),
                    "bundle_mode": p.get("bundle_mode", ""),
                    "version_name": p.get("version_name", ""),
                })
        result["ui_items"] = items
        result["ui_total"] = len(items)
        return result

    def validate_preset(self, name: Optional[str] = None) -> dict[str, Any]:
        """Run validation for a single preset or all presets."""
        result = self._unwrap(self.api.validate_export_preset(name))
        errors = result["data"].get("errors", []) if isinstance(result.get("data"), dict) else []
        result["ui_error_count"] = len(errors)
        result["ui_errors"] = errors
        return result

    def doctor(self) -> dict[str, Any]:
        """Run export toolchain doctor, return checks list for UI."""
        result = self._unwrap(self.api.export_doctor())
        checks = result["data"].get("checks", []) if isinstance(result.get("data"), dict) else []
        result["ui_checks"] = checks
        result["ui_healthy"] = result["data"].get("healthy", False) if isinstance(result.get("data"), dict) else False
        return result

    def build_export(self, name: str) -> dict[str, Any]:
        """Trigger a single-preset build."""
        result = self._unwrap(self.api.build_export(name))
        data = result.get("data")
        if isinstance(data, dict):
            result["ui_artifacts"] = data.get("artifacts", [])
            result["ui_duration"] = data.get("duration_seconds", 0)
            result["ui_report"] = data.get("report", None)
        else:
            result["ui_artifacts"] = []
            result["ui_duration"] = 0
            result["ui_report"] = None
        return result

    def build_all_exports(self) -> dict[str, Any]:
        """Trigger a build of all presets."""
        result = self._unwrap(self.api.build_all_exports())
        data = result.get("data")
        if isinstance(data, dict):
            result["ui_total"] = data.get("total", 0)
            result["ui_success_count"] = data.get("success_count", 0)
            results_raw = data.get("results", [])
            result["ui_results"] = [
                {"preset": r.get("preset", ""), "success": r.get("success", False)}
                for r in results_raw
            ]
        else:
            result["ui_total"] = 0
            result["ui_success_count"] = 0
            result["ui_results"] = []
        return result

    # ── pyray view ────────────────────────────────────────────────────

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
            self._presets = self.list_presets().get("ui_items", [])
            self._log("info", f"Loaded {len(self._presets)} preset(s)")
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
        btn_rect = rl.Rectangle(float(bx), float(by), 56, float(bh))
        if editor_button((btn_rect.x, btn_rect.y, btn_rect.width, btn_rect.height), "Clear").clicked:
            self._clear_log()

        if self._busy:
            rl.draw_text("Working...", int(rect.x + rect.width - 140), by + 6, self.FONT_SZ, self.WARN)

    def _draw_content(self, x: int, y: int, width: int, height: int) -> None:
        cy = int(y) + 4 - int(self._scroll_y)

        if self._presets:
            rl.draw_text("Presets:", x + 6, cy, self.FONT_SZ, self.TEXT_BRIGHT)
            cy += self.LINE_H + 2
            for p in self._presets:
                label = f"  {p['name']}  ({p['platform']}, {p['mode']})"
                rl.draw_text(label, x + 6, cy, self.FONT_SZ, self.TEXT)
                cy += self.LINE_H
            cy += 6

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

    def _handle_scroll(self, view_h: int) -> None:
        wheel = rl.get_mouse_wheel_move()
        if wheel != 0:
            self._scroll_y = max(0.0, self._scroll_y - wheel * self.LINE_H * 3)

    # ── action runners ────────────────────────────────────────────────

    def _run_build_selected(self) -> None:
        if not self._presets:
            self._log("warn", "No presets loaded. Click Presets first.")
            return
        name = self._presets[0]["name"]
        self._busy = True
        try:
            result = self.build_export(name)
            if result["success"]:
                self._log("ok", f"Build OK: {name} ({result.get('ui_duration', 0):.1f}s)")
                for a in result.get("ui_artifacts", []):
                    self._log("info", f"  -> {a}")
            else:
                self._log("err", f"Build FAILED: {name} — {result.get('message', '')}")
        except Exception as e:
            self._log("err", f"Build error: {e}")
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
                for r in result.get("ui_results", []):
                    kind = "ok" if r["success"] else "err"
                    self._log(kind, f"  {r['preset']}: {'OK' if r['success'] else 'FAILED'}")
            else:
                self._log("err", f"Build All FAILED — {result.get('message', '')}")
        except Exception as e:
            self._log("err", f"Build All error: {e}")
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
                    self._log("ok", f"  \u2713 {label}")
                elif status in ("warn", "warning"):
                    self._log("warn", f"  ! {label}: {check.get('detail', '')}")
                else:
                    self._log("err", f"  x {label}: {check.get('detail', '')}")
        except Exception as e:
            self._log("err", f"Doctor error: {e}")
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
        except Exception as e:
            self._log("err", f"Validation error: {e}")
        finally:
            self._busy = False

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _unwrap(raw: Any) -> dict[str, Any]:
        """Normalise ActionResult / dict / return value into a stable dict."""
        if isinstance(raw, dict):
            success = bool(raw.get("success", False))
            msg = str(raw.get("message", ""))
            data = raw.get("data") or {}
            return {"success": success, "message": msg, "data": dict(data) if isinstance(data, dict) else {"raw": data}}
        return {"success": False, "message": f"Unexpected response type: {type(raw).__name__}", "data": {}}
