"""
tests/test_motor_interface_coherence.py - Contract tests for motor CLI interface coherence

Ensures alignment between:
- Capability registry cli_command fields
- Actual motor CLI implementation
- START_HERE_AI.md documentation
- AI workflow examples

These tests will fail if the interface drifts or if legacy references persist.

ARCHITECTURE NOTE:
    These tests use the OFFICIAL motor CLI API:
        from motor.cli import create_motor_parser, run_motor_command
    
    They verify that:
    1. The official CLI parser (motor.cli.create_motor_parser) exists and works
    2. Commands can be executed via motor.cli.run_motor_command
    3. python -m motor works as entrypoint
    
    Do NOT use tools.engine_cli in these tests - it is deprecated.
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

from engine.ai import get_default_registry

# Import official CLI API
from motor.cli import create_motor_parser, run_motor_command

ROOT = Path(__file__).resolve().parents[1]


def _run_motor_subprocess(*args: str, env: dict | None = None) -> tuple[int, str, str]:
    """Run motor CLI command and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "-m", "motor"] + list(args)
    
    if env is None:
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.returncode, result.stdout, result.stderr


class MotorRegistryAlignmentTests(unittest.TestCase):
    """Tests that registry cli_command fields align with actual motor CLI."""
    
    @classmethod
    def setUpClass(cls):
        cls.registry = get_default_registry()
    
    def test_all_capabilities_use_motor_prefix(self) -> None:
        """All cli_command fields must start with 'motor '."""
        violations = []
        for cap in self.registry.list_all():
            if not cap.cli_command.startswith("motor "):
                violations.append(f"{cap.id}: {cap.cli_command}")
        
        if violations:
            self.fail(f"Capabilities without 'motor ' prefix:\n" + "\n".join(violations))
    
    def test_no_capabilities_use_deprecated_tools_engine_cli(self) -> None:
        """No cli_command should reference tools.engine_cli."""
        violations = []
        for cap in self.registry.list_all():
            if "tools.engine_cli" in cap.cli_command:
                violations.append(f"{cap.id}: {cap.cli_command}")
        
        if violations:
            self.fail(f"Capabilities using deprecated tools.engine_cli:\n" + "\n".join(violations))
    
    def test_registry_commands_are_executable_or_marked_future(self) -> None:
        """Registry commands should either work or be marked as future."""
        # Commands that are expected to fail (not yet implemented)
        known_future_commands = {
            "motor runtime play",
            "motor runtime pause",
            "motor runtime stop",
            "motor prefab create",
            "motor prefab edit",
            "motor prefab list",
            "motor physics query aabb",
            "motor physics query ray",
            "motor physics backends",
            "motor scene flow load-next",
            "motor scene flow load-menu",
            "motor asset refresh",
            "motor project manifest",
            "motor project state",
            "motor undo",
            "motor redo",
            "motor status",
        }
        
        for cap in self.registry.list_all():
            cmd = cap.cli_command
            
            # Skip known future commands
            if cmd in known_future_commands:
                continue
            
            # Skip commands that require arguments
            if "<" in cmd or "..." in cmd:
                continue
            
            # Check that help exists for this command
            parts = cmd.split()[1:]  # Remove 'motor' prefix
            if not parts:
                continue
                
            # Try --help on the command path
            help_args = parts + ["--help"]
            returncode, stdout, stderr = _run_motor_subprocess(*help_args)
            
            # --help should return 0 even if command needs more args
            if returncode != 0 and "error" in (stderr + stdout).lower():
                # This might be a command that doesn't exist
                self.fail(f"Command '{cmd}' from capability '{cap.id}' appears to not exist. "
                         f"Either implement it or mark it as future. Return code: {returncode}")


