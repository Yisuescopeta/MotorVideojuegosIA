"""Tests for export CLI contract."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
