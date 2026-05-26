"""Tests for export preset migrations."""

import unittest

from engine.export.preset_migrations import migrate_presets


class TestPresetMigrations(unittest.TestCase):
    def test_v0_missing_schema_version(self):
        data = {
            "presets": [
                {
                    "name": "legacy",
                    "platform": "windows",
                    "output_path": "dist/x",
                    "entry_scene": "x.json",
                },
            ],
        }
        result = migrate_presets(data)
        self.assertEqual(result["schema_version"], 1)

    def test_v0_preserves_existing_fields(self):
        data = {
            "presets": [
                {
                    "name": "keep",
                    "platform": "linux",
                    "output_path": "dist/keep",
                    "entry_scene": "keep.json",
                    "version_name": "2.0-beta",
                    "version_code": 42,
                },
            ],
        }
        result = migrate_presets(data)
        preset = result["presets"][0]
        self.assertEqual(preset["version_name"], "2.0-beta")
        self.assertEqual(preset["version_code"], 42)
        self.assertEqual(preset["bundle_mode"], "packed")

    def test_multiple_presets_migrated(self):
        data = {
            "presets": [
                {"name": "A", "platform": "windows", "output_path": "dist/a", "entry_scene": "a.json"},
                {"name": "B", "platform": "linux", "output_path": "dist/b", "entry_scene": "b.json"},
            ],
        }
        result = migrate_presets(data)
        self.assertEqual(len(result["presets"]), 2)
        for p in result["presets"]:
            self.assertIn("bundle_mode", p)
            self.assertIn("include_debug_tools", p)

    def test_double_migration_idempotent(self):
        data = {
            "presets": [
                {"name": "X", "platform": "windows", "output_path": "dist/x", "entry_scene": "x.json"},
            ],
        }
        r1 = migrate_presets(data)
        r2 = migrate_presets(r1)
        self.assertEqual(r1, r2)


if __name__ == "__main__":
    unittest.main()
