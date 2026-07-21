from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.editor_migration_benchmark import measure, run_benchmark


class EditorMigrationBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.scene_path = self.repo_root / "artifacts" / "refactor_editor_migration_v4" / "g0-04-reference_scene.json"
        self.budget_path = self.repo_root / "artifacts" / "refactor_editor_migration_v4" / "g0-04-budgets.json"

    def test_measure_reports_warmup_repeats_and_statistics(self) -> None:
        counter = iter(range(4))
        result = measure(lambda: next(counter), warmup=1, repeats=3)

        self.assertEqual(result["warmup"], 1)
        self.assertEqual(result["repeats"], 3)
        self.assertEqual(len(result["samples_ms"]), 3)
        self.assertIn("median_ms", result)
        self.assertIn("p95_ms", result)

    def test_reference_benchmark_passes_budgets(self) -> None:
        report = run_benchmark(self.scene_path, self.budget_path)

        self.assertTrue(report["passed"], report)
        self.assertEqual(report["scene"]["entity_count"], 3)
        self.assertEqual(
            set(report["operations"]),
            {"projection_create_world", "world_serialize", "world_clone"},
        )
        for operation in report["operations"].values():
            self.assertEqual(operation["repeats"], 7)
            self.assertTrue(operation["passed"], operation)

    def test_tight_budget_fails_without_changing_operation_measurement(self) -> None:
        budget = json.loads(self.budget_path.read_text(encoding="utf-8"))
        for operation in budget["operations"].values():
            operation["p95_ms"] = 0.0
        with tempfile.TemporaryDirectory() as temp_dir:
            budget_path = Path(temp_dir) / "budget.json"
            budget_path.write_text(json.dumps(budget), encoding="utf-8")
            report = run_benchmark(self.scene_path, budget_path)

        self.assertFalse(report["passed"])
        self.assertTrue(all("p95_ms" in operation for operation in report["operations"].values()))


if __name__ == "__main__":
    unittest.main()
