"""Tests for export CLI contract."""

import json
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
    def test_gradle_missing_is_unhealthy_when_android_sdk_and_java_exist(self):
        from engine.export import diagnostics

        with tempfile.TemporaryDirectory() as tmpdir:
            empty_template = Path(tmpdir) / "template"
            empty_template.mkdir()

            def fake_which(name):
                return "C:/Java/bin/java.exe" if name in {"java", "java.exe"} else None

            with (
                patch.dict(diagnostics.os.environ, {"ANDROID_HOME": "C:/Android/Sdk"}, clear=False),
                patch.object(diagnostics.shutil, "which", side_effect=fake_which),
                patch.object(diagnostics, "_android_template_dir", return_value=empty_template),
            ):
                result = diagnostics.run_export_doctor(project_root=tmpdir)

        self.assertFalse(result["healthy"])
        self.assertFalse(result["checks"]["gradle_available"])
        self.assertTrue(any("TOOLCHAIN_UNAVAILABLE: Gradle not found" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
