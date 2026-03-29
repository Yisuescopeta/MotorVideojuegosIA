import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_module(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-m", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Subprocess failed: {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


class EngineCliTests(unittest.TestCase):
    def test_validate_scene_subcommand(self) -> None:
        result = _run_module("tools.engine_cli", "validate", "--target", "scene", "--path", "levels/demo_level.json")
        self.assertIn("[OK]", result.stdout)

    def test_smoke_subcommand_produces_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "smoke"
            result = _run_module(
                "tools.engine_cli",
                "smoke",
                "--scene",
                "levels/demo_level.json",
                "--frames",
                "2",
                "--seed",
                "7",
                "--out-dir",
                out_dir.as_posix(),
            )
            self.assertIn("[OK]", result.stdout)
            self.assertTrue((out_dir / "smoke_migrated_scene.json").exists())
            self.assertTrue((out_dir / "smoke_debug_dump.json").exists())
            self.assertTrue((out_dir / "smoke_profile.json").exists())

            profile_report = json.loads((out_dir / "smoke_profile.json").read_text(encoding="utf-8"))
            debug_dump = json.loads((out_dir / "smoke_debug_dump.json").read_text(encoding="utf-8"))

        self.assertEqual(profile_report["frames"], 2)
        self.assertEqual(debug_dump["pass"], "Debug")


if __name__ == "__main__":
    unittest.main()
