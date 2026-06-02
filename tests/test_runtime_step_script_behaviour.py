"""
tests/test_runtime_step_script_behaviour.py - ScriptBehaviour como input-capable player

Verifica que un entity con InputMap + ScriptBehaviour (sin PlayerController2D)
es detectado como input-capable por motor runtime step.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_motor(*args: str, project: Path) -> tuple[int, str, str]:
    cmd = [sys.executable, "-m", "motor"] + list(args)
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project))
    return result.returncode, result.stdout, result.stderr


def _payload(stdout: str) -> dict:
    return json.loads(stdout[stdout.index("{"):])


class RuntimeStepScriptBehaviourTests(unittest.TestCase):
    """motor runtime step reconoce entidades InputMap + ScriptBehaviour."""

    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.project = Path(self._temp_dir.name) / "ScriptBehaviourCLI"
        self.project.mkdir()
        self._write_project_manifest()
        for dirname in ("assets", "levels", "prefabs", "scripts", "settings", ".motor"):
            (self.project / dirname).mkdir(parents=True, exist_ok=True)
        self._write_minimal_script()
        self._write_scene()

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_project_manifest(self) -> None:
        (self.project / "project.json").write_text(
            json.dumps({
                "name": "ScriptBehaviourCLI",
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
            }, indent=2),
            encoding="utf-8",
        )

    def _write_minimal_script(self) -> None:
        (self.project / "scripts" / "dummy_player.py").write_text(
            'def on_play(context) -> None:\n    pass\n\ndef on_update(context, dt: float) -> None:\n    pass\n\ndef on_stop(context) -> None:\n    pass\n',
            encoding="utf-8",
        )

    def _write_scene(self) -> None:
        scene_path = self.project / "levels" / "main_scene.json"
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_path.write_text(
            json.dumps({
                "name": "ScriptBehaviour Scene",
                "schema_version": 2,
                "entities": [
                    {
                        "id": "entity_script_player",
                        "name": "Player",
                        "active": True,
                        "tag": "Player",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 0.0,
                                "y": 0.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                            "RigidBody": {
                                "enabled": True,
                                "body_type": "dynamic",
                                "gravity_scale": 1.0,
                                "velocity_x": 0.0,
                                "velocity_y": 0.0,
                                "is_grounded": True,
                            },
                            "InputMap": {
                                "enabled": True,
                                "move_left": "A,LEFT",
                                "move_right": "D,RIGHT",
                                "move_up": "W,UP",
                                "move_down": "S,DOWN",
                                "action_1": "SPACE",
                                "action_2": "ENTER",
                            },
                            "ScriptBehaviour": {
                                "enabled": True,
                                "module_path": "dummy_player",
                                "script": {"path": "scripts/dummy_player.py", "guid": ""},
                                "run_in_edit_mode": False,
                                "public_data": {},
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }, indent=2),
            encoding="utf-8",
        )

    def test_runtime_step_finds_scriptbehaviour_player(self) -> None:
        returncode, stdout, stderr = _run_motor(
            "runtime", "step",
            "--project", self.project.as_posix(),
            "--frames", "1",
            "--input", "right",
            "--json",
            project=self.project,
        )
        self.assertEqual(returncode, 0, stderr + stdout)
        data = _payload(stdout)
        self.assertTrue(data["success"], data)
        response_data = data["data"]
        self.assertEqual(response_data["frames_simulated"], 1)
        self.assertEqual(response_data["input_sequence"], ["right"])
        self.assertIsNotNone(response_data["player_before"])
        self.assertEqual(response_data["player_before"]["name"], "Player")
        self.assertIn("ScriptBehaviour", response_data["player_before"])
        self.assertIsNotNone(response_data["player_after"])
        self.assertEqual(response_data["player_after"]["name"], "Player")

    def test_runtime_step_finds_player_by_iteration(self) -> None:
        """Entity con InputMap + ScriptBehaviour encontrado por iteracion (non-'Player' name)."""
        scene_path = self.project / "levels" / "main_scene.json"
        scene_path.write_text(
            json.dumps({
                "name": "Iter Scene",
                "schema_version": 2,
                "entities": [
                    {
                        "id": "entity_script_bot",
                        "name": "ScriptBot",
                        "active": True,
                        "tag": "Bot",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 10.0,
                                "y": 0.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                            "InputMap": {
                                "enabled": True,
                            },
                            "ScriptBehaviour": {
                                "enabled": True,
                                "module_path": "dummy_player",
                                "script": {"path": "scripts/dummy_player.py", "guid": ""},
                                "run_in_edit_mode": False,
                                "public_data": {},
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }, indent=2),
            encoding="utf-8",
        )

        returncode, stdout, stderr = _run_motor(
            "runtime", "step",
            "--project", self.project.as_posix(),
            "--frames", "1",
            "--input", "right",
            "--json",
            project=self.project,
        )
        self.assertEqual(returncode, 0, stderr + stdout)
        data = _payload(stdout)
        self.assertTrue(data["success"], data)
        response_data = data["data"]
        self.assertEqual(response_data["frames_simulated"], 1)
        self.assertIsNotNone(response_data["player_before"])
        self.assertEqual(response_data["player_before"]["name"], "ScriptBot")

    def test_runtime_step_preserves_playercontroller2d_behaviour(self) -> None:
        """PlayerController2D path sigue funcionando sin cambios."""
        scene_path = self.project / "levels" / "main_scene.json"
        scene_path.write_text(
            json.dumps({
                "name": "PC2D Scene",
                "schema_version": 2,
                "entities": [
                    {
                        "id": "entity_pc2d_player",
                        "name": "Player",
                        "active": True,
                        "tag": "Player",
                        "layer": "Gameplay",
                        "components": {
                            "Transform": {
                                "enabled": True,
                                "x": 0.0,
                                "y": 0.0,
                                "rotation": 0.0,
                                "scale_x": 1.0,
                                "scale_y": 1.0,
                            },
                            "RigidBody": {
                                "enabled": True,
                                "body_type": "dynamic",
                                "gravity_scale": 1.0,
                                "velocity_x": 0.0,
                                "velocity_y": 0.0,
                                "is_grounded": True,
                            },
                            "InputMap": {
                                "enabled": True,
                            },
                            "PlayerController2D": {
                                "enabled": True,
                                "speed": 200.0,
                                "jump_force": -400.0,
                            },
                        },
                    }
                ],
                "rules": [],
                "feature_metadata": {},
            }, indent=2),
            encoding="utf-8",
        )

        returncode, stdout, stderr = _run_motor(
            "runtime", "step",
            "--project", self.project.as_posix(),
            "--frames", "1",
            "--input", "right",
            "--json",
            project=self.project,
        )
        self.assertEqual(returncode, 0, stderr + stdout)
        data = _payload(stdout)
        self.assertTrue(data["success"], data)
        response_data = data["data"]
        self.assertEqual(response_data["frames_simulated"], 1)
        self.assertIsNotNone(response_data["player_before"])
        self.assertEqual(response_data["player_before"]["name"], "Player")
        self.assertIn("PlayerController2D", response_data["player_before"])
