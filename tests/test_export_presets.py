"""Tests for export presets: models, schema, loader, migrations."""

import json
import tempfile
import unittest
from pathlib import Path

from engine.export.models import (
    ExportPreset,
    PresetsDocument,
)
from engine.export.preset_loader import (
    PresetLoadError,
    get_preset_by_name,
    list_preset_names,
    load_presets,
)
from engine.export.preset_migrations import migrate_presets
from engine.export.preset_schema import (
    validate_preset,
    validate_presets_document,
    validate_presets_raw,
)


class TestExportModels(unittest.TestCase):
    def test_export_preset_from_dict_minimal(self):
        data = {
            "name": "My Preset",
            "platform": "windows",
            "output_path": "dist/windows/Test",
            "entry_scene": "levels/test.json",
        }
        preset = ExportPreset.from_dict(data)
        self.assertEqual(preset.name, "My Preset")
        self.assertEqual(preset.platform, "windows")
        self.assertEqual(preset.mode, "release")
        self.assertFalse(preset.include_debug_tools)

    def test_export_preset_to_dict_roundtrip(self):
        data = {
            "name": "Roundtrip",
            "platform": "windows",
            "architecture": "x86_64",
            "mode": "debug",
            "output_path": "dist/windows/Roundtrip",
            "entry_scene": "levels/level_1.json",
            "display_name": "RT",
            "application_id": "com.test.rt",
            "version_name": "1.0.0",
            "version_code": 2,
            "bundle_mode": "directory",
            "include_debug_tools": True,
            "window": {"width": 800, "height": 600},
        }
        preset = ExportPreset.from_dict(data)
        result = preset.to_dict()
        self.assertEqual(result["name"], "Roundtrip")
        self.assertEqual(result["mode"], "debug")
        self.assertEqual(result["version_code"], 2)
        self.assertEqual(result["window"]["width"], 800)

    def test_presets_document_from_dict(self):
        data = {
            "schema_version": 1,
            "presets": [
                {"name": "A", "platform": "windows", "output_path": "dist/a", "entry_scene": "x.json"},
                {"name": "B", "platform": "linux", "output_path": "dist/b", "entry_scene": "y.json"},
            ],
        }
        doc = PresetsDocument.from_dict(data)
        self.assertEqual(doc.schema_version, 1)
        self.assertEqual(len(doc.presets), 2)
        self.assertEqual(doc.presets[0].name, "A")


class TestExportPresetSchema(unittest.TestCase):
    def test_valid_preset_passes(self):
        preset = ExportPreset(
            name="Windows Test",
            platform="windows",
            output_path="dist/export/windows/Test",
            entry_scene="levels/test.json",
        )
        errors = validate_preset(preset)
        self.assertEqual(len(errors), 0)

    def test_missing_name(self):
        preset = ExportPreset(name="", platform="windows", output_path="dist/x", entry_scene="a.json")
        errors = validate_preset(preset)
        self.assertTrue(any(e.code == "PRESET_NAME_REQUIRED" for e in errors))

    def test_invalid_platform(self):
        preset = ExportPreset(name="X", platform="nintendo", output_path="dist/x", entry_scene="a.json")
        errors = validate_preset(preset)
        self.assertTrue(any(e.code == "INVALID_PLATFORM" for e in errors))

    def test_missing_output_path(self):
        preset = ExportPreset(name="X", platform="windows", output_path="", entry_scene="a.json")
        errors = validate_preset(preset)
        self.assertTrue(any(e.code == "OUTPUT_PATH_REQUIRED" for e in errors))

    def test_valid_device_profile_window_passes(self):
        preset = ExportPreset(
            name="Windows Mobile Preview",
            platform="windows",
            output_path="dist/x",
            entry_scene="a.json",
            window={"device_profile": "mobile_portrait"},
        )
        errors = validate_preset(preset)
        self.assertFalse(any(e.code == "INVALID_DEVICE_PROFILE" for e in errors))

    def test_unknown_device_profile_window_fails(self):
        preset = ExportPreset(
            name="Windows Bad Profile",
            platform="windows",
            output_path="dist/x",
            entry_scene="a.json",
            window={"device_profile": "watch"},
        )
        errors = validate_preset(preset)
        self.assertTrue(any(e.code == "INVALID_DEVICE_PROFILE" for e in errors))

    def test_android_requires_application_id(self):
        preset = ExportPreset(
            name="Android X", platform="android",
            output_path="dist/export/android/x.apk",
            entry_scene="levels/x.json",
            application_id="",
        )
        errors = validate_preset(preset)
        self.assertTrue(any(e.code == "APPLICATION_ID_REQUIRED" for e in errors))

    def test_validate_raw_missing_schema(self):
        errors = validate_presets_raw({"presets": []})
        self.assertTrue(any(e.code == "MISSING_SCHEMA_VERSION" for e in errors))

    def test_validate_raw_missing_presets(self):
        errors = validate_presets_raw({"schema_version": 1})
        self.assertTrue(any(e.code == "MISSING_PRESETS" for e in errors))

    def test_duplicate_names(self):
        doc = PresetsDocument(
            schema_version=1,
            presets=[
                ExportPreset(name="A", platform="windows", output_path="dist/a", entry_scene="a.json"),
                ExportPreset(name="A", platform="linux", output_path="dist/b", entry_scene="b.json"),
            ],
        )
        errors = validate_presets_document(doc)
        self.assertTrue(any(e.code == "DUPLICATE_PRESET_NAME" for e in errors))