class MotorDocumentationAlignmentTests(unittest.TestCase):
    """Tests that documentation uses official motor interface."""
    
    def test_start_here_md_uses_motor_not_tools_engine_cli(self) -> None:
        """START_HERE_AI.md must use 'motor ' not 'tools.engine_cli' except in compatibility notes."""
        start_here_path = ROOT / "START_HERE_AI.md"
        
        if not start_here_path.exists():
            self.skipTest("START_HERE_AI.md not found")
        
        content = start_here_path.read_text(encoding="utf-8")
        
        # Check for deprecated references, but allow them in context of "Legacy", "deprecated", "compatibility"
        deprecated_patterns = [
            r"python\s+-m\s+tools\.engine_cli",
            r"tools\.engine_cli",
        ]
        
        violations = []
        for pattern in deprecated_patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            for match in matches:
                # Get line number and surrounding context
                line_num = content[:match.start()].count("\n") + 1
                line_start = content.rfind("\n", 0, match.start()) + 1
                line_end = content.find("\n", match.end())
                context = content[line_start:line_end].lower()
                
                # Skip if this is in a compatibility/legacy context
                if any(word in context for word in ["legacy", "deprecated", "compatibility", "old"]):
                    continue
                
                violations.append(f"Line {line_num}: {match.group()}")
        
        if violations:
            self.fail(f"START_HERE_AI.md contains deprecated references:\n" + "\n".join(violations))
    
    def test_start_here_md_commands_use_motor_prefix(self) -> None:
        """Commands in START_HERE_AI.md should use 'motor ' prefix."""
        start_here_path = ROOT / "START_HERE_AI.md"
        
        if not start_here_path.exists():
            self.skipTest("START_HERE_AI.md not found")
        
        content = start_here_path.read_text(encoding="utf-8")
        
        # Find code blocks and command lines
        violations = []
        lines = content.split("\n")
        
        for i, line in enumerate(lines, 1):
            # Look for lines that look like commands but don't use motor
            if line.strip().startswith(("$ ", "> ")):
                cmd_part = line.strip()[2:]  # Remove prefix
                if cmd_part.startswith(("scene ", "entity ", "asset ", "animator ", 
                                       "doctor", "capabilities", "project ", "component ")):
                    violations.append(f"Line {i}: {line.strip()}")
        
        if violations:
            self.fail(f"Commands missing 'motor ' prefix in START_HERE_AI.md:\n" + "\n".join(violations))


class MotorExamplesAlignmentTests(unittest.TestCase):
    """Tests that AI workflow examples use official motor interface."""
    
    EXAMPLES_DIR = ROOT / "examples" / "ai_workflows"
    
    def test_examples_use_motor_not_tools_engine_cli(self) -> None:
        """Examples must use 'motor' command, not 'python -m tools.engine_cli'."""
        if not self.EXAMPLES_DIR.exists():
            self.skipTest("Examples directory not found")
        
        violations = []
        
        for py_file in self.EXAMPLES_DIR.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            
            # Check for deprecated patterns
            if "tools.engine_cli" in content:
                lines = content.split("\n")
                for i, line in enumerate(lines, 1):
                    if "tools.engine_cli" in line:
                        violations.append(f"{py_file.name}:{i}: {line.strip()}")
        
        if violations:
            self.fail(f"Examples using deprecated tools.engine_cli:\n" + "\n".join(violations))
    
    def test_examples_import_and_use_motor_env(self) -> None:
        """Examples should set up PYTHONPATH for motor CLI."""
        if not self.EXAMPLES_DIR.exists():
            self.skipTest("Examples directory not found")
        
        for py_file in self.EXAMPLES_DIR.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            
            # Examples should configure PYTHONPATH
            if "PYTHONPATH" not in content:
                self.fail(f"{py_file.name} does not configure PYTHONPATH for motor CLI")
            
            # Examples should use 'motor' command
            if '"motor"' not in content and "'motor'" not in content:
                self.fail(f"{py_file.name} does not use 'motor' command")


