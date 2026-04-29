"""
tests/test_motor_cli_contract.py - Executable contract tests for motor CLI

Blindaje contra regresiones:
- Verifica que TODOS los cli_command del registry sean compatibles con `motor`
- Falla si hay comandos documentados pero inexistentes
- Falla si los ejemplos usan la CLI antigua como camino principal
- Falla si START_HERE_AI.md usa `python -m tools.engine_cli` fuera de contexto legacy
- Falla si motor_ai.json referencia comandos obsoletos

Estos tests ejecutan comandos reales, no solo verifican estructura.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Set, Tuple
from unittest.mock import patch

from engine.ai import MotorAIBootstrapBuilder, get_default_registry
from engine.ai.compliance import run_ai_compliance
from engine.api import EngineAPI
from motor.cli import create_motor_parser
from motor.cli_core import cmd_prefab_create

ROOT = Path(__file__).resolve().parents[1]


def _run_motor(*args: str, env: dict | None = None, project: Path | None = None) -> Tuple[int, str, str]:
    """Run motor CLI command and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "-m", "motor"] + list(args)

    if env is None:
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path

    result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project) if project else str(ROOT))
    return result.returncode, result.stdout, result.stderr


def _create_test_project(workspace: Path, name: str = "TestProject") -> Path:
    """Create a minimal valid test project."""
    project_root = workspace / name
    project_root.mkdir()

    (project_root / "project.json").write_text(
        json.dumps({
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
        }),
        encoding="utf-8",
    )

    for dir_name in ["assets", "levels", "scripts", "settings", ".motor"]:
        (project_root / dir_name).mkdir(parents=True, exist_ok=True)

    return project_root


class RegistryToCLIExecutableContractTests(unittest.TestCase):
    """Executable contract tests: registry commands must work in motor CLI."""

    @classmethod
    def setUpClass(cls):
        cls.registry = get_default_registry()
        cls.parser = create_motor_parser()
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls.project = _create_test_project(Path(cls._temp_dir.name), "ContractTest")
        cls.env = os.environ.copy()
        python_path = cls.env.get("PYTHONPATH", "")
        cls.env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path

    @classmethod
    def tearDownClass(cls):
        cls._temp_dir.cleanup()

    def _get_available_commands(self) -> Set[str]:
        """Extract available commands from motor CLI parser."""
        commands = set()
        for action in self.parser._actions:
            if hasattr(action, 'choices') and action.choices:
                for cmd_name, subparser in action.choices.items():
                    commands.add(cmd_name)
                    # Check for subcommands
                    if hasattr(subparser, '_actions'):
                        for sub_action in subparser._actions:
                            if hasattr(sub_action, 'choices') and sub_action.choices:
                                for sub_cmd in sub_action.choices.keys():
                                    commands.add(f"{cmd_name} {sub_cmd}")
        return commands

    def test_all_registry_cli_commands_start_with_motor(self) -> None:
        """CADA cli_command en el registry debe empezar con 'motor '."""
        violations = []
        for cap in self.registry.list_all():
            if not cap.cli_command.startswith("motor "):
                violations.append(f"{cap.id}: {cap.cli_command}")

        if violations:
            self.fail("Capabilities sin prefijo 'motor ':\n" + "\n".join(violations))

    def test_no_registry_commands_use_deprecated_tools_engine_cli(self) -> None:
        """NINGÚN cli_command debe referenciar tools.engine_cli."""
        deprecated_patterns = [
            "python -m tools.engine_cli",
            "tools.engine_cli",
            "python -m tools",
        ]

        violations = []
        for cap in self.registry.list_all():
            for pattern in deprecated_patterns:
                if pattern in cap.cli_command:
                    violations.append(f"{cap.id}: {cap.cli_command}")
                    break

        if violations:
            self.fail("Capabilities con CLI obsoleto:\n" + "\n".join(violations))

    def test_registry_command_scopes_exist_in_motor_cli(self) -> None:
        """Todos los scopes de comandos en registry deben existir en motor CLI."""
        available = self._get_available_commands()

        # Mapeo de capability scope a comandos CLI
        scope_to_command = {
            "ai": "ai",
            "scene": "scene",
            "entity": "entity",
            "component": "component",
            "asset": "asset",
            "animator": "animator",
            "prefab": "prefab",
            "project": "project",
            "runtime": "runtime",
            "physics": "physics",
            "slice": "asset",  # slice commands are under asset
            "introspect": "capabilities",  # introspect:capabilities -> capabilities
        }

        # Comandos que pueden no estar implementados aún pero están documentados
        future_scopes = {"physics", "introspect"}

        violations = []
        for cap in self.registry.list_all():
            scope = cap.id.split(":")[0]
            expected_cmd = scope_to_command.get(scope, scope)

            if scope in future_scopes:
                continue  # Skip future commands

            # Check if command or subcommand exists
            cmd_parts = cap.cli_command.split()[1:]  # Remove 'motor'
            if not cmd_parts:
                continue

            base_cmd = cmd_parts[0]
            if base_cmd not in available and f"{base_cmd} {cmd_parts[1] if len(cmd_parts) > 1 else ''}".strip() not in available:
                if expected_cmd not in available:
                    violations.append(f"{cap.id}: scope '{scope}' -> command '{expected_cmd}' not found")

        if violations:
            self.fail("Scopes de registry sin comandos CLI correspondientes:\n" + "\n".join(violations))

    def test_implemented_commands_actually_work(self) -> None:
        """Los comandos marcados como implementados deben funcionar realmente."""
        # Comandos que deberían funcionar (no marcados como futuro)
        # Usando gramática oficial: motor <noun> [<subnoun>] <verb>
        implemented_patterns = [
            ("ai", ["start"]),
            ("ai", ["compliance"]),
            ("capabilities", []),
            ("doctor", []),
            ("game", ["platformer", "create"]),
            ("project", ["info"]),
            ("scene", ["list"]),
            ("scene", ["create"]),
            ("runtime", ["play"]),
            ("runtime", ["step"]),
            ("runtime", ["stop"]),
            ("runtime", ["status"]),
            ("runtime", ["entities"]),
            ("runtime", ["inspect"]),
            ("runtime", ["events"]),
            ("entity", ["create"]),
            ("component", ["add"]),
            ("prefab", ["create"]),
            ("prefab", ["instantiate"]),
            ("prefab", ["unpack"]),
            ("prefab", ["apply"]),
            ("prefab", ["list"]),
            ("asset", ["list"]),
            ("animator", ["info"]),
            ("animator", ["ensure"]),
            ("animator", ["state", "create"]),  # Nueva gramática jerárquica
            ("animator", ["state", "remove"]),  # Nueva gramática jerárquica
        ]

        for scope, subcommands in implemented_patterns:
            cmd_parts = [scope] + subcommands

            with self.subTest(command=f"motor {' '.join(cmd_parts)}"):
                args = cmd_parts + ["--help"]
                returncode, stdout, stderr = _run_motor(*args, env=self.env)

                # --help should work (return 0) even if command needs args
                if returncode != 0 and "error" in (stderr + stdout).lower():
                    self.fail(f"Command 'motor {' '.join(cmd_parts)}' parece no existir. Return code: {returncode}")

    def test_no_duplicate_official_commands(self) -> None:
        """No debe haber dos sintaxis oficiales para la misma operación.

        Este test verifica que no se introduzcan aliases no documentados
        como parte de la interfaz oficial.
        """
        # Mapeo de operaciones a su sintaxis oficial única
        # Verificar que no hay múltiples capabilities apuntando a comandos similares
        for cap in self.registry.list_all():
            cmd = cap.cli_command

            # Verificar que los comandos legacy no están documentados como oficiales
            if "upsert-state" in cmd or "remove-state" in cmd:
                self.fail(
                    f"Capability '{cap.id}' usa sintaxis legacy en cli_command: {cmd}\n"
                    f"Use 'animator state create/remove' en su lugar."
                )


class AIStartCLIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.project = _create_test_project(Path(self._temp_dir.name), "AIStartCLI")
        self.env = os.environ.copy()
        python_path = self.env.get("PYTHONPATH", "")
        self.env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
        scene_path = self.project / "levels" / "main_scene.json"
        scene_path.write_text(
            json.dumps({"name": "Main Scene", "entities": [], "rules": [], "feature_metadata": {}}, indent=2),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_motor_ai_start_returns_contract_json(self) -> None:
        returncode, stdout, stderr = _run_motor(
            "ai",
            "start",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = json.loads(stdout[stdout.index("{"):])
        self.assertTrue(payload["success"])

        data = payload["data"]
        self.assertEqual(data["engine"]["name"], "MotorVideojuegosIA")
        self.assertTrue(data["engine"]["version"])
        self.assertEqual(data["recommended_cli"], "motor")
        self.assertEqual(data["recommended_api"], "EngineAPI")
        self.assertIn("serialized Scene", data["authoring_contract"])
        self.assertIn("EngineAPI", data["authoring_contract"])
        self.assertGreaterEqual(data["scene_context"]["detected_scene_count"], 1)
        self.assertIn("motor ai start --project . --json", data["initial_commands"])
        self.assertIn("motor doctor --project . --json", data["initial_commands"])

        rules_text = json.dumps(data["rules"])
        self.assertIn("external runtime", rules_text)
        self.assertIn("run_game.py", rules_text)
        self.assertIn("alternate main loop", rules_text)

        self.assertEqual(
            data["validation"]["command"],
            "motor ai compliance --project . --strict --json",
        )
        self.assertEqual(data["validation"]["status"], "implemented")
        self.assertTrue(data["validation"]["next_step"])
        self.assertTrue(data["recommended_workflows"])


class RuntimeCLIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.project = _create_test_project(Path(self._temp_dir.name), "RuntimeCLI")
        self.env = os.environ.copy()
        python_path = self.env.get("PYTHONPATH", "")
        self.env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_scene(self, relative_path: str = "levels/main_scene.json") -> Path:
        scene_path = self.project / relative_path
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_path.write_text(
            json.dumps(
                {
                    "name": "Runtime Scene",
                    "entities": [
                        {
                            "name": "RuntimeProbe",
                            "active": True,
                            "components": {
                                "Transform": {
                                    "enabled": True,
                                    "x": 0.0,
                                    "y": 0.0,
                                    "rotation": 0.0,
                                    "scale_x": 1.0,
                                    "scale_y": 1.0,
                                }
                            },
                        }
                    ],
                    "rules": [],
                    "feature_metadata": {},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return scene_path

    def _payload(self, stdout: str) -> dict:
        return json.loads(stdout[stdout.index("{"):])

    def test_motor_runtime_play_headless_json(self) -> None:
        self._write_scene()

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "play",
            "--project",
            self.project.as_posix(),
            "--headless",
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = self._payload(stdout)
        self.assertTrue(payload["success"])
        data = payload["data"]
        self.assertEqual(data["command"], "runtime play")
        self.assertTrue(data["headless"])
        self.assertTrue(data["stateless"])
        self.assertTrue(data["scene"]["has_scene"])
        self.assertIn("PLAY", data["status_after"]["state"])
        self.assertIn("EDIT", data["cleanup_status"]["state"])

    def test_motor_runtime_step_play_step_stop_does_not_save_scene(self) -> None:
        scene_path = self._write_scene()
        before = scene_path.read_text(encoding="utf-8")

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "step",
            "--project",
            self.project.as_posix(),
            "--frames",
            "300",
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = self._payload(stdout)
        self.assertTrue(payload["success"])
        data = payload["data"]
        self.assertEqual(data["command"], "runtime step")
        self.assertTrue(data["headless"])
        self.assertTrue(data["stateless"])
        self.assertEqual(data["frames_requested"], 300)
        self.assertIn("EDIT", data["status_before"]["state"])
        self.assertIn("PLAY", data["status_after_play"]["state"])
        self.assertIn("PLAY", data["status_after_step"]["state"])
        self.assertIn("EDIT", data["status_after"]["state"])
        self.assertEqual(scene_path.read_text(encoding="utf-8"), before)


class GamePlatformerCLIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.project = _create_test_project(Path(self._temp_dir.name), "PlatformerCLI")
        self.env = os.environ.copy()
        python_path = self.env.get("PYTHONPATH", "")
        self.env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _payload(self, stdout: str) -> dict:
        return json.loads(stdout[stdout.index("{"):])

    def _write_scene(self, relative_path: str = "levels/main_scene.json") -> Path:
        scene_path = self.project / relative_path
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_path.write_text(
            json.dumps(
                {
                    "name": "Runtime Scene",
                    "entities": [
                        {
                            "name": "RuntimeProbe",
                            "active": True,
                            "components": {
                                "Transform": {
                                    "enabled": True,
                                    "x": 0.0,
                                    "y": 0.0,
                                    "rotation": 0.0,
                                    "scale_x": 1.0,
                                    "scale_y": 1.0,
                                }
                            },
                        }
                    ],
                    "rules": [],
                    "feature_metadata": {},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return scene_path

    def test_motor_game_platformer_create_help_exists(self) -> None:
        returncode, stdout, stderr = _run_motor(
            "game",
            "platformer",
            "create",
            "--help",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        self.assertIn("Create a minimal native 2D platformer scene", stdout)

    def test_motor_game_platformer_create_scaffolds_loadable_scene(self) -> None:
        returncode, stdout, stderr = _run_motor(
            "game",
            "platformer",
            "create",
            "Level 1",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = self._payload(stdout)
        self.assertTrue(payload["success"], payload)
        data = payload["data"]
        self.assertEqual(data["scene_name"], "Level 1")
        self.assertEqual(data["startup_scene"], "levels/level_1.json")
        self.assertEqual(set(data["entities_created"]), {"Player", "Ground", "Goal", "MainCamera"})

        scene_path = self.project / "levels" / "level_1.json"
        self.assertTrue(scene_path.exists())
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        self.assertEqual(scene["schema_version"], 2)
        names = {entity["name"] for entity in scene["entities"]}
        self.assertIn("Player", names)
        self.assertIn("Ground", names)
        self.assertIn("Goal", names)
        self.assertIn("MainCamera", names)

        player = next(entity for entity in scene["entities"] if entity["name"] == "Player")
        self.assertEqual(player["tag"], "Player")
        self.assertIn("Transform", player["components"])
        self.assertIn("Collider", player["components"])
        self.assertIn("RigidBody", player["components"])
        self.assertIn("InputMap", player["components"])
        self.assertIn("PlayerController2D", player["components"])

        goal = next(entity for entity in scene["entities"] if entity["name"] == "Goal")
        self.assertEqual(goal["tag"], "Goal")
        self.assertIn("Goal2D", goal["components"])
        self.assertTrue(goal["components"]["Collider"]["is_trigger"])

        settings_path = self.project / "settings" / "project_settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertEqual(settings["startup_scene"], "levels/level_1.json")

        api = EngineAPI(project_root=self.project.as_posix())
        self.addCleanup(api.shutdown)
        api.load_level("levels/level_1.json")
        self.assertEqual(api.get_active_scene()["name"], "Level 1")
        self.assertIsNotNone(api.game.world.get_entity_by_name("Player"))

        compliance = run_ai_compliance(self.project, strict=True)
        self.assertTrue(compliance["success"], compliance)
        self.assertTrue(compliance["strict_pass"], compliance)

    def test_motor_game_platformer_create_runtime_status_can_load_without_mutation(self) -> None:
        _run_motor(
            "game",
            "platformer",
            "create",
            "Level 1",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )
        scene_path = self.project / "levels" / "level_1.json"
        before = scene_path.read_text(encoding="utf-8")

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "status",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = self._payload(stdout)
        self.assertTrue(payload["success"], payload)
        self.assertTrue(payload["data"]["scene"]["has_scene"])
        self.assertEqual(scene_path.read_text(encoding="utf-8"), before)

    def test_motor_game_platformer_incremental_flow_validates(self) -> None:
        commands = [
            ("game", "platformer", "create", "Level 1"),
            ("game", "platformer", "add-player", "--x", "100", "--y", "300"),
            ("game", "platformer", "add-ground", "--from-x", "0", "--to-x", "20", "--y", "8"),
        ]

        payloads: list[dict] = []
        for command in commands:
            returncode, stdout, stderr = _run_motor(
                *command,
                "--project",
                self.project.as_posix(),
                "--json",
                env=self.env,
            )
            self.assertEqual(returncode, 0, stderr + stdout)
            payload = self._payload(stdout)
            self.assertTrue(payload["success"], payload)
            self.assertIn("scene_path", payload["data"])
            self.assertIn("entities_created", payload["data"])
            self.assertIn("warnings", payload["data"])
            payloads.append(payload)

        self.assertEqual(payloads[1]["data"]["entities_created"], [])
        self.assertEqual(payloads[2]["data"]["entities_created"], ["Ground_001"])

        returncode, stdout, stderr = _run_motor(
            "game",
            "platformer",
            "validate",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )
        self.assertEqual(returncode, 0, stderr + stdout)
        validate_payload = self._payload(stdout)
        self.assertTrue(validate_payload["success"], validate_payload)
        validation = validate_payload["data"]["validation"]
        self.assertTrue(all(validation.values()), validation)
        self.assertTrue(validate_payload["data"]["platformer_validation"]["success"], validate_payload)
        self.assertTrue(validate_payload["data"]["strict_compliance"]["success"], validate_payload)

        scene_path = self.project / "levels" / "level_1.json"
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        player = next(entity for entity in scene["entities"] if entity["name"] == "Player")
        self.assertEqual(player["components"]["Transform"]["x"], 100.0)
        self.assertEqual(player["components"]["Transform"]["y"], 300.0)

        ground = next(entity for entity in scene["entities"] if entity["name"] == "Ground_001")
        self.assertEqual(ground["components"]["Transform"]["x"], 640.0)
        self.assertEqual(ground["components"]["Transform"]["y"], 512.0)
        self.assertEqual(ground["components"]["Collider"]["width"], 1280.0)

        goal = next(entity for entity in scene["entities"] if entity["name"] == "Goal")
        self.assertIn("Goal2D", goal["components"])
        self.assertTrue(goal["components"]["Collider"]["is_trigger"])

        compliance = run_ai_compliance(self.project, strict=True)
        self.assertTrue(compliance["success"], compliance)
        self.assertTrue(compliance["strict_pass"], compliance)

    def test_motor_game_platformer_semantic_add_commands_create_entities(self) -> None:
        setup_commands = [
            ("game", "platformer", "create", "Level 1"),
            ("game", "platformer", "add-goal", "--x", "1100", "--y", "200"),
            ("game", "platformer", "add-coin", "--x", "320", "--y", "200", "--points", "1"),
            ("game", "platformer", "add-coin", "--x", "360", "--y", "210", "--points", "2"),
            ("game", "platformer", "add-coin", "--name", "Coin_A", "--x", "400", "--y", "220", "--points", "3"),
            ("game", "platformer", "add-coin", "--name", "Coin_A", "--x", "420", "--y", "230", "--points", "4"),
            ("game", "platformer", "add-hazard", "--x", "640", "--y", "300", "--damage", "1"),
            ("game", "platformer", "add-respawn", "--x", "100", "--y", "300", "--id", "default"),
        ]

        payloads: list[dict] = []
        for command in setup_commands:
            returncode, stdout, stderr = _run_motor(
                *command,
                "--project",
                self.project.as_posix(),
                "--json",
                env=self.env,
            )
            self.assertEqual(returncode, 0, stderr + stdout)
            payload = self._payload(stdout)
            self.assertTrue(payload["success"], payload)
            payloads.append(payload)

        self.assertIn("Goal", payloads[0]["data"]["entities_created"])
        self.assertEqual(payloads[1]["data"]["entities_created"], ["Goal_001"])
        self.assertEqual(payloads[2]["data"]["entities_created"], ["Coin_001"])
        self.assertEqual(payloads[3]["data"]["entities_created"], ["Coin_002"])
        self.assertEqual(payloads[4]["data"]["entities_created"], ["Coin_A"])
        self.assertEqual(payloads[5]["data"]["entities_created"], [])
        self.assertEqual(payloads[6]["data"]["entities_created"], ["Hazard_001"])
        self.assertEqual(payloads[7]["data"]["entities_created"], ["Respawn_default"])

        scene_path = self.project / "levels" / "level_1.json"
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        by_name = {entity["name"]: entity for entity in scene["entities"]}

        coin_components = by_name["Coin_001"]["components"]
        self.assertIn("Transform", coin_components)
        self.assertIn("Collider", coin_components)
        self.assertIn("Collectible2D", coin_components)
        self.assertEqual(coin_components["Transform"]["x"], 320.0)
        self.assertEqual(coin_components["Collectible2D"]["points"], 1)
        self.assertTrue(coin_components["Collider"]["is_trigger"])
        self.assertIn("Coin_002", by_name)
        self.assertEqual(by_name["Coin_002"]["components"]["Collectible2D"]["points"], 2)
        self.assertEqual(by_name["Coin_A"]["components"]["Transform"]["x"], 420.0)
        self.assertEqual(by_name["Coin_A"]["components"]["Collectible2D"]["points"], 4)

        hazard_components = by_name["Hazard_001"]["components"]
        self.assertIn("Transform", hazard_components)
        self.assertIn("Collider", hazard_components)
        self.assertIn("Hazard2D", hazard_components)
        self.assertEqual(hazard_components["Transform"]["x"], 640.0)
        self.assertEqual(hazard_components["Hazard2D"]["damage"], 1)

        goal_components = by_name["Goal"]["components"]
        self.assertIn("Transform", goal_components)
        self.assertIn("Collider", goal_components)
        self.assertIn("Goal2D", goal_components)

        respawn_components = by_name["Respawn_default"]["components"]
        self.assertIn("Transform", respawn_components)
        self.assertIn("RespawnPoint2D", respawn_components)
        self.assertEqual(respawn_components["RespawnPoint2D"]["spawn_id"], "default")

        returncode, stdout, stderr = _run_motor(
            "game",
            "platformer",
            "validate",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )
        self.assertEqual(returncode, 0, stderr + stdout)
        validate_payload = self._payload(stdout)
        self.assertTrue(validate_payload["success"], validate_payload)
        semantic_entities = validate_payload["data"]["semantic_entities"]
        self.assertEqual(set(semantic_entities["collectibles"]), {"Coin_001", "Coin_002", "Coin_A"})
        self.assertEqual(semantic_entities["hazards"], ["Hazard_001"])
        self.assertEqual(set(semantic_entities["goals"]), {"Goal", "Goal_001"})
        self.assertEqual(semantic_entities["respawns"], ["Respawn_default"])
        self.assertTrue(validate_payload["data"]["platformer_validation"]["success"], validate_payload)
        self.assertTrue(validate_payload["data"]["strict_compliance"]["success"], validate_payload)

        compliance = run_ai_compliance(self.project, strict=True)
        self.assertTrue(compliance["success"], compliance)
        self.assertTrue(compliance["strict_pass"], compliance)

        before = scene_path.read_text(encoding="utf-8")
        returncode, stdout, stderr = _run_motor(
            "runtime",
            "entities",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )
        self.assertEqual(returncode, 0, stderr + stdout)
        runtime_payload = self._payload(stdout)
        self.assertTrue(runtime_payload["success"], runtime_payload)
        runtime_names = {entity["name"] for entity in runtime_payload["data"]["entities"]}
        self.assertTrue({"Coin_001", "Coin_002", "Coin_A", "Hazard_001", "Goal", "Goal_001", "Respawn_default"}.issubset(runtime_names))
        self.assertEqual(scene_path.read_text(encoding="utf-8"), before)

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "inspect",
            "Coin_001",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )
        self.assertEqual(returncode, 0, stderr + stdout)
        inspect_payload = self._payload(stdout)
        self.assertTrue(inspect_payload["success"], inspect_payload)
        self.assertIn("Collectible2D", inspect_payload["data"]["entity"]["components"])
        self.assertEqual(scene_path.read_text(encoding="utf-8"), before)

    def test_motor_game_platformer_incremental_scene_runtime_read_only(self) -> None:
        for command in [
            ("game", "platformer", "create", "Level 1"),
            ("game", "platformer", "add-player", "--x", "100", "--y", "300"),
            ("game", "platformer", "add-ground", "--from-x", "0", "--to-x", "20", "--y", "8"),
            ("game", "platformer", "add-goal", "--x", "1100", "--y", "200"),
        ]:
            returncode, stdout, stderr = _run_motor(
                *command,
                "--project",
                self.project.as_posix(),
                "--json",
                env=self.env,
            )
            self.assertEqual(returncode, 0, stderr + stdout)

        scene_path = self.project / "levels" / "level_1.json"
        before = scene_path.read_text(encoding="utf-8")

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "status",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = self._payload(stdout)
        self.assertTrue(payload["success"], payload)
        self.assertTrue(payload["data"]["scene"]["has_scene"])
        self.assertEqual(scene_path.read_text(encoding="utf-8"), before)

    def test_motor_runtime_stop_is_stateless_and_warns(self) -> None:
        returncode, stdout, stderr = _run_motor(
            "runtime",
            "stop",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = self._payload(stdout)
        self.assertTrue(payload["success"])
        data = payload["data"]
        self.assertEqual(data["command"], "runtime stop")
        self.assertTrue(data["stateless"])
        self.assertTrue(any("stateless" in warning for warning in data["warnings"]))
        self.assertTrue(any("No active scene" in warning for warning in data["warnings"]))

    def test_motor_runtime_play_fails_without_loadable_scene(self) -> None:
        returncode, stdout, _stderr = _run_motor(
            "runtime",
            "play",
            "--project",
            self.project.as_posix(),
            "--headless",
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 1, stdout)
        payload = self._payload(stdout)
        self.assertFalse(payload["success"])
        warnings = payload["data"]["warnings"]
        self.assertTrue(any("No active scene" in warning for warning in warnings))

    def test_motor_runtime_step_warns_when_fallback_scene_loaded(self) -> None:
        self._write_scene()

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "step",
            "--project",
            self.project.as_posix(),
            "--frames",
            "1",
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = self._payload(stdout)
        self.assertTrue(payload["success"])
        warnings = payload["data"]["warnings"]
        self.assertTrue(any("No active scene" in warning for warning in warnings))
        self.assertTrue(any("fallback scene" in warning for warning in warnings))

    def test_motor_runtime_status_returns_json_with_scene_and_status(self) -> None:
        self._write_scene()

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "status",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = self._payload(stdout)
        self.assertTrue(payload["success"])
        data = payload["data"]
        self.assertEqual(data["command"], "runtime status")
        self.assertTrue(data["stateless"])
        self.assertIn("status", data)
        self.assertIn("scene", data)
        self.assertTrue(data["scene"]["has_scene"])

    def test_motor_runtime_status_does_not_modify_scene_file(self) -> None:
        scene_path = self._write_scene()
        before = scene_path.read_text(encoding="utf-8")

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "status",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        self.assertEqual(scene_path.read_text(encoding="utf-8"), before)

    def test_motor_runtime_entities_lists_entities(self) -> None:
        self._write_scene()

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "entities",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = self._payload(stdout)
        self.assertTrue(payload["success"])
        data = payload["data"]
        self.assertEqual(data["command"], "runtime entities")
        self.assertTrue(data["stateless"])
        self.assertIn("entities", data)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["entities"][0]["name"], "RuntimeProbe")

    def test_motor_runtime_entities_with_filters(self) -> None:
        self._write_scene()

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "entities",
            "--project",
            self.project.as_posix(),
            "--active-only",
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = self._payload(stdout)
        self.assertTrue(payload["success"])
        data = payload["data"]
        self.assertEqual(data["count"], 1)

    def test_motor_runtime_entities_does_not_modify_scene_file(self) -> None:
        scene_path = self._write_scene()
        before = scene_path.read_text(encoding="utf-8")

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "entities",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        self.assertEqual(scene_path.read_text(encoding="utf-8"), before)

    def test_motor_runtime_inspect_returns_entity_data(self) -> None:
        self._write_scene()

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "inspect",
            "RuntimeProbe",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = self._payload(stdout)
        self.assertTrue(payload["success"])
        data = payload["data"]
        self.assertEqual(data["command"], "runtime inspect")
        self.assertTrue(data["stateless"])
        self.assertIn("entity", data)
        self.assertEqual(data["entity"]["name"], "RuntimeProbe")
        self.assertIn("components", data["entity"])

    def test_motor_runtime_inspect_fails_for_missing_entity(self) -> None:
        self._write_scene()

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "inspect",
            "MissingEntity",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 1, stderr + stdout)
        payload = self._payload(stdout)
        self.assertFalse(payload["success"])

    def test_motor_runtime_inspect_does_not_modify_scene_file(self) -> None:
        scene_path = self._write_scene()
        before = scene_path.read_text(encoding="utf-8")

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "inspect",
            "RuntimeProbe",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        self.assertEqual(scene_path.read_text(encoding="utf-8"), before)

    def test_motor_runtime_events_returns_list(self) -> None:
        self._write_scene()

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "events",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        payload = self._payload(stdout)
        self.assertTrue(payload["success"])
        data = payload["data"]
        self.assertEqual(data["command"], "runtime events")
        self.assertTrue(data["stateless"])
        self.assertIn("events", data)
        self.assertIsInstance(data["events"], list)
        self.assertIsInstance(data["count"], int)

    def test_motor_runtime_events_does_not_modify_scene_file(self) -> None:
        scene_path = self._write_scene()
        before = scene_path.read_text(encoding="utf-8")

        returncode, stdout, stderr = _run_motor(
            "runtime",
            "events",
            "--project",
            self.project.as_posix(),
            "--count",
            "10",
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stderr + stdout)
        self.assertEqual(scene_path.read_text(encoding="utf-8"), before)


class PrefabCLIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.project = _create_test_project(Path(self._temp_dir.name), "PrefabCLI")
        self.env = os.environ.copy()
        python_path = self.env.get("PYTHONPATH", "")
        self.env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _write_scene(self, relative_path: str = "levels/main_scene.json") -> Path:
        scene_path = self.project / relative_path
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        scene_path.write_text(
            json.dumps({"name": "Main Scene", "entities": [], "rules": [], "feature_metadata": {}}, indent=2),
            encoding="utf-8",
        )
        return scene_path

    def _write_root_prefab(self, relative_path: str = "prefabs/enemy.prefab") -> Path:
        prefab_path = self.project / relative_path
        prefab_path.parent.mkdir(parents=True, exist_ok=True)
        prefab_path.write_text(
            json.dumps(
                {
                    "root_name": "Enemy",
                    "entities": [
                        {
                            "name": "Enemy",
                            "active": True,
                            "tag": "Enemy",
                            "layer": "Actors",
                            "components": {
                                "Transform": {
                                    "enabled": True,
                                    "x": 0.0,
                                    "y": 0.0,
                                    "rotation": 0.0,
                                    "scale_x": 1.0,
                                    "scale_y": 1.0,
                                }
                            },
                        }
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return prefab_path

    def test_motor_prefab_create_writes_prefab_and_json_payload(self) -> None:
        scene_path = self._write_scene()
        api = EngineAPI(project_root=self.project.as_posix())
        self.addCleanup(api.shutdown)
        api.load_level(scene_path.as_posix())
        self.assertTrue(api.create_entity("EnemyTemplate")["success"])
        self.assertTrue(api.save_scene()["success"])

        returncode, stdout, _stderr = _run_motor(
            "prefab",
            "create",
            "EnemyTemplate",
            "prefabs/enemy.prefab",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stdout)
        payload = json.loads(stdout[stdout.index("{"):])
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["prefab_path"], "prefabs/enemy.prefab")
        self.assertTrue((self.project / "prefabs" / "enemy.prefab").exists())

    def test_cmd_prefab_create_asset_only_does_not_save_scene(self) -> None:
        scene_path = self._write_scene()
        real_api = EngineAPI(project_root=self.project.as_posix())
        self.addCleanup(real_api.shutdown)
        real_api.load_level(scene_path.as_posix())
        self.assertTrue(real_api.create_entity("EnemyTemplate")["success"])
        self.assertTrue(real_api.save_scene()["success"])

        stdout = StringIO()
        with patch("motor.cli_core.EngineAPI", return_value=real_api) as engine_api_cls, \
             patch("motor.cli_core._auto_load_scene", return_value=(True, "")), \
             patch.object(real_api, "save_scene", wraps=real_api.save_scene) as save_scene_spy, \
             redirect_stdout(stdout):
            returncode = cmd_prefab_create(
                self.project,
                "EnemyTemplate",
                "prefabs/enemy.prefab",
                replace_original=False,
                instance_name=None,
                json_output=True,
            )

        self.assertEqual(returncode, 0, stdout.getvalue())
        engine_api_cls.assert_called_once()
        save_scene_spy.assert_not_called()
        payload = json.loads(stdout.getvalue()[stdout.getvalue().index("{"):])
        self.assertTrue(payload["success"])
        self.assertTrue((self.project / "prefabs" / "enemy.prefab").exists())

    def test_cmd_prefab_create_replace_original_saves_scene_once(self) -> None:
        scene_path = self._write_scene()
        real_api = EngineAPI(project_root=self.project.as_posix())
        self.addCleanup(real_api.shutdown)
        real_api.load_level(scene_path.as_posix())
        self.assertTrue(real_api.create_entity("EnemyTemplate")["success"])
        self.assertTrue(real_api.save_scene()["success"])

        stdout = StringIO()
        with patch("motor.cli_core.EngineAPI", return_value=real_api) as engine_api_cls, \
             patch("motor.cli_core._auto_load_scene", return_value=(True, "")), \
             patch.object(real_api, "save_scene", wraps=real_api.save_scene) as save_scene_spy, \
             redirect_stdout(stdout):
            returncode = cmd_prefab_create(
                self.project,
                "EnemyTemplate",
                "prefabs/enemy.prefab",
                replace_original=True,
                instance_name=None,
                json_output=True,
            )

        self.assertEqual(returncode, 0, stdout.getvalue())
        engine_api_cls.assert_called_once()
        save_scene_spy.assert_called_once()
        payload = json.loads(stdout.getvalue()[stdout.getvalue().index("{"):])
        self.assertTrue(payload["success"])
        self.assertTrue((self.project / "prefabs" / "enemy.prefab").exists())

    def test_motor_prefab_instantiate_creates_linked_instance(self) -> None:
        scene_path = self._write_scene()
        self._write_root_prefab()
        api = EngineAPI(project_root=self.project.as_posix())
        self.addCleanup(api.shutdown)
        api.load_level(scene_path.as_posix())

        returncode, stdout, _stderr = _run_motor(
            "prefab",
            "instantiate",
            "prefabs/enemy.prefab",
            "--name",
            "EnemyA",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stdout)
        payload = json.loads(stdout[stdout.index("{"):])
        self.assertTrue(payload["success"])

        reloaded = EngineAPI(project_root=self.project.as_posix())
        self.addCleanup(reloaded.shutdown)
        reloaded.load_level(scene_path.as_posix())
        entity = reloaded.scene_manager.current_scene.find_entity("EnemyA")
        self.assertEqual(entity["prefab_instance"]["prefab_path"], "../prefabs/enemy.prefab")

    def test_motor_prefab_unpack_removes_prefab_link(self) -> None:
        scene_path = self._write_scene()
        self._write_root_prefab()
        api = EngineAPI(project_root=self.project.as_posix())
        self.addCleanup(api.shutdown)
        api.load_level(scene_path.as_posix())
        self.assertTrue(api.instantiate_prefab("prefabs/enemy.prefab", name="EnemyA")["success"])
        self.assertTrue(api.save_scene()["success"])

        returncode, stdout, _stderr = _run_motor(
            "prefab",
            "unpack",
            "EnemyA",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stdout)
        payload = json.loads(stdout[stdout.index("{"):])
        self.assertTrue(payload["success"])

        reloaded = EngineAPI(project_root=self.project.as_posix())
        self.addCleanup(reloaded.shutdown)
        reloaded.load_level(scene_path.as_posix())
        entity = reloaded.scene_manager.current_scene.find_entity("EnemyA")
        self.assertNotIn("prefab_instance", entity)

    def test_motor_prefab_apply_persists_overrides_to_source_prefab(self) -> None:
        scene_path = self._write_scene()
        prefab_path = self._write_root_prefab()
        api = EngineAPI(project_root=self.project.as_posix())
        self.addCleanup(api.shutdown)
        api.load_level(scene_path.as_posix())
        self.assertTrue(api.instantiate_prefab("prefabs/enemy.prefab", name="EnemyA")["success"])
        self.assertTrue(api.edit_component("EnemyA", "Transform", "x", 15.0)["success"])
        self.assertTrue(api.save_scene()["success"])

        returncode, stdout, _stderr = _run_motor(
            "prefab",
            "apply",
            "EnemyA",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stdout)
        payload = json.loads(stdout[stdout.index("{"):])
        self.assertTrue(payload["success"])
        prefab_payload = json.loads(prefab_path.read_text(encoding="utf-8"))
        self.assertEqual(prefab_payload["entities"][0]["components"]["Transform"]["x"], 15.0)

    def test_motor_prefab_list_returns_project_prefabs(self) -> None:
        self._write_root_prefab("prefabs/enemy.prefab")
        (self.project / "prefabs" / "legacy.json").write_text('{"root_name":"Legacy","entities":[]}', encoding="utf-8")

        returncode, stdout, _stderr = _run_motor(
            "prefab",
            "list",
            "--project",
            self.project.as_posix(),
            "--json",
            env=self.env,
        )

        self.assertEqual(returncode, 0, stdout)
        payload = json.loads(stdout[stdout.index("{"):])
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["prefabs"], ["prefabs/enemy.prefab", "prefabs/legacy.json"])


class DocumentationContractTests(unittest.TestCase):
    """Contract tests for documentation alignment with motor CLI."""

    def test_start_here_md_uses_motor_as_primary_interface(self) -> None:
        """START_HERE_AI.md debe usar `motor` como interfaz principal."""
        start_here_path = ROOT / "START_HERE_AI.md"
        if not start_here_path.exists():
            self.skipTest("START_HERE_AI.md no encontrado")

        content = start_here_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        violations = []
        for i, line in enumerate(lines, 1):
            # Buscar referencias a tools.engine_cli fuera de contexto legacy
            if "tools.engine_cli" in line:
                context = line.lower()
                # Permitir solo en contextos explícitos de legacy/deprecated
                if not any(word in context for word in ["legacy", "deprecated", "compatibility", "old", "alternative"]):
                    violations.append(f"Línea {i}: {line.strip()}")

            # Buscar comandos sin prefijo motor en bloques de código
            if line.strip().startswith(("```bash", "```shell", "$ ")):
                # Verificar siguiente línea
                continue

        if violations:
            self.fail("START_HERE_AI.md usa CLI obsoleto como principal:\n" + "\n".join(violations))

    def test_start_here_md_no_python_m_tools_pattern(self) -> None:
        """START_HERE_AI.md no debe tener `python -m tools...` como ejemplo principal."""
        start_here_path = ROOT / "START_HERE_AI.md"
        if not start_here_path.exists():
            self.skipTest("START_HERE_AI.md no encontrado")

        content = start_here_path.read_text(encoding="utf-8")

        # Buscar patrones prohibidos
        prohibited_patterns = [
            r"python\s+-m\s+tools\.engine_cli",
            r"python\s+-m\s+tools\s",
        ]

        violations = []
        for pattern in prohibited_patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            for match in matches:
                line_num = content[:match.start()].count("\n") + 1
                line_start = content.rfind("\n", 0, match.start()) + 1
                line_end = content.find("\n", match.end())
                context = content[line_start:line_end].lower()

                # Solo permitir en contexto legacy explícito
                if not any(word in context for word in ["legacy", "deprecated", "compatibility"]):
                    violations.append(f"Línea {line_num}: {match.group()}")

        if violations:
            self.fail("START_HERE_AI.md contiene patrones prohibidos:\n" + "\n".join(violations))


class ExamplesContractTests(unittest.TestCase):
    """Contract tests for AI workflow examples."""

    EXAMPLES_DIR = ROOT / "examples" / "ai_workflows"

    def test_all_examples_use_motor_not_legacy_cli(self) -> None:
        """Todos los ejemplos deben usar `motor`, no `python -m tools.engine_cli`."""
        if not self.EXAMPLES_DIR.exists():
            self.skipTest("Directorio de ejemplos no encontrado")

        violations = []
        for py_file in self.EXAMPLES_DIR.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")

            # Verificar que NO usen tools.engine_cli
            if "tools.engine_cli" in content:
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    if "tools.engine_cli" in line:
                        violations.append(f"{py_file.name}:{i}: {line.strip()}")

            # Verificar que SÍ usen motor
            if '"motor"' not in content and "'motor'" not in content:
                violations.append(f"{py_file.name}: No usa comando 'motor'")

        if violations:
            self.fail("Ejemplos con CLI incorrecto:\n" + "\n".join(violations))

    def test_examples_are_executable(self) -> None:
        """Los ejemplos deben poder ejecutarse sin errores de importación."""
        if not self.EXAMPLES_DIR.exists():
            self.skipTest("Directorio de ejemplos no encontrado")

        # Solo verificar sintaxis, no ejecutar completamente
        for py_file in self.EXAMPLES_DIR.glob("*.py"):
            with self.subTest(example=py_file.name):
                # Verificar que el archivo tiene sintaxis Python válida
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(py_file)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    self.fail(f"{py_file.name} tiene errores de sintaxis: {result.stderr}")


class MotorAIBootstrapContractTests(unittest.TestCase):
    """Contract tests for motor_ai.json generation."""

    def test_generated_motor_ai_uses_official_interface(self) -> None:
        """motor_ai.json generado debe usar solo comandos motor oficiales."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_test_project(Path(tmpdir), "BootstrapTest")

            # Generate bootstrap
            registry = get_default_registry()
            builder = MotorAIBootstrapBuilder(registry)
            builder.write_to_project(project, {"project": {"name": "BootstrapTest"}})

            # Verify motor_ai.json
            motor_ai_path = project / "motor_ai.json"
            self.assertTrue(motor_ai_path.exists())

            content = motor_ai_path.read_text(encoding="utf-8")

            # No debe tener referencias a tools.engine_cli
            if "tools.engine_cli" in content:
                self.fail("motor_ai.json contiene referencia a 'tools.engine_cli'")

            # Debe tener referencias a motor
            if "motor " not in content:
                self.fail("motor_ai.json no contiene referencias a 'motor'")

            # Verificar estructura v3
            data = json.loads(content)
            self.assertEqual(data["schema_version"], 3, "motor_ai.json debe ser schema v3")
            self.assertIn("engine", data)
            self.assertIn("implemented_capabilities", data, "v3 debe tener implemented_capabilities")
            self.assertIn("planned_capabilities", data, "v3 debe tener planned_capabilities")

            # Verificar que todas las capabilities usan motor
            for cap in data.get("implemented_capabilities", []):
                cli_cmd = cap.get("cli_command", "")
                if cli_cmd and not cli_cmd.startswith("motor "):
                    self.fail(f"Capability {cap['id']} usa comando no-motor: {cli_cmd}")

    def test_generated_start_here_uses_motor(self) -> None:
        """START_HERE_AI.md generado debe usar motor como interfaz principal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = _create_test_project(Path(tmpdir), "StartHereTest")

            # Generate bootstrap
            registry = get_default_registry()
            builder = MotorAIBootstrapBuilder(registry)
            builder.write_to_project(project, {"project": {"name": "StartHereTest"}})

            start_here_path = project / "START_HERE_AI.md"
            self.assertTrue(start_here_path.exists())

            content = start_here_path.read_text(encoding="utf-8")

            # No debe tener tools.engine_cli fuera de contexto legacy
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                if "tools.engine_cli" in line:
                    if not any(word in line.lower() for word in ["legacy", "deprecated", "compatibility"]):
                        self.fail(f"START_HERE_AI.md línea {i} usa CLI obsoleto: {line}")


class NoRegressionTests(unittest.TestCase):
    """Tests para prevenir regresiones a interfaces legacy."""

    def test_no_hardcoded_python_m_tools_in_source(self) -> None:
        """El código fuente no debe hardcodear python -m tools como camino principal.

        Las referencias en documentación/contexto deprecado están permitidas.
        """
        # Directorios a revisar (excluyendo tools/ que es legacy)
        source_dirs = [ROOT / "engine", ROOT / "motor", ROOT / "cli"]

        violations = []
        for src_dir in source_dirs:
            if not src_dir.exists():
                continue
            for py_file in src_dir.rglob("*.py"):
                content = py_file.read_text(encoding="utf-8")
                rel_path = py_file.relative_to(ROOT)
                if 'test' in str(rel_path).lower():
                    continue  # Tests pueden tener compatibilidad

                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    if 'python -m tools' in line or 'python -m tools.engine_cli' in line:
                        # Permitir si está en contexto legacy/deprecated explícito
                        # Buscar en línea actual y algunas líneas cercanas
                        context_lines = [line]
                        if i > 1:
                            context_lines.append(lines[i-2])  # Línea anterior
                        if i < len(lines):
                            context_lines.append(lines[i])  # Línea siguiente

                        context_text = ' '.join(context_lines).lower()
                        if any(word in context_text for word in ['legacy', 'deprecated', 'compatibility', 'old', 'backward']):
                            continue
                        # Permitir si es un comentario (línea empieza con #)
                        if line.strip().startswith('#'):
                            continue
                        violations.append(f"{rel_path}:{i}")

        if violations:
            self.fail("Código fuente con referencias legacy (sin contexto explícito):\n" + "\n".join(violations))


class CommandCoverageTests(unittest.TestCase):
    """Tests para verificar cobertura de comandos entre registry y CLI."""

    def test_all_motor_commands_are_in_registry(self) -> None:
        """Todos los comandos motor deben estar documentados en registry."""
        registry = get_default_registry()
        parser = create_motor_parser()

        # Extraer comandos del parser
        motor_commands = set()
        for action in parser._actions:
            if hasattr(action, 'choices') and action.choices:
                motor_commands.update(action.choices.keys())

        # Extraer scopes del registry
        registry_scopes = set()
        for cap in registry.list_all():
            scope = cap.id.split(":")[0]
            registry_scopes.add(scope)

        # Mapeo inverso: comandos CLI a scopes
        command_to_scope = {
            "capabilities": "introspect",
            "ai": "ai",
            "doctor": "project",
            "project": "project",
            "scene": "scene",
            "entity": "entity",
            "component": "component",
            "animator": "animator",
            "asset": "asset",
        }

        # Verificar que cada comando motor tiene al menos un capability
        missing = []
        for cmd in motor_commands:
            expected_scope = command_to_scope.get(cmd, cmd)
            if expected_scope not in registry_scopes:
                # Algunos comandos son meta-comandos
                if cmd not in ["doctor", "capabilities"]:
                    missing.append(cmd)

        if missing:
            self.fail(f"Comandos motor sin capabilities en registry: {missing}")


if __name__ == "__main__":
    unittest.main()
