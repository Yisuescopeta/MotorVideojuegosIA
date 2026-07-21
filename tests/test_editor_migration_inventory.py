from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.editor_migration_inventory import build_inventory, render_markdown


class EditorMigrationInventoryTests(unittest.TestCase):
    def test_inventory_uses_ast_and_records_conservative_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "engine" / "scenes").mkdir(parents=True)
            (root / "engine" / "editor").mkdir(parents=True)
            (root / "engine" / "scenes" / "scene.py").write_text(
                """
class Scene:
    @property
    def data(self):
        return self._data

    def find_entity(self, name):
        return self._data['entities'][name]
""",
                encoding="utf-8",
            )
            (root / "engine" / "editor" / "panel.py").write_text(
                """
from engine.scenes.scene import Scene

def mutate(entry):
    entry.edit_world.get_entity_by_name('Actor').x = 2
    entry.scene.sync_from_edit_world()
""",
                encoding="utf-8",
            )

            inventory = build_inventory(root)

        metrics = inventory["metrics"]
        assert isinstance(metrics, dict)
        self.assertEqual(metrics["python_files"], 2)
        self.assertEqual(metrics["scene_mutable_surface_candidates"], 2)
        self.assertEqual(metrics["legacy_sync_consumers"], 1)
        self.assertEqual(metrics["direct_world_assignment_candidates"], 1)
        self.assertEqual(len(inventory["import_graph"]), 1)

    def test_real_repo_inventory_exposes_scene_and_runtime_boundary_metrics(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        inventory = build_inventory(repo_root)
        metrics = inventory["metrics"]
        assert isinstance(metrics, dict)
        self.assertGreater(metrics["python_files"], 100)
        self.assertGreater(metrics["scene_public_surfaces"], 0)
        self.assertGreater(metrics["scene_mutable_surface_candidates"], 0)
        self.assertGreater(metrics["legacy_sync_consumers"], 0)
        self.assertEqual(metrics["parse_errors"], 0)

    def test_markdown_report_contains_metrics_and_evidence(self) -> None:
        inventory = {
            "metrics": {"python_files": 2, "legacy_sync_consumers": 1},
            "scene_mutable_surfaces": [
                {"path": "engine/scenes/scene.py", "line": 4, "name": "data", "reason": "internal"}
            ],
            "world_to_scene_consumers": [
                {
                    "path": "engine/editor/panel.py",
                    "line": 8,
                    "category": "legacy_sync_api",
                    "symbol": "sync_from_edit_world",
                    "evidence": "entry.scene.sync_from_edit_world()",
                }
            ],
        }
        report = render_markdown(inventory)
        self.assertIn("G0 baseline inventory", report)
        self.assertIn("`legacy_sync_consumers`", report)
        self.assertIn("sync_from_edit_world", report)

    def test_inventory_is_json_serializable(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        payload = build_inventory(repo_root)
        json.dumps(payload, sort_keys=True)


if __name__ == "__main__":
    unittest.main()