class MotorBootstrapCoherenceTests(unittest.TestCase):
    """Tests that motor_ai.json bootstrap is coherent with CLI."""
    
    def test_bootstrap_references_official_interface(self) -> None:
        """motor_ai.json content should reference motor CLI, not tools.engine_cli."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "Test"
            project.mkdir()
            (project / "project.json").write_text(
                json.dumps({
                    "name": "Test",
                    "version": 2,
                    "paths": {
                        "assets": "assets", "levels": "levels",
                        "scripts": "scripts", "settings": "settings",
                        "meta": ".motor/meta", "build": ".motor/build"
                    },
                }),
                encoding="utf-8",
            )
            for d in ["assets", "levels", "scripts", "settings", ".motor"]:
                (project / d).mkdir(parents=True, exist_ok=True)
            
            # Generate bootstrap
            from engine.ai import get_default_registry, MotorAIBootstrapBuilder
            registry = get_default_registry()
            builder = MotorAIBootstrapBuilder(registry)
            builder.write_to_project(project, {"project": {"name": "Test"}})
            
            # Check motor_ai.json
            motor_ai_path = project / "motor_ai.json"
            self.assertTrue(motor_ai_path.exists())
            
            content = motor_ai_path.read_text(encoding="utf-8")
            
            # Should not have deprecated references
            if "tools.engine_cli" in content:
                self.fail("motor_ai.json contains deprecated 'tools.engine_cli' reference")
            
            # Should have motor references
            if "motor " not in content:
                self.fail("motor_ai.json does not reference 'motor' CLI")
            
            # Check START_HERE_AI.md
            start_here_path = project / "START_HERE_AI.md"
            self.assertTrue(start_here_path.exists())
            
            md_content = start_here_path.read_text(encoding="utf-8")
            
            # Should not have deprecated references except in compatibility context
            lines = md_content.split("\n")
            for i, line in enumerate(lines, 1):
                if "tools.engine_cli" in line:
                    # Skip if this is in a compatibility/legacy context
                    if any(word in line.lower() for word in ["legacy", "deprecated", "compatibility", "old"]):
                        continue
                    self.fail(f"START_HERE_AI.md line {i} contains deprecated 'tools.engine_cli' reference: {line}")


class MotorCLIContractTests(unittest.TestCase):
    """Executable contract tests for motor CLI commands."""
    
    def test_capabilities_command_is_available(self) -> None:
        """motor capabilities must work and return valid JSON."""
        returncode, stdout, stderr = _run_motor_subprocess("capabilities", "--json")
        
        if returncode != 0:
            self.fail(f"capabilities command failed with code {returncode}: {stderr}")
        
        # Parse JSON
        if "{" in stdout:
            stdout = stdout[stdout.index("{"):]
        
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            self.fail(f"capabilities returned invalid JSON: {e}\nOutput: {stdout[:200]}")
        
        # Check structure
        self.assertIn("success", data)
        self.assertIn("data", data)
        self.assertTrue(data["success"])
        self.assertIn("capabilities", data["data"])
    
    def test_doctor_command_is_available(self) -> None:
        """motor doctor must work with a valid project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "Test"
            project.mkdir()
            (project / "project.json").write_text(
                json.dumps({
                    "name": "Test",
                    "version": 2,
                    "paths": {
                        "assets": "assets", "levels": "levels",
                        "scripts": "scripts", "settings": "settings",
                        "meta": ".motor/meta", "build": ".motor/build"
                    },
                }),
                encoding="utf-8",
            )
            for d in ["assets", "levels", "scripts", "settings", ".motor"]:
                (project / d).mkdir(parents=True, exist_ok=True)
            
            returncode, stdout, stderr = _run_motor_subprocess(
                "doctor", "--project", str(project), "--json"
            )
            
            if returncode != 0:
                self.fail(f"doctor command failed with code {returncode}: {stderr}")
            
            # Parse JSON
            if "{" in stdout:
                stdout = stdout[stdout.index("{"):]
            
            try:
                data = json.loads(stdout)
            except json.JSONDecodeError as e:
                self.fail(f"doctor returned invalid JSON: {e}\nOutput: {stdout[:200]}")
            
            # Check structure
            self.assertIn("success", data)
            self.assertIn("data", data)
            self.assertIn("healthy", data["data"])
    
    def test_scene_create_and_list_commands_work(self) -> None:
        """motor scene create and list must work end-to-end."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "Test"
            project.mkdir()
            (project / "project.json").write_text(
                json.dumps({
                    "name": "Test",
                    "version": 2,
                    "paths": {
                        "assets": "assets", "levels": "levels",
                        "scripts": "scripts", "settings": "settings",
                        "meta": ".motor/meta", "build": ".motor/build"
                    },
                }),
                encoding="utf-8",
            )
            for d in ["assets", "levels", "scripts", "settings", ".motor"]:
                (project / d).mkdir(parents=True, exist_ok=True)
            
            # Create scene
            returncode, stdout, stderr = _run_motor_subprocess(
                "scene", "create", "TestScene", "--project", str(project), "--json"
            )
            
            if returncode != 0:
                self.fail(f"scene create failed with code {returncode}: {stderr}")
            
            # Parse JSON
            if "{" in stdout:
                stdout = stdout[stdout.index("{"):]
            
            data = json.loads(stdout)
            self.assertTrue(data.get("success"), f"scene create failed: {data}")
            
            # List scenes
            returncode, stdout, stderr = _run_motor_subprocess(
                "scene", "list", "--project", str(project), "--json"
            )
            
            if "{" in stdout:
                stdout = stdout[stdout.index("{"):]
            
            data = json.loads(stdout)
            self.assertTrue(data.get("success"), f"scene list failed: {data}")
            self.assertGreaterEqual(data["data"]["count"], 1)


class MotorNoRegressionTests(unittest.TestCase):
    """Tests that prevent regression to legacy interfaces."""
    
    def test_no_hardcoded_python_m_tools_engine_cli_in_tests(self) -> None:
        """Test files should not hardcode python -m tools.engine_cli as primary."""
        tests_dir = ROOT / "tests"
        
        violations = []
        for py_file in tests_dir.rglob("*.py"):
            # Skip files that explicitly test backward compatibility
            if py_file.name in ["test_motor_entrypoint.py", "test_engine_cli.py", "test_motor_interface_coherence.py"]:
                continue
            
            content = py_file.read_text(encoding="utf-8")
            
            # Check for patterns that EXECUTE tools.engine_cli (not just reference it in strings or comments)
            # Look for subprocess.run patterns that actually call the command
            execute_patterns = [
                r'subprocess\.run\s*\(\s*\[\s*sys\.executable\s*,\s*["\']-m["\']\s*,\s*["\']tools\.engine_cli["\']',
                r'subprocess\.run\s*\(\s*\[\s*["\']python["\']\s*,\s*["\']-m["\']\s*,\s*["\']tools\.engine_cli["\']',
            ]
            
            for pattern in execute_patterns:
                matches = list(re.finditer(pattern, content))
                if matches:
                    # Check if this is in a context of testing backward compatibility
                    for match in matches:
                        # Get surrounding context (50 chars before and after)
                        start = max(0, match.start() - 50)
                        end = min(len(content), match.end() + 50)
                        context = content[start:end].lower()
                        
                        # Skip if in legacy/compatibility context
                        if any(word in context for word in ['legacy', 'deprecated', 'backward', 'compatibility', 'old']):
                            continue
                        
                        line_num = content[:match.start()].count("\n") + 1
                        violations.append(f"{py_file.name}:{line_num}")
        
        if violations:
            self.fail(f"Tests ejecutando tools.engine_cli como principal (deberían usar 'motor'):\n" + "\n".join(violations))


class MotorCLIContractExecutableTests(unittest.TestCase):
    """Executable contract tests - commands must actually work."""
    
    @classmethod
    def setUpClass(cls):
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls.workspace = Path(cls._temp_dir.name)
        cls.project = cls.workspace / "TestProject"
        cls.project.mkdir()
        
        # Create minimal project
        (cls.project / "project.json").write_text(
            json.dumps({
                "name": "TestProject",
                "version": 2,
                "engine_version": "2026.03",
                "template": "empty",
                "paths": {
                    "assets": "assets", "levels": "levels",
                    "prefabs": "prefabs", "scripts": "scripts",
                    "settings": "settings", "meta": ".motor/meta",
                    "build": ".motor/build"
                },
            }),
            encoding="utf-8",
        )
        for d in ["assets", "levels", "scripts", "settings", ".motor"]:
            (cls.project / d).mkdir(parents=True, exist_ok=True)
        
        cls.env = os.environ.copy()
        python_path = cls.env.get("PYTHONPATH", "")
        cls.env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    
    @classmethod
    def tearDownClass(cls):
        cls._temp_dir.cleanup()
    
    def _run_motor(self, *args):
        """Execute motor command and return result."""
        cmd = [sys.executable, "-m", "motor"] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, env=self.env, cwd=str(self.project))
    
    def test_motor_entity_create_works_end_to_end(self) -> None:
        """motor entity create must actually create entities."""
        # First create a scene
        self._run_motor("scene", "create", "EntityTest", "--json")
        
        # Create entity
        result = self._run_motor("entity", "create", "TestEntity", "--json")
        self.assertEqual(result.returncode, 0, f"entity create failed: {result.stderr}")
        
        output = result.stdout
        if "{" in output:
            output = output[output.index("{"):]
        data = json.loads(output)
        self.assertTrue(data.get("success"), f"entity create returned failure: {data}")
    
    def test_motor_component_add_works_end_to_end(self) -> None:
        """motor component add must actually add components."""
        # Setup
        self._run_motor("scene", "create", "ComponentTest", "--json")
        self._run_motor("entity", "create", "Player", "--json")
        
        # Add component
        result = self._run_motor(
            "component", "add", "Player", "Transform",
            "--data", '{"x": 100, "y": 200}',
            "--json"
        )
        self.assertEqual(result.returncode, 0, f"component add failed: {result.stderr}")
        
        output = result.stdout
        if "{" in output:
            output = output[output.index("{"):]
        data = json.loads(output)
        self.assertTrue(data.get("success"), f"component add returned failure: {data}")
    
    def test_motor_animator_commands_work_end_to_end(self) -> None:
        """motor animator commands must work."""
        # Setup
        self._run_motor("scene", "create", "AnimatorTest", "--json")
        self._run_motor("entity", "create", "AnimatedEntity", "--json")
        
        # Test animator ensure
        result = self._run_motor("animator", "ensure", "AnimatedEntity", "--json")
        self.assertEqual(result.returncode, 0, f"animator ensure failed: {result.stderr}")
        
        output = result.stdout
        if "{" in output:
            output = output[output.index("{"):]
        data = json.loads(output)
        self.assertTrue(data.get("success"), f"animator ensure returned failure: {data}")
        
        # Test animator info
        result = self._run_motor("animator", "info", "AnimatedEntity", "--json")
        self.assertEqual(result.returncode, 0, f"animator info failed: {result.stderr}")


class RegistryToCLICoherenceTests(unittest.TestCase):
    """Tests ensuring registry and CLI stay aligned."""
    
    def test_registry_commands_match_implementation(self) -> None:
        """Registry commands should match actual CLI implementation."""
        from motor.cli import create_motor_parser
        registry = get_default_registry()
        parser = create_motor_parser()
        
        # Extract available commands (hasta 3 niveles de profundidad)
        available_commands = set()
        for action in parser._actions:
            if hasattr(action, 'choices') and action.choices:
                for cmd_name, subparser in action.choices.items():
                    available_commands.add(cmd_name)
                    if hasattr(subparser, '_actions'):
                        for sub_action in subparser._actions:
                            if hasattr(sub_action, 'choices') and sub_action.choices:
                                for sub_cmd, sub_subparser in sub_action.choices.items():
                                    available_commands.add(f"{cmd_name} {sub_cmd}")
                                    # Tercer nivel (ej: animator state create)
                                    if hasattr(sub_subparser, '_actions'):
                                        for sub_sub_action in sub_subparser._actions:
                                            if hasattr(sub_sub_action, 'choices') and sub_sub_action.choices:
                                                for sub_sub_cmd in sub_sub_action.choices.keys():
                                                    available_commands.add(f"{cmd_name} {sub_cmd} {sub_sub_cmd}")
        
        # Check registry commands
        missing_commands = []
        for cap in registry.list_all():
            cmd_parts = cap.cli_command.split()[1:]  # Remove 'motor'
            if not cmd_parts:
                continue
            
            # Construir path completo del comando
            full_path = " ".join(cmd_parts)
            
            # Skip commands that require arguments (can't test without them)
            if any(c in cap.cli_command for c in ["<", "[", "..."]):
                continue
            
            # Skip known future commands
            future_commands = {
                "runtime", "prefab", "undo", "redo", "status", "physics"
            }
            if cmd_parts[0] in future_commands:
                continue
            
            # Verificar si el comando existe (match exacto o parcial)
            if full_path not in available_commands:
                # Verificar si al menos el primer nivel existe
                if cmd_parts[0] not in available_commands:
                    missing_commands.append(f"{cap.id}: {cap.cli_command}")
        
        if missing_commands:
            self.fail(f"Registry commands not in motor CLI:\n" + "\n".join(missing_commands))
    
    def test_no_duplicate_grammar_patterns(self) -> None:
        """No debe haber múltiples patterns gramaticales para la misma operación.
        
        Verifica que no se documenten aliases como comandos oficiales separados.
        """
        registry = get_default_registry()
        
        # Mapeo de operaciones semánticas a su comando único oficial
        semantic_operations = {
            "animator state create": ["motor animator state create", "motor animator upsert-state"],
            "animator state remove": ["motor animator state remove", "motor animator remove-state"],
        }
        
        for operation, possible_commands in semantic_operations.items():
            found_commands = []
            for cap in registry.list_all():
                for cmd_pattern in possible_commands:
                    if cap.cli_command.startswith(cmd_pattern):
                        found_commands.append((cap.id, cap.cli_command))
            
            # Solo debe haber UN comando oficial documentado
            official_commands = [(cid, cmd) for cid, cmd in found_commands 
                               if "upsert-state" not in cmd and "remove-state" not in cmd]
            
            if len(official_commands) > 1:
                self.fail(f"Múltiples comandos oficiales para '{operation}': {official_commands}")


if __name__ == "__main__":
    unittest.main()
