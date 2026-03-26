import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())


class EngineCliTests(unittest.TestCase):
    def test_validate_scene_subcommand(self) -> None:
        exit_code = os.system("py -3 tools/engine_cli.py validate --target scene --path levels/demo_level.json")
        self.assertEqual(exit_code, 0)

    def test_smoke_subcommand_produces_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "smoke"
            exit_code = os.system(
                f'py -3 tools/engine_cli.py smoke --scene levels/demo_level.json --frames 2 --seed 7 --out-dir "{out_dir.as_posix()}"'
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue((out_dir / "smoke_migrated_scene.json").exists())
            self.assertTrue((out_dir / "smoke_debug_dump.json").exists())
            self.assertTrue((out_dir / "smoke_profile.json").exists())

            profile_report = json.loads((out_dir / "smoke_profile.json").read_text(encoding="utf-8"))
            debug_dump = json.loads((out_dir / "smoke_debug_dump.json").read_text(encoding="utf-8"))

        self.assertEqual(profile_report["frames"], 2)
        self.assertEqual(debug_dump["pass"], "Debug")


if __name__ == "__main__":
    unittest.main()
