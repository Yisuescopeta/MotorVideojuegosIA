"""Tests for export CLI contract."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _run(*args):
    cmd = [sys.executable, "-m", "motor"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    return result.returncode, result.stdout.strip(), result.stderr.strip()


class TestExportCLIContract(unittest.TestCase):
    def test_presets_list_json(self):
        code, stdout, stderr = _run(
            "export", "presets", "list", "--project", str(ROOT), "--json",
        )
        self.assertEqual(code, 0, f"stderr: {stderr}")
        data = json.loads(stdout)
        self.assertIn("success", data)
        self.assertIn("message", data)
        self.assertIn("data", data)
        if data["success"]:
            self.assertIn("presets", data["data"])

    def test_presets_validate_json(self):
        code, stdout, stderr = _run(
            "export", "presets", "validate", "--project", str(ROOT), "--json",
        )
        self.assertEqual(code, 0)
        data = json.loads(stdout)
        self.assertIn("success", data)

    def test_export_doctor_json(self):
        code, stdout, stderr = _run(
            "export", "doctor", "--project", str(ROOT), "--json",
        )
        self.assertIn(code, (0, 1))
        data = json.loads(stdout)
        self.assertIn("success", data)
        self.assertIn("data", data)
        self.assertIn("checks", data["data"])
        self.assertIn("pyinstaller_resolution", data["data"]["checks"])

    def test_export_pack_json(self):
        code, stdout, stderr = _run(
            "export", "pack", "Windows Desktop", "--project", str(ROOT), "--json",
        )
        self.assertIn(code, (0, 1))
        data = json.loads(stdout)
        self.assertIn("success", data)

    def test_export_build_json(self):
        code, stdout, stderr = _run(
            "export", "build", "Windows Desktop", "--project", str(ROOT), "--json",
        )
        self.assertIn(code, (0, 1))
        data = json.loads(stdout)
        self.assertIn("success", data)
        if not data["success"]:
            errors = data.get("data", {}).get("errors", [])
            self.assertTrue(
                any("TOOLCHAIN_UNAVAILABLE" in str(e) for e in errors)
                or "PyInstaller" in str(errors),
                f"Expected TOOLCHAIN_UNAVAILABLE: {errors}",
            )

    def test_contract_json_structure(self):
        code, stdout, stderr = _run(
            "export", "presets", "list", "--project", str(ROOT), "--json",
        )
        data = json.loads(stdout)
        self.assertIsInstance(data["success"], bool)
        self.assertIsInstance(data["message"], str)
        self.assertIsInstance(data["data"], (dict, list))

    def test_export_validation_error_to_dict_contract(self):
        from engine.export.models import ExportValidationError
        err = ExportValidationError(code="TEST_CODE", path="test.json", hint="test hint")
        d = err.to_dict()
        self.assertEqual(set(d.keys()), {"code", "path", "hint"})
        self.assertIsInstance(d["code"], str)
        self.assertIsInstance(d["path"], str)
        self.assertIsInstance(d["hint"], str)
        # Empty fields should still be present
        err2 = ExportValidationError(code="MINIMAL")
        d2 = err2.to_dict()
        self.assertEqual(set(d2.keys()), {"code", "path", "hint"})

    def test_export_pack_does_not_rewrite_project_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "levels").mkdir()
            (project / "assets").mkdir()
            (project / "scripts").mkdir()
            (project / "prefabs").mkdir()
            (project / "settings").mkdir()
            (project / "project.json").write_text(
                json.dumps(
                    {
                        "name": "PackSideEffectTest",
                        "version": 2,
                        "engine_version": "2026.03",
                        "paths": {
                            "assets": "assets",
                            "levels": "levels",
                            "prefabs": "prefabs",
                            "scripts": "scripts",
                            "settings": "settings",
                            "meta": ".motor/meta",
                            "build": ".motor/build",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (project / "export_presets.motor.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "presets": [
                            {
                                "name": "Pack Test",
                                "platform": "windows",
                                "mode": "debug",
                                "output_path": "dist/export/test",
                                "entry_scene": "levels/test.json",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (project / "levels" / "test.json").write_text(
                json.dumps({"schema_version": 2, "name": "Test", "entities": []}),
                encoding="utf-8",
            )
            meta_path = project / "levels" / "test.json.meta.json"
            meta_text = json.dumps(
                {
                    "guid": "ast_keep_me",
                    "source_path": "levels/test.json",
                    "path": "levels/test.json",
                    "asset_kind": "scene_data",
                },
                indent=4,
            )
            meta_path.write_text(meta_text, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "motor",
                    "export",
                    "pack",
                    "Pack Test",
                    "--project",
                    str(project),
                    "--json",
                ],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(meta_path.read_text(encoding="utf-8"), meta_text)
            self.assertFalse((project / "settings" / "project_settings.json").exists())


class TestExportDoctorDiagnostics(unittest.TestCase):
    def _write_android_presets(self, project: Path, compile_sdks: list[int]) -> None:
        project.joinpath("export_presets.motor.json").write_text(
            json.dumps({
                "schema_version": 1,
                "presets": [
                    {
                        "name": f"Android {compile_sdk}",
                        "platform": "android",
                        "mode": "debug",
                        "output_path": f"dist/android-{compile_sdk}.apk",
                        "entry_scene": "levels/main.json",
                        "application_id": f"com.example.sdk{compile_sdk}",
                        "min_sdk": 24,
                        "target_sdk": compile_sdk,
                        "compile_sdk": compile_sdk,
                    }
                    for compile_sdk in compile_sdks
                ],
            }),
            encoding="utf-8",
        )

    def test_gradle_missing_is_unhealthy_when_android_sdk_and_java_exist(self):
        from engine.export import android_environment, diagnostics

        with tempfile.TemporaryDirectory() as tmpdir:
            sdk = Path(tmpdir) / "sdk"
            (sdk / "platforms" / "android-35").mkdir(parents=True)
            (sdk / "build-tools" / "35.0.0").mkdir(parents=True)
            empty_template = Path(tmpdir) / "template"
            empty_template.mkdir()

            def fake_which(name):
                return "C:/Java/bin/java.exe" if name in {"java", "java.exe"} else None

            with (
                patch.dict(os.environ, {"ANDROID_HOME": str(sdk)}, clear=True),
                patch.object(android_environment.shutil, "which", side_effect=fake_which),
                patch.object(
                    android_environment,
                    "android_template_dir",
                    return_value=empty_template,
                ),
            ):
                result = diagnostics.run_export_doctor(project_root=tmpdir)

        self.assertFalse(result["healthy"])
        self.assertFalse(result["checks"]["gradle_available"])
        self.assertTrue(any("TOOLCHAIN_UNAVAILABLE: Gradle not found" in issue for issue in result["issues"]))

    def test_android_probe_reports_missing_and_installed_platform(self):
        from engine.export.android_environment import probe_android_environment

        with tempfile.TemporaryDirectory() as tmpdir:
            sdk = Path(tmpdir) / "sdk"
            sdk.mkdir()
            with patch.dict(os.environ, {"ANDROID_HOME": str(sdk)}, clear=True):
                missing = probe_android_environment(compile_sdk=35)
                platform = sdk / "platforms" / "android-35"
                platform.mkdir(parents=True)
                installed = probe_android_environment(compile_sdk=35)

        self.assertTrue(missing["android_sdk_available"])
        self.assertFalse(missing["android_platform_available"])
        self.assertEqual(missing["android_platform_path"], str(platform))
        self.assertTrue(installed["android_platform_available"])

    def test_android_probe_requires_installed_build_tools_version(self):
        from engine.export.android_environment import probe_android_environment

        with tempfile.TemporaryDirectory() as tmpdir:
            sdk = Path(tmpdir) / "sdk"
            sdk.mkdir()
            with patch.dict(os.environ, {"ANDROID_HOME": str(sdk)}, clear=True):
                absent = probe_android_environment()
                (sdk / "build-tools").mkdir()
                empty = probe_android_environment()
                (sdk / "build-tools" / "35.0.0").mkdir()
                installed = probe_android_environment()

        self.assertFalse(absent["android_build_tools_available"])
        self.assertFalse(empty["android_build_tools_available"])
        self.assertTrue(installed["android_build_tools_available"])

    def test_android_probe_falls_back_to_android_sdk_root(self):
        from engine.export.android_environment import probe_android_environment

        with tempfile.TemporaryDirectory() as tmpdir:
            sdk = Path(tmpdir) / "sdk"
            sdk.mkdir()
            with patch.dict(
                os.environ,
                {
                    "ANDROID_HOME": str(Path(tmpdir) / "missing-sdk"),
                    "ANDROID_SDK_ROOT": str(sdk),
                },
                clear=True,
            ):
                result = probe_android_environment()

        self.assertTrue(result["android_sdk_available"])
        self.assertEqual(result["android_home"], str(sdk))

    @unittest.skipIf(os.name == "nt", "Unix executable permissions only")
    def test_android_probe_reports_non_executable_gradle_wrapper(self):
        from engine.export import android_environment

        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            wrapper = project / "gradlew"
            wrapper.write_text("#!/bin/sh\n", encoding="utf-8")
            wrapper.chmod(0o644)
            wrapper_dir = project / "gradle" / "wrapper"
            wrapper_dir.mkdir(parents=True)
            (wrapper_dir / "gradle-wrapper.properties").write_text(
                "distributionUrl=x",
                encoding="utf-8",
            )
            (wrapper_dir / "gradle-wrapper.jar").write_bytes(b"jar")
            empty_template = project / "empty-template"
            empty_template.mkdir()

            with (
                patch.object(android_environment.shutil, "which", return_value=None),
                patch.object(
                    android_environment,
                    "android_template_dir",
                    return_value=empty_template,
                ),
            ):
                result = android_environment.probe_android_environment(project)

        self.assertTrue(result["gradle_wrapper_available"])
        self.assertFalse(result["gradle_wrapper_executable"])
        self.assertFalse(result["gradle_available"])

    def test_doctor_reports_each_missing_compile_sdk(self):
        from engine.export import android_environment, diagnostics

        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            self._write_android_presets(project, [35, 36])
            sdk = project / "sdk"
            (sdk / "platforms" / "android-35").mkdir(parents=True)
            (sdk / "build-tools" / "35.0.0").mkdir(parents=True)

            def fake_which(name):
                if name in {"java", "java.exe"}:
                    return "/tools/java"
                if name in {"gradle", "gradle.bat"}:
                    return "/tools/gradle"
                return None

            with (
                patch.dict(os.environ, {"ANDROID_HOME": str(sdk)}, clear=True),
                patch.object(android_environment.shutil, "which", side_effect=fake_which),
                patch.object(
                    diagnostics,
                    "resolve_pyinstaller",
                    return_value={
                        "pyinstaller_available": True,
                        "pyinstaller_path": "/tools/pyinstaller",
                        "pyinstaller_module_available": False,
                        "pyinstaller_resolution": "path_executable",
                    },
                ),
            ):
                result = diagnostics.run_export_doctor(project)

        platforms = result["checks"]["android_platforms"]
        self.assertEqual([item["compile_sdk"] for item in platforms], [35, 36])
        self.assertTrue(platforms[0]["android_platform_available"])
        self.assertFalse(platforms[1]["android_platform_available"])
        self.assertIn(
            "ANDROID_PLATFORM_MISSING: Install Android SDK Platform 36",
            result["issues"],
        )

    def test_doctor_does_not_require_android_sdk_without_android_presets(self):
        from engine.export import diagnostics

        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            project.joinpath("export_presets.motor.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "presets": [{
                        "name": "Desktop",
                        "platform": "windows",
                        "mode": "debug",
                        "output_path": "dist/desktop",
                        "entry_scene": "levels/main.json",
                    }],
                }),
                encoding="utf-8",
            )
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(
                    diagnostics,
                    "resolve_pyinstaller",
                    return_value={
                        "pyinstaller_available": True,
                        "pyinstaller_path": "/tools/pyinstaller",
                        "pyinstaller_module_available": False,
                        "pyinstaller_resolution": "path_executable",
                    },
                ),
            ):
                result = diagnostics.run_export_doctor(project)

        self.assertEqual(result["checks"]["android_platforms"], [])
        self.assertFalse(any("ANDROID_" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