class TestExportPresetLoader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.presets_path = Path(self.tmp) / "export_presets.motor.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_presets(self, data):
        self.presets_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def test_load_valid_presets(self):
        self._write_presets({
            "schema_version": 1,
            "presets": [
                {"name": "A", "platform": "windows", "output_path": "dist/a", "entry_scene": "a.json"},
            ],
        })
        doc = load_presets(str(self.tmp))
        self.assertEqual(len(doc.presets), 1)
        self.assertEqual(doc.presets[0].name, "A")

    def test_load_missing_file_raises(self):
        with self.assertRaises(PresetLoadError) as cm:
            load_presets(str(self.tmp))
        self.assertTrue(any(e.code == "PRESETS_FILE_NOT_FOUND" for e in cm.exception.errors))

    def test_load_invalid_json_raises(self):
        self.presets_path.write_text("not json", encoding="utf-8")
        with self.assertRaises(PresetLoadError) as cm:
            load_presets(str(self.tmp))
        self.assertTrue(any(e.code == "INVALID_JSON" for e in cm.exception.errors))

    def test_list_preset_names(self):
        self._write_presets({
            "schema_version": 1,
            "presets": [
                {"name": "Windows", "platform": "windows", "output_path": "dist/w", "entry_scene": "a.json"},
                {"name": "Android", "platform": "android", "output_path": "dist/a.apk", "entry_scene": "b.json", "application_id": "com.test"},
            ],
        })
        doc = load_presets(str(self.tmp))
        names = list_preset_names(doc)
        self.assertEqual(names, ["Windows", "Android"])

    def test_get_preset_by_name(self):
        self._write_presets({
            "schema_version": 1,
            "presets": [
                {"name": "Windows", "platform": "windows", "output_path": "dist/w", "entry_scene": "a.json"},
            ],
        })
        doc = load_presets(str(self.tmp))
        preset = get_preset_by_name(doc, "Windows")
        self.assertIsNotNone(preset)
        self.assertEqual(preset.platform, "windows")

        preset = get_preset_by_name(doc, "Missing")
        self.assertIsNone(preset)


class TestExportPresetMigrations(unittest.TestCase):
    def test_v0_to_v1_adds_defaults(self):
        data = {
            "presets": [
                {"name": "Old", "platform": "windows", "output_path": "dist/o", "entry_scene": "o.json"},
            ],
        }
        result = migrate_presets(data)
        self.assertEqual(result["schema_version"], 1)
        preset = result["presets"][0]
        self.assertEqual(preset["bundle_mode"], "packed")
        self.assertFalse(preset["include_debug_tools"])
        self.assertEqual(preset["version_name"], "0.1.0")
        self.assertEqual(preset["version_code"], 1)

    def test_migration_idempotent(self):
        data = {
            "schema_version": 1,
            "presets": [
                {
                    "name": "A", "platform": "windows",
                    "output_path": "dist/a", "entry_scene": "a.json",
                    "bundle_mode": "packed", "include_debug_tools": False,
                },
            ],
        }
        result = migrate_presets(data)
        result2 = migrate_presets(result)
        self.assertEqual(result, result2)


if __name__ == "__main__":
    unittest.main()
