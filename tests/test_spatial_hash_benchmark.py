import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.spatial_hash_benchmark import SPATIAL_HASH_BENCHMARK_VERSION, run_spatial_hash_benchmark

ROOT = Path(__file__).resolve().parents[1]


def _run_module(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    result = subprocess.run(
        [sys.executable, "-m", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Subprocess failed: {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


class SpatialHashBenchmarkTests(unittest.TestCase):
    def test_spatial_hash_benchmark_reports_required_schema(self) -> None:
        report = run_spatial_hash_benchmark(
            entity_count=32,
            query_count=8,
            ray_count=6,
            cell_size=16.0,
            columns=8,
            spacing=12.0,
            oversized_count=1,
            warmup=0,
            repeats=2,
        )

        self.assertEqual(report["benchmark_version"], SPATIAL_HASH_BENCHMARK_VERSION)
        self.assertEqual(report["parameters"]["entity_count"], 32)
        self.assertEqual(report["parameters"]["query_count"], 8)
        self.assertEqual(report["parameters"]["ray_count"], 6)
        self.assertEqual(report["counts"]["total_entries"], 33)
        self.assertEqual(report["counts"]["oversized_entry_count"], 1)
        self.assertIn("environment", report)
        self.assertIn("checksum", report)
        self.assertEqual(set(report["operations"]), {"insert", "query", "query_into", "ray_candidates"})
        for operation in report["operations"].values():
            self.assertGreaterEqual(operation["median_ms"], 0.0)
            self.assertGreaterEqual(operation["p95_ms"], operation["median_ms"])
            self.assertEqual(len(operation["samples_ms"]), 2)
            self.assertTrue(operation["stable_checksum"])

    def test_spatial_hash_benchmark_checksum_is_deterministic(self) -> None:
        first = run_spatial_hash_benchmark(
            entity_count=24,
            query_count=7,
            ray_count=5,
            cell_size=16.0,
            columns=6,
            spacing=12.0,
            warmup=0,
            repeats=1,
        )
        second = run_spatial_hash_benchmark(
            entity_count=24,
            query_count=7,
            ray_count=5,
            cell_size=16.0,
            columns=6,
            spacing=12.0,
            warmup=0,
            repeats=1,
        )

        self.assertEqual(first["counts"], second["counts"])
        self.assertEqual(first["checksum"], second["checksum"])
        self.assertEqual(
            {name: operation["checksum"] for name, operation in first["operations"].items()},
            {name: operation["checksum"] for name, operation in second["operations"].items()},
        )

    def test_spatial_hash_benchmark_cli_writes_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "spatial_hash.json"
            result = _run_module(
                "tools.spatial_hash_benchmark",
                "--entity-count",
                "16",
                "--query-count",
                "4",
                "--ray-count",
                "3",
                "--cell-size",
                "16",
                "--columns",
                "4",
                "--warmup",
                "0",
                "--repeats",
                "1",
                "--out",
                output_path.as_posix(),
                cwd=ROOT,
            )
            self.assertIn('"benchmark_version"', result.stdout)
            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(report["benchmark_version"], SPATIAL_HASH_BENCHMARK_VERSION)
        self.assertEqual(report["parameters"]["entity_count"], 16)
        self.assertEqual(report["parameters"]["query_count"], 4)
        self.assertEqual(report["parameters"]["ray_count"], 3)
        self.assertEqual(set(report["operations"]), {"insert", "query", "query_into", "ray_candidates"})


if __name__ == "__main__":
    unittest.main()
