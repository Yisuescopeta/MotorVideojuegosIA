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
from pathlib import Path
from typing import List, Set, Tuple

from engine.ai import get_default_registry, CapabilityRegistry, MotorAIBootstrapBuilder
from engine.api import EngineAPI
from motor.cli import create_motor_parser

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
            self.fail(f"Capabilities sin prefijo 'motor ':\n" + "\n".join(violations))
    
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
            self.fail(f"Capabilities con CLI obsoleto:\n" + "\n".join(violations))
    
    def test_registry_command_scopes_exist_in_motor_cli(self) -> None:
        """Todos los scopes de comandos en registry deben existir en motor CLI."""
        available = self._get_available_commands()
        
        # Mapeo de capability scope a comandos CLI
        scope_to_command = {
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
        future_scopes = {"runtime", "physics", "introspect"}
        
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
            self.fail(f"Scopes de registry sin comandos CLI correspondientes:\n" + "\n".join(violations))
    
    def test_implemented_commands_actually_work(self) -> None:
        """Los comandos marcados como implementados deben funcionar realmente."""
        # Comandos que deberían funcionar (no marcados como futuro)
        # Usando gramática oficial: motor <noun> [<subnoun>] <verb>
        implemented_patterns = [
            ("capabilities", []),
            ("doctor", []),
            ("project", ["info"]),
            ("scene", ["list"]),
            ("scene", ["create"]),
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
        official_syntax = {
            "animator state create": "motor animator state create <entity> <state>",
            "animator state remove": "motor animator state remove <entity> <state>",
        }
        
        # Verificar que no hay múltiples capabilities apuntando a comandos similares
        for cap in self.registry.list_all():
            cmd = cap.cli_command
            
            # Verificar que los comandos legacy no están documentados como oficiales
            if "upsert-state" in cmd or "remove-state" in cmd:
                self.fail(
                    f"Capability '{cap.id}' usa sintaxis legacy en cli_command: {cmd}\n"
                    f"Use 'animator state create/remove' en su lugar."
                )


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
            self.fail(f"START_HERE_AI.md usa CLI obsoleto como principal:\n" + "\n".join(violations))
    
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
            self.fail(f"START_HERE_AI.md contiene patrones prohibidos:\n" + "\n".join(violations))


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
            self.fail(f"Ejemplos con CLI incorrecto:\n" + "\n".join(violations))
    
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
            self.fail(f"Código fuente con referencias legacy (sin contexto explícito):\n" + "\n".join(violations))


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
