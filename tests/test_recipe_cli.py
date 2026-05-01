from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.recipes import RecipeValidationError, run_recipe

ROOT = Path(__file__).resolve().parents[1]


def _run_motor(*args: str, project: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "motor", *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )


def _payload(stdout: str) -> dict:
    return json.loads(stdout[stdout.index("{"):])


def _create_project(workspace: Path, name: str = "RecipeProject") -> Path:
    project = workspace / name
    project.mkdir()
    (project / "project.json").write_text(
        json.dumps(
            {
                "name": name,
                "version": 2,
                "engine_version": "2026.03",
                "template": "empty",
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "prefabs": "prefabs",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }
        ),
        encoding="utf-8",
    )
    for dirname in ["assets", "levels", "prefabs", "scripts", "settings", ".motor"]:
        (project / dirname).mkdir(parents=True, exist_ok=True)
    return project


class RecipeCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self.project = _create_project(self.workspace)
        self.outside = self.workspace / "outside"
        self.outside.mkdir()
        (self.outside / "sentinel.txt").write_text("unchanged", encoding="utf-8")
        self.env = os.environ.copy()
        python_path = self.env.get("PYTHONPATH", "")
        self.env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_recipe_list_shows_platformer_recipes(self) -> None:
        result = _run_motor(
            "recipe",
            "list",
            "--project",
            self.project.as_posix(),
            "--json",
            project=self.project,
            env=self.env,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = _payload(result.stdout)
        self.assertTrue(payload["success"], payload)
        ids = {recipe["id"] for recipe in payload["data"]["recipes"]}
        self.assertIn("platformer-basic", ids)
        self.assertIn("platformer-advanced", ids)

    def test_recipe_show_returns_steps_and_is_read_only(self) -> None:
        before = {
            path.relative_to(self.project).as_posix(): path.read_text(encoding="utf-8")
            for path in self.project.rglob("*")
            if path.is_file()
        }

        result = _run_motor(
            "recipe",
            "show",
            "platformer-basic",
            "--project",
            self.project.as_posix(),
            "--json",
            project=self.project,
            env=self.env,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = _payload(result.stdout)
        self.assertTrue(payload["success"], payload)
        recipe = payload["data"]["recipe"]
        self.assertEqual(recipe["id"], "platformer-basic")
        self.assertEqual(recipe["version"], "1.0.0")
        self.assertTrue(recipe["steps"])
        self.assertTrue(recipe["expected_capabilities"])
        self.assertTrue(recipe["validation_commands"])
        after = {
            path.relative_to(self.project).as_posix(): path.read_text(encoding="utf-8")
            for path in self.project.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_recipe_show_platformer_advanced_returns_steps(self) -> None:
        result = _run_motor(
            "recipe",
            "show",
            "platformer-advanced",
            "--project",
            self.project.as_posix(),
            "--json",
            project=self.project,
            env=self.env,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = _payload(result.stdout)
        self.assertTrue(payload["success"], payload)
        recipe = payload["data"]["recipe"]
        self.assertEqual(recipe["id"], "platformer-advanced")
        self.assertTrue(recipe["steps"])
        self.assertEqual(recipe["steps"][0]["command"], ["game", "platformer", "create", "Advanced Platformer"])
        self.assertTrue(recipe["validation_commands"])

    def test_recipe_run_platformer_basic_creates_valid_scene_and_keeps_outside_files(self) -> None:
        result = _run_motor(
            "recipe",
            "run",
            "platformer-basic",
            "--project",
            self.project.as_posix(),
            "--json",
            project=self.project,
            env=self.env,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = _payload(result.stdout)
        self.assertTrue(payload["success"], payload)
        data = payload["data"]
        self.assertEqual(data["recipe"], "platformer-basic")
        self.assertEqual(data["version"], "1.0.0")
        self.assertIsNone(data["first_failure"], data)
        self.assertEqual(len(data["steps"]), 8)
        self.assertTrue(all(step["success"] for step in data["steps"]))

        scene_path = self.project / "levels" / "level_1.json"
        self.assertTrue(scene_path.exists())
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        names = {entity["name"] for entity in scene["entities"]}
        self.assertIn("Player", names)
        self.assertIn("Coin_001", names)
        self.assertIn("Hazard_001", names)
        self.assertIn("Respawn_default", names)

        validate = _run_motor(
            "game",
            "platformer",
            "validate",
            "--project",
            self.project.as_posix(),
            "--json",
            project=self.project,
            env=self.env,
        )
        self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
        self.assertTrue(_payload(validate.stdout)["success"])

        compliance = _run_motor(
            "ai",
            "compliance",
            "--strict",
            "--project",
            self.project.as_posix(),
            "--json",
            project=self.project,
            env=self.env,
        )
        self.assertEqual(compliance.returncode, 0, compliance.stdout + compliance.stderr)
        compliance_payload = _payload(compliance.stdout)
        self.assertTrue(compliance_payload["success"], compliance_payload)
        self.assertTrue(compliance_payload["data"]["strict_pass"], compliance_payload)

        self.assertEqual((self.outside / "sentinel.txt").read_text(encoding="utf-8"), "unchanged")
        self.assertEqual(sorted(path.name for path in self.outside.iterdir()), ["sentinel.txt"])

    def test_recipe_run_platformer_basic_mutates_project_state_files(self) -> None:
        result = _run_motor(
            "recipe",
            "run",
            "platformer-basic",
            "--project",
            self.project.as_posix(),
            "--json",
            project=self.project,
            env=self.env,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = _payload(result.stdout)
        self.assertTrue(payload["success"], payload)

        self.assertTrue((self.project / "levels" / "level_1.json").exists())
        self.assertTrue((self.project / ".motor" / "editor_state.json").exists())
        self.assertTrue((self.project / "settings" / "project_settings.json").exists())

        editor_state = json.loads((self.project / ".motor" / "editor_state.json").read_text(encoding="utf-8"))
        project_settings = json.loads((self.project / "settings" / "project_settings.json").read_text(encoding="utf-8"))

        self.assertEqual(editor_state.get("active_scene"), "levels/level_1.json")
        self.assertEqual(project_settings.get("startup_scene"), "levels/level_1.json")

    def test_recipe_run_platformer_advanced_creates_native_vertical_slice(self) -> None:
        result = _run_motor(
            "recipe",
            "run",
            "platformer-advanced",
            "--project",
            self.project.as_posix(),
            "--json",
            project=self.project,
            env=self.env,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = _payload(result.stdout)
        self.assertTrue(payload["success"], payload)
        data = payload["data"]
        self.assertEqual(data["recipe"], "platformer-advanced")
        self.assertEqual(data["recipe_id"], "platformer-advanced")
        self.assertIsNone(data["first_failure"], data)
        self.assertEqual(len(data["steps"]), 17)
        self.assertEqual(len(data["commands_executed"]), 17)
        self.assertTrue(data["generated_scene"])
        self.assertTrue(data["validations"])
        self.assertIn("warnings", data)
        self.assertIn("events", data)
        self.assertTrue(all(step["success"] for step in data["steps"]))

        scene_path = self.project / "levels" / "advanced_platformer.json"
        self.assertTrue(scene_path.exists())
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        by_name = {entity["name"]: entity for entity in scene["entities"]}
        self.assertIn("MovingPlatform2D", by_name["Lift_A"]["components"])
        self.assertIn("EnemyPatrol2D", by_name["Slime_A"]["components"])
        self.assertIn("Checkpoint2D", by_name["Checkpoint_A"]["components"])
        self.assertIn("KillZone2D", by_name["Pit_A"]["components"])
        self.assertIn("LevelBounds2D", by_name["LevelBounds"]["components"])

        validate = _run_motor(
            "game",
            "platformer",
            "validate",
            "--project",
            self.project.as_posix(),
            "--json",
            project=self.project,
            env=self.env,
        )
        self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
        self.assertTrue(_payload(validate.stdout)["success"])

        compliance = _run_motor(
            "ai",
            "compliance",
            "--strict",
            "--project",
            self.project.as_posix(),
            "--json",
            project=self.project,
            env=self.env,
        )
        self.assertEqual(compliance.returncode, 0, compliance.stdout + compliance.stderr)
        compliance_payload = _payload(compliance.stdout)
        self.assertTrue(compliance_payload["success"], compliance_payload)
        self.assertTrue(compliance_payload["data"]["strict_pass"], compliance_payload)

        self.assertFalse((self.project / "run_game.py").exists())
        self.assertFalse(any(path.name == "run_game.py" for path in self.workspace.rglob("*")))
        self.assertEqual((self.outside / "sentinel.txt").read_text(encoding="utf-8"), "unchanged")
        self.assertEqual(sorted(path.name for path in self.outside.iterdir()), ["sentinel.txt"])

        for path in self.workspace.rglob("*"):
            if not path.is_file():
                continue
            try:
                path.relative_to(self.project)
                continue
            except ValueError:
                pass
            self.assertEqual(path, self.outside / "sentinel.txt")

    def test_recipe_run_rejects_non_allowlisted_action(self) -> None:
        fake_recipe = {
            "id": "bad",
            "version": "1.0.0",
            "description": "Bad recipe",
            "expected_capabilities": ["scene:create"],
            "steps": [
                {
                    "id": "bad-step",
                    "description": "Attempt a non-allowlisted command.",
                    "command": ["scene", "create", "Bad"],
                }
            ],
            "validation_commands": [["scene", "list"]],
        }

        with patch("engine.recipes.runner.get_recipe", return_value=fake_recipe):
            with self.assertRaises(RecipeValidationError):
                run_recipe("bad", self.project)


if __name__ == "__main__":
    unittest.main()
