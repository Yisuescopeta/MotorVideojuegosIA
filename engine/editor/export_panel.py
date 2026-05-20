"""
engine/editor/export_panel.py - Export panel controller (Phase 11).

Pure model/controller for the editor export panel. No rendering, no pyray.
Uses EngineAPI public methods exclusively:
  list_export_presets, validate_export_preset, build_export,
  build_all_exports, export_doctor.

Does not duplicate any export logic. Import-safe in headless tests.
Designed so a hypothetical UI renderer (e.g. raygui/pyray) can call these
methods and display results.

Usage::

    panel = ExportPanel()
    panel.bind_api(engine_api)  # EngineAPI instance or fake
    result = panel.list_presets()
    # result is a dict with keys: success, message, data, ui_items
"""

from __future__ import annotations

from typing import Any, Optional, Protocol


class _ExportAPIProtocol(Protocol):
    """Minimal structural interface for EngineAPI export methods."""

    def list_export_presets(self) -> Any: ...
    def validate_export_preset(self, name: Optional[str]) -> Any: ...
    def export_doctor(self) -> Any: ...
    def build_export(self, name: str) -> Any: ...
    def build_all_exports(self) -> Any: ...


class ExportPanel:
    """Controller for the editor export panel.

    Delegates all work to an EngineAPI instance (or compatible fake).
    Produces UI-ready dict results with a ``ui_items`` key mapping each
    action to presentable data (presets, validation errors, doctor checks,
    build results).

    No rendering — callers are responsible for drawing the UI.
    """

    def __init__(self) -> None:
        self._api: Optional[_ExportAPIProtocol] = None

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
