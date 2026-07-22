from __future__ import annotations

import unittest

from engine.serialization.schema import (
    migrate_scene_data,
    migrate_scene_data_with_report,
    validate_scene_data,
)


class SchemaV3MigrationTests(unittest.TestCase):
    def test_v2_parent_name_migrates_deterministically_to_parent_id(self) -> None:
        payload = {
            "schema_version": 2,
            "name": "Migration",
            "entities": [
                {"id": "root-id", "name": "Root", "components": {}},
                {"id": "child-id", "name": "Child", "parent": "Root", "components": {}},
            ],
            "rules": [],
            "feature_metadata": {},
        }

        first = migrate_scene_data(payload)
        second = migrate_scene_data(payload)

        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], 3)
        self.assertIsNone(first["entities"][0]["parent_id"])
        self.assertEqual(first["entities"][1]["parent_id"], "root-id")
        self.assertEqual(validate_scene_data(first), [])

    def test_v3_unknown_parent_id_is_a_blocking_validation_diagnostic(self) -> None:
        payload = migrate_scene_data(
            {
                "schema_version": 3,
                "name": "InvalidV3",
                "entities": [
                    {"id": "child-id", "name": "Child", "parent_id": "missing", "components": {}}
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        errors = validate_scene_data(payload)

        self.assertTrue(any("parent_id" in error and "unknown parent id" in error for error in errors))

    def test_duplicate_ids_remain_diagnostic_instead_of_being_rewritten(self) -> None:
        payload = migrate_scene_data(
            {
                "schema_version": 2,
                "name": "DuplicateIds",
                "entities": [
                    {"id": "duplicate", "name": "A", "components": {}},
                    {"id": "duplicate", "name": "B", "components": {}},
                ],
                "rules": [],
                "feature_metadata": {},
            }
        )

        errors = validate_scene_data(payload)

        self.assertTrue(any("duplicate entity id" in error for error in errors))

    def test_migration_report_is_deterministic_and_contains_parent_count(self) -> None:
        payload = {
            "schema_version": 2,
            "name": "Report",
            "entities": [
                {"id": "root", "name": "Root", "components": {}},
                {"id": "child", "name": "Child", "parent": "Root", "components": {}},
            ],
            "rules": [],
            "feature_metadata": {},
        }

        first, first_report = migrate_scene_data_with_report(payload)
        second, second_report = migrate_scene_data_with_report(payload)

        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)
        self.assertTrue(first_report.migrated)
        self.assertEqual(first_report.source_version, 2)
        self.assertEqual(first_report.target_version, 3)
        self.assertEqual(first_report.parent_references_migrated, 1)
        self.assertEqual(first_report.diagnostics, ())


if __name__ == "__main__":
    unittest.main()
