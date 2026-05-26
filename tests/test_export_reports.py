"""Tests for build report generation."""

import json
import tempfile
import unittest
from pathlib import Path

from engine.export.build_context import BuildContext
from engine.export.models import ExportPreset
from engine.export.reports import generate_build_report, write_build_report


class TestBuildReports(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.preset = ExportPreset(
            name="Test Preset",
            platform="windows",
            mode="release",
            output_path="dist/export/windows/Test",
            entry_scene="levels/test.json",
            display_name="Test Game",
            version_name="0.1.0",
        )
        self.ctx = BuildContext(self.preset, str(self.tmp))

    def tearDown(self):
        import shutil
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_generate_success_report(self):
        report = generate_build_report(self.ctx, True, 12.5)
        self.assertTrue(report["success"])
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["preset"], "Test Preset")
        self.assertEqual(report["platform"], "windows")
        self.assertEqual(report["mode"], "release")
        self.assertEqual(report["duration_seconds"], 12.5)
        self.assertIn("environment", report)

    def test_generate_failure_report(self):
        self.ctx.add_error("Something went wrong")
        report = generate_build_report(self.ctx, False, 2.0)
        self.assertFalse(report["success"])
        self.assertIn("Something went wrong", report["errors"])

    def test_report_includes_artifacts(self):
        self.ctx.add_artifact("dist/export/windows/Test/Test.exe", "executable", 1000000, "abc123")
        report = generate_build_report(self.ctx, True, 5.0)
        self.assertEqual(len(report["artifacts"]), 1)
        self.assertEqual(report["artifacts"][0]["kind"], "executable")

    def test_write_report_creates_file(self):
        report = generate_build_report(self.ctx, True, 1.0)
        path = write_build_report(report, str(self.tmp), "Test Preset")

        self.assertTrue(path.exists())
        self.assertIn("export_reports", str(path))
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["preset"], "Test Preset")

    def test_report_no_secrets(self):
        self.ctx.add_warning("keystore at /secret/path")
        self.ctx.add_error("keystore_password=super_secret_123")
        self.ctx.add_artifact("dist/key.pem", "keystore", 1000, "abc")
        report = generate_build_report(self.ctx, True, 1.0)
        report_str = json.dumps(report)

        self.assertNotIn("super_secret_123", report_str)
        self.assertNotIn("/secret/path", report_str)
        self.assertIn("[REDACTED]", report_str)

    def test_report_no_secrets_token_password(self):
        self.ctx.add_warning("token=abc123xyz secret=keepme")
        self.ctx.add_error("password=hunter2")
        report = generate_build_report(self.ctx, True, 1.0)
        report_str = json.dumps(report)

        self.assertNotIn("abc123xyz", report_str)
        self.assertNotIn("hunter2", report_str)
        self.assertNotIn("keepme", report_str)

    def test_report_no_secrets_keystore_fields(self):
        self.ctx.add_warning("keystore_path=/home/user/key.jks")
        self.ctx.add_warning("key_alias=mygame")
        self.ctx.add_warning("key_password=release123")
        report = generate_build_report(self.ctx, True, 1.0)
        report_str = json.dumps(report)

        self.assertNotIn("key.jks", report_str)
        self.assertNotIn("mygame", report_str)
        self.assertNotIn("release123", report_str)

    def test_timestamps_present(self):
        report = generate_build_report(self.ctx, True, 1.0)
        self.assertIn("started_at_utc", report)
        self.assertIn("finished_at_utc", report)
        self.assertNotEqual(report["started_at_utc"], "")


if __name__ == "__main__":
    unittest.main()
