"""Tests for engine.editor.export_panel — controller-only, no rendering."""

import unittest
from typing import Any, Optional

# Verify import is clean in headless env (no pyray, no render)
from engine.editor.export_panel import ExportPanel


class FakeEngineAPI:
    """Fake EngineAPI implementing only the export protocol used by ExportPanel."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def _record(self, method: str, **kw: Any) -> dict:
        self.calls.append({"method": method, **kw})
        return {}

    def list_export_presets(self) -> dict:
        self._record("list_export_presets")
        return {
            "success": True,
            "message": "Found 2 export preset(s)",
            "data": {
                "count": 2,
                "names": ["Windows Desktop", "Android"],
                "presets": [
                    {
                        "name": "Windows Desktop", "platform": "windows",
                        "mode": "release", "output_path": "dist/windows/App",
                        "entry_scene": "levels/main.json",
                        "bundle_mode": "packed", "version_name": "1.0",
                    },
                    {
                        "name": "Android", "platform": "android",
                        "mode": "debug", "output_path": "dist/android/app.apk",
                        "entry_scene": "levels/main.json",
                        "bundle_mode": "apk", "version_name": "0.2",
                    },
                ],
            },
        }

    def validate_export_preset(self, name: Optional[str] = None) -> dict:
        self._record("validate_export_preset", name=name)
        return {
            "success": True,
            "message": "All presets validated successfully.",
            "data": {"checked": 2, "errors": []},
        }

    def export_doctor(self) -> dict:
        self._record("export_doctor")
        return {
            "success": True,
            "message": "Export toolchain is healthy.",
            "data": {
                "healthy": True,
                "checks": {
                    "pyinstaller_available": True,
                    "pip_available": True,
                },
                "issues": [],
                "warnings": [],
            },
        }

    def build_export(self, name: str) -> dict:
        self._record("build_export", name=name)
        return {
            "success": True,
            "message": "Build completed for 'Windows Desktop'",
            "data": {
                "preset": name,
                "platform": "windows",
                "success": True,
                "duration_seconds": 2.34,
                "artifacts": ["dist/windows/App.exe"],
                "report": ".motor/build/reports/Windows_Desktop.json",
            },
        }

    def build_all_exports(self) -> dict:
        self._record("build_all_exports")
        return {
            "success": True,
            "message": "Build-all completed for 2 preset(s)",
            "data": {
                "total": 2,
                "success_count": 2,
                "results": [
                    {"preset": "Windows Desktop", "success": True},
                    {"preset": "Android", "success": True},
                ],
            },
        }


class TestExportPanelDelegation(unittest.TestCase):
    """ExportPanel delegates to EngineAPI, does not duplicate logic."""

    def setUp(self) -> None:
        self.fake = FakeEngineAPI()
        self.panel = ExportPanel()
        self.panel.bind_api(self.fake)

    # ── list_presets ────────────────────────────────────────────────

    def test_list_presets_delegates_to_api(self):
        result = self.panel.list_presets()
        self.assertTrue(result["success"])
        self.assertEqual(result["ui_total"], 2)
        self.assertEqual(self.fake.calls[0]["method"], "list_export_presets")

    def test_list_presets_ui_items_structure(self):
        result = self.panel.list_presets()
        self.assertIn("ui_items", result)
        self.assertIsInstance(result["ui_items"], list)
        first = result["ui_items"][0]
        self.assertEqual(first["name"], "Windows Desktop")
        self.assertEqual(first["platform"], "windows")
        self.assertIn("mode", first)
        self.assertIn("output_path", first)

    # ── validate_preset ─────────────────────────────────────────────

    def test_validate_single_preset_delegates(self):
        result = self.panel.validate_preset("Windows Desktop")
        self.assertTrue(result["success"])
        self.assertEqual(self.fake.calls[0]["method"], "validate_export_preset")
        self.assertEqual(self.fake.calls[0]["name"], "Windows Desktop")

    def test_validate_all_presets_delegates(self):
        result = self.panel.validate_preset(None)
        self.assertTrue(result["success"])
        self.assertEqual(self.fake.calls[0]["name"], None)

    def test_validate_ui_error_fields(self):
        result = self.panel.validate_preset("X")
        self.assertIn("ui_error_count", result)
        self.assertIn("ui_errors", result)
        self.assertEqual(result["ui_error_count"], 0)

    # ── doctor ──────────────────────────────────────────────────────

    def test_doctor_delegates_to_api(self):
        result = self.panel.doctor()
        self.assertTrue(result["success"])
        self.assertEqual(self.fake.calls[0]["method"], "export_doctor")

    def test_doctor_ui_checks(self):
        result = self.panel.doctor()
        self.assertIn("ui_checks", result)
        self.assertIn("ui_healthy", result)
        self.assertTrue(result["ui_healthy"])
        self.assertEqual(len(result["ui_checks"]), 2)
        self.assertEqual(result["ui_checks"][0]["name"], "pyinstaller_available")

    def test_doctor_ui_checks_include_issues_and_warnings(self):
        self.fake.export_doctor = lambda: {
            "success": False,
            "message": "Export toolchain has issues.",
            "data": {
                "healthy": False,
                "checks": {"pyinstaller_available": False},
                "issues": ["TOOLCHAIN_UNAVAILABLE: PyInstaller not found"],
                "warnings": ["ANDROID_HOME not set"],
            },
        }

        result = self.panel.doctor()

        self.assertFalse(result["ui_healthy"])
        self.assertTrue(any(item["status"] == "err" for item in result["ui_checks"]))
        self.assertTrue(any(item["status"] == "warn" for item in result["ui_checks"]))

    def test_unbound_panel_returns_controlled_errors(self):
        panel = ExportPanel()

        list_result = panel.list_presets()
        validate_result = panel.validate_preset()
        doctor_result = panel.doctor()

        self.assertFalse(list_result["success"])
        self.assertEqual(list_result["ui_total"], 0)
        self.assertFalse(validate_result["success"])
        self.assertEqual(validate_result["ui_error_count"], 1)
        self.assertFalse(doctor_result["success"])
        self.assertFalse(doctor_result["ui_healthy"])

    # ── build_export ────────────────────────────────────────────────

    def test_build_export_delegates(self):
        result = self.panel.build_export("Windows Desktop")
        self.assertTrue(result["success"])
        self.assertEqual(self.fake.calls[0]["method"], "build_export")
        self.assertEqual(self.fake.calls[0]["name"], "Windows Desktop")

    def test_build_export_ui_fields(self):
        result = self.panel.build_export("Windows Desktop")
        self.assertIn("ui_artifacts", result)
        self.assertIn("ui_duration", result)
        self.assertIn("ui_report", result)
        self.assertEqual(result["ui_artifacts"], ["dist/windows/App.exe"])
        self.assertEqual(result["ui_duration"], 2.34)

    # ── build_all_exports ───────────────────────────────────────────

    def test_build_all_exports_delegates(self):
        result = self.panel.build_all_exports()
        self.assertTrue(result["success"])
        self.assertEqual(self.fake.calls[0]["method"], "build_all_exports")

    def test_build_all_exports_ui_results(self):
        result = self.panel.build_all_exports()
        self.assertEqual(result["ui_total"], 2)
        self.assertEqual(result["ui_success_count"], 2)
        self.assertEqual(len(result["ui_results"]), 2)
        self.assertEqual(result["ui_results"][0]["preset"], "Windows Desktop")
        self.assertTrue(result["ui_results"][0]["success"])

    # ── safety / import ─────────────────────────────────────────────

    def test_pyray_imported_for_render(self):
        """Panel imports pyray for its render() method (controller+view)."""
        import engine.editor.export_panel as ep
        source = ep.__file__
        if source:
            with open(source, encoding="utf-8") as fh:
                content = fh.read()
            self.assertIn("import pyray", content)
            self.assertIn("def render", content)

    def test_no_exporter_imports(self):
        """Panel must not import exporter/internal modules directly."""
        import engine.editor.export_panel as ep
        source = ep.__file__
        if source:
            with open(source, encoding="utf-8") as fh:
                content = fh.read()
            forbidden = [
                "engine.export.preset_loader",
                "engine.export.preset_schema",
                "engine.export.exporter_registry",
                "engine.export.windows_exporter",
                "engine.export.linux_exporter",
                "engine.export.android_exporter",
                "engine.export.macos_exporter",
                "engine.export.ios_exporter",
                "engine.export.models",
                "engine.export.content_pack",
                "engine.export.diagnostics",
                "engine.export.reports",
                "engine.export.validator",
            ]
            for mod in forbidden:
                self.assertNotIn(mod, content, f"ExportPanel must not import {mod}")


if __name__ == "__main__":
    unittest.main()
