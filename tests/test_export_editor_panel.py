"""Tests for engine.editor.export_panel."""

import unittest
from typing import Any, Optional
from unittest.mock import Mock

from engine.editor.export_panel import ExportPanel


class FakeEngineAPI:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.scene_items = [
            {
                "name": "Platformer Test Scene",
                "path": "levels/platformer_test_scene.json",
                "absolute_path": "C:/project/levels/platformer_test_scene.json",
            },
            {
                "name": "Main Scene",
                "path": "levels/main.json",
                "absolute_path": "C:/project/levels/main.json",
            },
            {
                "name": "Boss Scene",
                "path": "levels/boss.json",
                "absolute_path": "C:/project/levels/boss.json",
            },
        ]
        self.active_scene = "levels/platformer_test_scene.json"

    def _record(self, method: str, **kw: Any) -> dict[str, Any]:
        self.calls.append({"method": method, **kw})
        return {}

    def list_export_presets(self) -> dict[str, Any]:
        self._record("list_export_presets")
        return {
            "success": True,
            "message": "Found 2 export preset(s)",
            "data": {
                "count": 2,
                "names": ["Windows Desktop", "Android"],
                "presets": [
                    {
                        "name": "Windows Desktop",
                        "platform": "windows",
                        "mode": "release",
                        "output_path": "dist/windows/App",
                        "entry_scene": "levels/main.json",
                        "bundle_mode": "packed",
                        "version_name": "1.0",
                    },
                    {
                        "name": "Android",
                        "platform": "android",
                        "mode": "debug",
                        "output_path": "dist/android/app.apk",
                        "entry_scene": "levels/boss.json",
                        "bundle_mode": "apk",
                        "version_name": "0.2",
                    },
                ],
            },
        }

    def list_export_entry_scenes(self) -> dict[str, Any]:
        self._record("list_export_entry_scenes")
        return {
            "success": True,
            "message": f"Found {len(self.scene_items)} scene(s)",
            "data": {
                "scenes": list(self.scene_items),
                "active_scene": self.active_scene,
            },
        }

    def validate_export_preset(self, name: Optional[str] = None) -> dict[str, Any]:
        self._record("validate_export_preset", name=name)
        return {
            "success": True,
            "message": "All presets validated successfully.",
            "data": {"checked": 2, "errors": []},
        }

    def export_doctor(self) -> dict[str, Any]:
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

    def build_export(self, name: str) -> dict[str, Any]:
        self._record("build_export", name=name)
        return {
            "success": True,
            "message": f"Build completed for '{name}'",
            "data": {
                "preset": name,
                "platform": "windows",
                "mode": "release",
                "success": True,
                "duration_seconds": 2.34,
                "artifacts": ["dist/windows/App.exe"],
                "report": ".motor/build/reports/Windows_Desktop.json",
                "effective_entry_scene": "levels/main.json",
                "entry_scene_override": None,
            },
        }

    def build_export_for_scene(self, name: str, entry_scene: str) -> dict[str, Any]:
        self._record("build_export_for_scene", name=name, entry_scene=entry_scene)
        return {
            "success": True,
            "message": f"Build completed for '{name}'",
            "data": {
                "preset": name,
                "platform": "windows",
                "mode": "release",
                "success": True,
                "duration_seconds": 1.11,
                "artifacts": ["dist/windows/App.exe"],
                "report": ".motor/build/reports/Windows_Desktop.json",
                "effective_entry_scene": entry_scene,
                "entry_scene_override": entry_scene,
            },
        }

    def build_all_exports(self) -> dict[str, Any]:
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
    def setUp(self) -> None:
        self.fake = FakeEngineAPI()
        self.panel = ExportPanel()
        self.panel.bind_api(self.fake)

    def test_list_presets_delegates_to_api(self) -> None:
        result = self.panel.list_presets()
        self.assertTrue(result["success"])
        self.assertEqual(result["ui_total"], 2)
        self.assertEqual(self.fake.calls[0]["method"], "list_export_presets")

    def test_list_presets_ui_items_structure(self) -> None:
        result = self.panel.list_presets()
        first = result["ui_items"][0]
        self.assertEqual(first["name"], "Windows Desktop")
        self.assertEqual(first["platform"], "windows")
        self.assertEqual(first["entry_scene"], "levels/main.json")

    def test_list_entry_scenes_delegates_to_api(self) -> None:
        result = self.panel.list_entry_scenes()
        self.assertTrue(result["success"])
        self.assertEqual(result["ui_active_scene"], "levels/platformer_test_scene.json")
        self.assertEqual(self.fake.calls[0]["method"], "list_export_entry_scenes")

    def test_refresh_export_options_loads_presets_and_scenes(self) -> None:
        self.panel.refresh_export_options()
        self.assertEqual(len(self.panel._presets), 2)
        self.assertEqual(len(self.panel._scene_items), 3)
        self.assertEqual(self.panel._selected_preset_name, "Windows Desktop")
        self.assertEqual(self.panel._selected_scene_path, "levels/platformer_test_scene.json")

    def test_refresh_defaults_to_preset_entry_scene_when_active_missing(self) -> None:
        self.fake.active_scene = "levels/missing.json"
        self.panel.refresh_export_options()
        self.assertEqual(self.panel._selected_scene_path, "levels/main.json")

    def test_refresh_defaults_to_first_scene_when_active_and_preset_missing(self) -> None:
        self.fake.active_scene = "levels/missing.json"
        original = self.fake.list_export_presets

        def _missing_preset_entry() -> dict[str, Any]:
            result = original()
            result["data"]["presets"][0]["entry_scene"] = "levels/ghost.json"
            return result

        self.fake.list_export_presets = _missing_preset_entry
        self.panel.refresh_export_options()
        self.assertEqual(self.panel._selected_scene_path, "levels/platformer_test_scene.json")

    def test_validate_single_preset_delegates(self) -> None:
        result = self.panel.validate_preset("Windows Desktop")
        self.assertTrue(result["success"])
        self.assertEqual(self.fake.calls[0]["method"], "validate_export_preset")
        self.assertEqual(self.fake.calls[0]["name"], "Windows Desktop")

    def test_validate_ui_error_fields(self) -> None:
        result = self.panel.validate_preset("X")
        self.assertEqual(result["ui_error_count"], 0)
        self.assertEqual(result["ui_errors"], [])

    def test_doctor_delegates_to_api(self) -> None:
        result = self.panel.doctor()
        self.assertTrue(result["success"])
        self.assertEqual(self.fake.calls[0]["method"], "export_doctor")

    def test_doctor_ui_checks_include_issues_and_warnings(self) -> None:
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

    def test_unbound_panel_returns_controlled_errors(self) -> None:
        panel = ExportPanel()
        list_result = panel.list_presets()
        validate_result = panel.validate_preset()
        doctor_result = panel.doctor()
        scenes_result = panel.list_entry_scenes()

        self.assertFalse(list_result["success"])
        self.assertEqual(list_result["ui_total"], 0)
        self.assertFalse(validate_result["success"])
        self.assertEqual(validate_result["ui_error_count"], 1)
        self.assertFalse(doctor_result["success"])
        self.assertFalse(doctor_result["ui_healthy"])
        self.assertFalse(scenes_result["success"])
        self.assertEqual(scenes_result["ui_scene_items"], [])

    def test_build_export_delegates(self) -> None:
        result = self.panel.build_export("Windows Desktop")
        self.assertTrue(result["success"])
        self.assertEqual(self.fake.calls[0]["method"], "build_export")
        self.assertEqual(self.fake.calls[0]["name"], "Windows Desktop")

    def test_build_export_ui_fields(self) -> None:
        result = self.panel.build_export("Windows Desktop")
        self.assertEqual(result["ui_artifacts"], ["dist/windows/App.exe"])
        self.assertEqual(result["ui_duration"], 2.34)
        self.assertEqual(result["ui_effective_entry_scene"], "levels/main.json")
        self.assertIsNone(result["ui_entry_scene_override"])

    def test_build_export_for_scene_delegates(self) -> None:
        result = self.panel.build_export_for_scene("Windows Desktop", "levels/boss.json")
        self.assertTrue(result["success"])
        self.assertEqual(self.fake.calls[0]["method"], "build_export_for_scene")
        self.assertEqual(self.fake.calls[0]["entry_scene"], "levels/boss.json")

    def test_build_all_exports_delegates(self) -> None:
        result = self.panel.build_all_exports()
        self.assertTrue(result["success"])
        self.assertEqual(self.fake.calls[0]["method"], "build_all_exports")

    def test_build_all_exports_ui_results(self) -> None:
        result = self.panel.build_all_exports()
        self.assertEqual(result["ui_total"], 2)
        self.assertEqual(result["ui_success_count"], 2)
        self.assertEqual(result["ui_results"][0]["preset"], "Windows Desktop")

    def test_select_previous_and_next_scene(self) -> None:
        self.panel.refresh_export_options()
        self.panel._selected_scene_path = "levels/main.json"
        self.panel._select_previous_scene()
        self.assertEqual(self.panel._selected_scene_path, "levels/platformer_test_scene.json")
        self.panel._select_next_scene()
        self.assertEqual(self.panel._selected_scene_path, "levels/main.json")

    def test_select_active_scene_refreshes_current_active_scene(self) -> None:
        self.panel.refresh_export_options()
        self.fake.active_scene = "levels/boss.json"
        self.panel._selected_scene_path = "levels/main.json"
        self.panel._select_active_scene()
        self.assertEqual(self.panel._selected_scene_path, "levels/boss.json")

    def test_bind_prebuild_save_callback_stores_callback(self) -> None:
        callback = Mock(return_value=True)
        self.panel.bind_prebuild_save_callback(callback)
        self.assertIs(self.panel._prebuild_save_callback, callback)

    def test_run_build_selected_uses_selected_scene_override(self) -> None:
        self.panel.refresh_export_options()
        self.panel._selected_scene_path = "levels/boss.json"
        self.panel._run_build_selected()
        self.assertEqual(self.fake.calls[-1]["method"], "build_export_for_scene")
        self.assertEqual(self.fake.calls[-1]["name"], "Windows Desktop")
        self.assertEqual(self.fake.calls[-1]["entry_scene"], "levels/boss.json")
        self.assertIn(("info", "Entry Scene: levels/boss.json"), self.panel._logs)

    def test_run_build_selected_without_scene_logs_error(self) -> None:
        self.panel.refresh_export_options()
        self.panel._selected_scene_path = ""
        call_count_before = len(self.fake.calls)
        self.panel._run_build_selected()
        self.assertEqual(len(self.fake.calls), call_count_before)
        self.assertIn(("err", "No entry scene selected."), self.panel._logs)

    def test_run_build_selected_cancels_when_prebuild_save_fails(self) -> None:
        self.panel.refresh_export_options()
        callback = Mock(return_value=False)
        self.panel.bind_prebuild_save_callback(callback)
        call_count_before = len(self.fake.calls)
        self.panel._run_build_selected()
        callback.assert_called_once_with()
        self.assertEqual(len(self.fake.calls), call_count_before)
        self.assertIn(("err", "Build cancelled: could not save dirty scenes."), self.panel._logs)

    def test_pyray_imported_for_render(self) -> None:
        import engine.editor.export_panel as export_panel_module

        source = export_panel_module.__file__
        if source:
            with open(source, encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("import pyray", content)
            self.assertIn("def render", content)

    def test_no_exporter_imports(self) -> None:
        import engine.editor.export_panel as export_panel_module

        source = export_panel_module.__file__
        if source:
            with open(source, encoding="utf-8") as handle:
                content = handle.read()
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
            for module_name in forbidden:
                self.assertNotIn(module_name, content, f"ExportPanel must not import {module_name}")


if __name__ == "__main__":
    unittest.main()
