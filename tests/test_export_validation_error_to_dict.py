"""Tests for ExportValidationError.to_dict() contract.

Ensures to_dict always returns code, path, and hint keys.
"""
import unittest

from engine.export.models import ExportValidationError


class TestExportValidationErrorToDict(unittest.TestCase):
    def test_to_dict_all_keys_present_even_empty(self):
        err = ExportValidationError(code="MISSING_SCENE")
        d = err.to_dict()
        self.assertEqual(set(d.keys()), {"code", "path", "hint"})
        self.assertEqual(d["code"], "MISSING_SCENE")
        self.assertEqual(d["path"], "")
        self.assertEqual(d["hint"], "")

    def test_to_dict_with_path(self):
        err = ExportValidationError(code="BAD_FORMAT", path="levels/main.json")
        d = err.to_dict()
        self.assertEqual(d["code"], "BAD_FORMAT")
        self.assertEqual(d["path"], "levels/main.json")
        self.assertEqual(d["hint"], "")

    def test_to_dict_with_hint(self):
        err = ExportValidationError(
            code="MISSING_ENTRY",
            hint="Add an entry_scene to your preset.",
        )
        d = err.to_dict()
        self.assertEqual(d["code"], "MISSING_ENTRY")
        self.assertEqual(d["path"], "")
        self.assertEqual(d["hint"], "Add an entry_scene to your preset.")

    def test_to_dict_all_keys_filled(self):
        err = ExportValidationError(
            code="INVALID_PLATFORM",
            path="export_presets.json",
            hint="Use one of: windows, linux, macos, android, ios",
        )
        d = err.to_dict()
        self.assertEqual(d["code"], "INVALID_PLATFORM")
        self.assertEqual(d["path"], "export_presets.json")
        self.assertEqual(d["hint"], "Use one of: windows, linux, macos, android, ios")

    def test_to_dict_all_values_are_strings(self):
        err = ExportValidationError(code="TEST")
        d = err.to_dict()
        for key, val in d.items():
            self.assertIsInstance(val, str, f"Key '{key}' value should be str")

    def test_repr_unchanged(self):
        err = ExportValidationError(code="ERR", path="foo.json")
        r = repr(err)
        self.assertIn("ERR", r)
        self.assertIn("foo.json", r)


if __name__ == "__main__":
    unittest.main()
