from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.editor_migration_fitness import evaluate_fitness
from tools.editor_migration_inventory import build_inventory


class EditorMigrationFitnessTests(unittest.TestCase):
    def test_current_repo_matches_g0_inventory_baseline(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        baseline_path = repo_root / "artifacts" / "refactor_editor_migration_v4" / "g0-01-inventory.json"
        current = build_inventory(repo_root)
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

        report = evaluate_fitness(current, baseline)

        self.assertTrue(report["passed"], report["violations"])
        self.assertEqual(report["violations"], [])

    def test_new_surface_consumer_and_boundary_are_reported(self) -> None:
        baseline = {
            "metrics": {},
            "scene_mutable_surfaces": [],
            "world_to_scene_consumers": [],
            "runtime_to_editor_boundary_edges": [],
            "parse_errors": [],
        }
        current = {
            "metrics": {},
            "scene_mutable_surfaces": [
                {"path": "engine/scenes/scene.py", "name": "data", "kind": "property"}
            ],
            "world_to_scene_consumers": [
                {
                    "path": "engine/editor/panel.py",
                    "category": "legacy_sync_api",
                    "symbol": "sync_from_edit_world",
                    "evidence": "entry.sync_from_edit_world()",
                }
            ],
            "runtime_to_editor_boundary_edges": [
                {"source": "engine.runtime.host", "target": "engine.editor.panel"}
            ],
            "parse_errors": [],
        }

        report = evaluate_fitness(current, baseline)

        self.assertFalse(report["passed"])
        self.assertEqual(
            {violation["rule"] for violation in report["violations"]},
            {
                "no_new_mutable_scene_surfaces",
                "no_new_world_to_scene_consumers",
                "runtime_cannot_import_editor_or_inspector",
            },
        )

    def test_parse_errors_are_blocking(self) -> None:
        baseline = {
            "metrics": {},
            "scene_mutable_surfaces": [],
            "world_to_scene_consumers": [],
            "runtime_to_editor_boundary_edges": [],
            "parse_errors": [],
        }
        current = {**baseline, "parse_errors": [{"path": "engine/broken.py", "error": "syntax"}]}

        report = evaluate_fitness(current, baseline)

        self.assertFalse(report["passed"])
        self.assertEqual(report["violations"][0]["rule"], "all_scoped_python_files_parse")

    def test_inventory_baseline_is_json_serializable(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "inventory.json"
            output.write_text(
                json.dumps(build_inventory(repo_root), sort_keys=True),
                encoding="utf-8",
            )
            json.loads(output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
