"""Export API delegate for EngineAPI.

Exposes public export methods:
  list_export_presets()
  validate_export_preset(name)
  export_doctor()
  export_pack(name)
  build_export(name)
  build_all_exports()
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from engine.api._context import EngineAPIComponent
from engine.export.android_exporter import AndroidExporter
from engine.export.build_context import BuildContext
from engine.export.content_pack import build_content_pack
from engine.export.diagnostics import run_export_doctor
from engine.export.exporter_registry import ExporterRegistry
from engine.export.ios_exporter import IOSExporter
from engine.export.linux_exporter import LinuxExporter
from engine.export.macos_exporter import MacOSExporter
from engine.export.models import ExportPreset
from engine.export.preset_loader import (
    PresetLoadError,
    get_preset_by_name,
    list_preset_names,
    load_presets,
)
from engine.export.preset_schema import validate_preset
from engine.export.reports import generate_build_report, write_build_report
from engine.export.validator import validate_preset_against_project
from engine.export.windows_exporter import WindowsExporter


def _register_default_exporters() -> None:
    if "windows" not in ExporterRegistry._exporters:
        ExporterRegistry.register(WindowsExporter())
    if "linux" not in ExporterRegistry._exporters:
        ExporterRegistry.register(LinuxExporter())
    if "macos" not in ExporterRegistry._exporters:
        ExporterRegistry.register(MacOSExporter())
    if "android" not in ExporterRegistry._exporters:
        ExporterRegistry.register(AndroidExporter())
    if "ios" not in ExporterRegistry._exporters:
        ExporterRegistry.register(IOSExporter())


_register_default_exporters()


class ExportAPI(EngineAPIComponent):  # type: ignore[misc]
    def list_export_presets(self) -> dict[str, Any]:
        """List all export presets from export_presets.motor.json.

        Result shape:
          Success → {"success": True, "message": "Found N export preset(s)",
                      "data": {"count": int, "presets": [ExportPreset, ...],
                               "names": [str, ...]}}
          Failure → {"success": False, "message": str,
                     "data": {"errors": [{"code": str, "message": str}, ...]}}

        Side effects: reads the project's export_presets.motor.json.
        """
        try:
            doc = load_presets(self._context.project_root)
            names = list_preset_names(doc)
            presets_data = [p.to_dict() for p in doc.presets]
            return _ok(f"Found {len(names)} export preset(s)", {
                "count": len(names),
                "presets": presets_data,
                "names": names,
            })
        except PresetLoadError as exc:
            return _fail(str(exc), _err_dicts(exc))

    def validate_export_preset(
        self, name: str | None = None
    ) -> dict[str, Any]:
        """Validate one or all export presets against schema and project.

        If *name* is None, validates every preset found in
        export_presets.motor.json.  Otherwise validates only the named preset.

        Result shape:
          Success → {"success": True,
                     "message": "All presets validated successfully.",
                     "data": {"checked": int, "errors": []}}
          Failure → {"success": False, "message": str,
                     "data": {"errors": [{"code": str, "message": str}, ...]}}

        Side effects: reads export_presets.motor.json; no writes.
        """
        try:
            doc = load_presets(self._context.project_root)
        except PresetLoadError as exc:
            return _fail(str(exc), {"errors": _err_dicts(exc)})

        presets_to_check: list[ExportPreset]
        if name:
            preset = get_preset_by_name(doc, name)
            if preset is None:
                return _fail(f"Preset '{name}' not found.")
            presets_to_check = [preset]
        else:
            presets_to_check = doc.presets

        all_errors: list[dict[str, str]] = []
        for preset in presets_to_check:
            schema_errors = validate_preset(preset)
            proj_errors = validate_preset_against_project(
                preset, self._context.project_root,
            )
            all_errors.extend(e.to_dict() for e in schema_errors)
            all_errors.extend(e.to_dict() for e in proj_errors)

        if all_errors:
            return _fail(
                "Export preset validation failed",
                {"errors": all_errors},
            )

        return _ok(
            "All presets validated successfully.",
            {"checked": len(presets_to_check), "errors": []},
        )

    def export_doctor(self) -> dict[str, Any]:
        """Run diagnostics on the export toolchain (SDKs, tools, paths).

        Result shape:
          Success → {"success": True, "message": "Export toolchain is healthy.",
                      "data": {"healthy": True, ...platform-specific keys...}}
          Failure → {"success": False,
                     "message": "Export toolchain has issues.",
                     "data": {"healthy": False, "issues": [...], ...}}

        Side effects: probes installed SDKs and build tools read-only.
        """
        result = run_export_doctor()
        if result["healthy"]:
            return _ok("Export toolchain is healthy.", result)
        return _fail("Export toolchain has issues.", result)

    def export_pack(self, name: str) -> dict[str, Any]:
        """Build a content pack (game.pak + game.manifest.json) for *name*.

        Stages assets, scenes and scripts under .motor/build/staging/<name>/
        and produces a self-contained content pack ready for platform export.

        Result shape:
          Success → {"success": True,
                     "message": "Content pack built for '<name>'",
                     "data": {"preset": str, "platform": str,
                              "assets": int, "scenes": int, "scripts": int,
                              "manifest": str, "pack": str,
                              "entry_scene": str, "warnings": [str, ...]}}
          Failure → {"success": False, "message": str,
                     "data": {"errors": [...]}}

        Side effects: writes .pak and manifest files to the staging directory.
        """
        try:
            doc = load_presets(self._context.project_root)
        except PresetLoadError as exc:
            return _fail(str(exc), {"errors": _err_dicts(exc)})

        preset = get_preset_by_name(doc, name)
        if preset is None:
            return _fail(f"Preset '{name}' not found.")

        errors = _validate_export_preset_for_project(
            preset, self._context.project_root,
        )
        if errors:
            return _fail("Export preset validation failed", {"errors": errors})

        staging_dir = (
            Path(self._context.project_root)
            / ".motor" / "build" / "staging" / _safe_name(name)
        )

        try:
            manifest, graph = build_content_pack(
                preset, self._context.project_root, staging_dir,
            )
            return _ok(
                f"Content pack built for '{name}'",
                {
                    "preset": name,
                    "platform": preset.platform,
                    "assets": len(manifest.assets),
                    "scenes": len(manifest.scenes),
                    "scripts": len(manifest.scripts),
                    "manifest": str(staging_dir / "game.manifest.json"),
                    "pack": str(staging_dir / "game.pak"),
                    "entry_scene": graph.entry_scene,
                    "warnings": graph.warnings,
                },
            )
        except Exception as exc:
            return _fail(f"Pack failed: {exc}")

    def build_export(self, name: str) -> dict[str, Any]:
        """Run the platform exporter for preset *name* to produce artifacts.

        Validates the preset, dispatches to the registered platform exporter,
        and writes a JSON build report under .motor/build/reports/.

        Result shape:
          Success → {"success": True,
                     "message": "Build completed for '<name>'",
                     "data": {"preset": str, "platform": str, "mode": str,
                              "success": True, "duration_seconds": float,
                              "artifacts": [str, ...], "report": str | None}}
          Failure → {"success": False,
                     "message": "Build failed for '<name>'",
                     "data": {"preset": str, ..., "errors": [...],
                              "warnings": [...]}}

        Side effects: spawns external build tools; writes artifacts and a build
        report to disk.
        """
        try:
            doc = load_presets(self._context.project_root)
        except PresetLoadError as exc:
            return _fail(str(exc), {"errors": _err_dicts(exc)})

        preset = get_preset_by_name(doc, name)
        if preset is None:
            return _fail(f"Preset '{name}' not found.")

        errors = _validate_export_preset_for_project(
            preset, self._context.project_root,
        )
        if errors:
            return _fail("Export preset validation failed", {"errors": errors})

        ctx = BuildContext(preset, self._context.project_root)

        exporter = ExporterRegistry.get(preset.platform)
        if exporter is None:
            ctx.add_error(
                f"No exporter registered for platform '{preset.platform}'"
            )

        t0 = time.time()
        success = False

        if exporter is not None:
            success = exporter.export(ctx)

        duration = time.time() - t0
        report = generate_build_report(ctx, success, duration)

        try:
            report_path = write_build_report(
                report, self._context.project_root, name,
            )
        except Exception:
            report_path = None

        data: dict[str, Any] = {
            "preset": name,
            "platform": preset.platform,
            "mode": preset.mode,
            "success": success,
            "duration_seconds": round(duration, 2),
            "artifacts": ctx.artifacts,
        }
        if report_path:
            data["report"] = str(report_path)

        if success:
            return _ok(
                f"Build completed for '{name}'",
                data,
            )
        return _fail(
            f"Build failed for '{name}'",
            {**data, "errors": ctx.errors, "warnings": ctx.warnings},
        )

    def build_all_exports(self) -> dict[str, Any]:
        """Run build_export for every preset in export_presets.motor.json.

        Aggregates individual build results into a single summary.

        Result shape:
          All pass → {"success": True,
                      "message": "Build-all completed for N preset(s)",
                      "data": {"total": int, "success_count": int,
                               "results": [build_export dict, ...]}}
          Any fail → {"success": False,
                      "message": "Build-all completed with failures",
                      "data": {"total": int, "success_count": int,
                               "results": [...]}}

        Side effects: same cumulative side effects as build_export for each
        preset.
        """
        try:
            doc = load_presets(self._context.project_root)
        except PresetLoadError as exc:
            return _fail(str(exc), {"errors": _err_dicts(exc)})

        results: list[dict[str, Any]] = []

        for preset in doc.presets:
            result = self.build_export(preset.name)
            results.append(result)

        success_count = sum(1 for r in results if r.get("success"))
        data = {
            "total": len(doc.presets),
            "success_count": success_count,
            "results": results,
        }
        if success_count == len(doc.presets):
            return _ok(
                f"Build-all completed for {len(doc.presets)} preset(s)",
                data,
            )
        return _fail("Build-all completed with failures", data)


def _ok(message: str, data: Any = None) -> dict[str, Any]:
    return {"success": True, "message": message, "data": data or {}}


def _fail(message: str, data: Any = None) -> dict[str, Any]:
    return {"success": False, "message": message, "data": data or {}}


def _err_dicts(exc: PresetLoadError) -> list[dict[str, str]]:
    return [e.to_dict() for e in exc.errors]


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in name)


def _validate_export_preset_for_project(
    preset: ExportPreset, project_root: str | Path,
) -> list[dict[str, str]]:
    errors = validate_preset(preset)
    errors.extend(validate_preset_against_project(preset, project_root))
    return [error.to_dict() for error in errors]
