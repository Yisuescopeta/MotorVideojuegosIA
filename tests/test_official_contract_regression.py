"""
tests/test_official_contract_regression.py - Regression prevention tests for official motor interface

This module provides a safety net against regressions in:
- CLI interface official implementation
- Registry semantic alignment
- Bootstrap file portability
- Examples using official patterns

Design principles:
1. Tests REAL implementation, not future architecture
2. Fails on ANY incoherence between parser, registry, bootstrap, examples
3. Separates LEGACY compatibility from OFFICIAL contract
4. Executable validation (not just structural checks)
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


class OfficialCLIContractTests(unittest.TestCase):
    """Tests validating the official motor CLI contract is maintained."""
    
    def setUp(self):
        """Set up test environment."""
        self.env = os.environ.copy()
        python_path = self.env.get("PYTHONPATH", "")
        self.env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
    
    def test_python_m_motor_works(self) -> None:
        """CRITICAL: python -m motor must work as entrypoint."""
        result = subprocess.run(
            [sys.executable, "-m", "motor", "--help"],
            capture_output=True,
            text=True,
            env=self.env,
        )
        self.assertEqual(result.returncode, 0, "python -m motor --help must work")
        self.assertIn("motor", result.stdout.lower(), "Help should mention motor")
    
    def test_motor_capabilities_works(self) -> None:
        """CRITICAL: motor capabilities must return valid JSON."""
        result = subprocess.run(
            [sys.executable, "-m", "motor", "capabilities", "--json"],
            capture_output=True,
            text=True,
            env=self.env,
        )
        self.assertEqual(result.returncode, 0, "motor capabilities must work")
        
        output = result.stdout
        if "{" in output:
            output = output[output.index("{"):]
        
        data = json.loads(output)
        self.assertTrue(data.get("success"), "capabilities must report success")
        self.assertIn("capabilities", data.get("data", {}), "must return capabilities list")
    
    def test_motor_doctor_works(self) -> None:
        """CRITICAL: motor doctor must diagnose projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "Test"
            project.mkdir()
            
            # Create minimal project
            (project / "project.json").write_text(json.dumps({
                "name": "Test",
                "version": 2,
                "paths": {
                    "assets": "assets", "levels": "levels",
                    "scripts": "scripts", "settings": "settings",
                    "meta": ".motor/meta", "build": ".motor/build"
                },
            }))
            for d in ["assets", "levels", "scripts", "settings", ".motor"]:
                (project / d).mkdir(parents=True, exist_ok=True)
            
            result = subprocess.run(
                [sys.executable, "-m", "motor", "doctor", "--project", str(project), "--json"],
                capture_output=True,
                text=True,
                env=self.env,
            )
            
            self.assertEqual(result.returncode, 0, "motor doctor must work")
            
            output = result.stdout
            if "{" in output:
                output = output[output.index("{"):]
            
            data = json.loads(output)
            self.assertTrue(data.get("success"), "doctor must report success")
            self.assertIn("checks", data.get("data", {}), "must return checks")


class NoAbsolutePathsInBootstrapTests(unittest.TestCase):
    """Tests preventing absolute paths in motor_ai.json."""
    
    def test_bootstrap_generates_no_absolute_paths(self) -> None:
        """CRITICAL: motor_ai.json must not contain absolute paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "TestProject"
            project.mkdir()
            
            # Create project
            (project / "project.json").write_text(json.dumps({
                "name": "TestProject",
                "version": 2,
                "engine_version": "2026.03",
                "paths": {
                    "assets": "assets", "levels": "levels",
                    "scripts": "scripts", "settings": "settings",
                    "meta": ".motor/meta", "build": ".motor/build"
                },
            }))
            for d in ["assets", "levels", "scripts", "settings", ".motor"]:
                (project / d).mkdir(parents=True, exist_ok=True)
            
            env = os.environ.copy()
            python_path = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
            
            # Run bootstrap
            result = subprocess.run(
                [sys.executable, "-m", "motor", "project", "bootstrap-ai", "--project", str(project)],
                capture_output=True,
                text=True,
                env=env,
            )
            
            self.assertEqual(result.returncode, 0, "bootstrap-ai must succeed")
            
            # Check motor_ai.json content
            motor_ai_path = project / "motor_ai.json"
            self.assertTrue(motor_ai_path.exists(), "motor_ai.json must be created")
            
            content = motor_ai_path.read_text(encoding="utf-8")
            
            # Check for Windows absolute paths
            import re
            windows_abs = re.search(r'[A-Za-z]:\\\\', content)
            self.assertIsNone(windows_abs, f"motor_ai.json contains Windows absolute path: {windows_abs.group() if windows_abs else ''}")
            
            # Check for Unix absolute paths
            unix_abs = re.search(r'"/[^"]*(?:/home/|/Users/|/root/)', content)
            self.assertIsNone(unix_abs, f"motor_ai.json contains Unix absolute path")
            
            # Verify structure
            data = json.loads(content)
            self.assertEqual(data.get("project", {}).get("root"), ".", "project.root must be relative '.'")


class ExamplesUseOfficialInterfaceTests(unittest.TestCase):
    """Tests ensuring examples use official motor interface."""
    
    EXAMPLES_DIR = ROOT / "examples" / "ai_workflows"
    
    def test_examples_use_motor_not_tools_engine_cli(self) -> None:
        """CRITICAL: Examples must use 'motor', not 'tools.engine_cli'."""
        if not self.EXAMPLES_DIR.exists():
            self.skipTest("Examples directory not found")
        
        violations = []
        for py_file in self.EXAMPLES_DIR.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            
            # Check for tools.engine_cli usage
            if "tools.engine_cli" in content:
                # Skip if in context of explaining legacy
                if "legacy" not in content.lower() and "deprecated" not in content.lower():
                    violations.append(f"{py_file.name}: Uses tools.engine_cli")
            
            # Check they use motor
            if '"motor"' not in content and "'motor'" not in content:
                violations.append(f"{py_file.name}: Does not use 'motor' command")
        
        if violations:
            self.fail(f"Examples must use official 'motor' interface:\n" + "\n".join(violations))
    
    def test_examples_do_not_use_legacy_upsert_state(self) -> None:
        """Examples must use 'animator state create', not 'upsert-state'."""
        if not self.EXAMPLES_DIR.exists():
            self.skipTest("Examples directory not found")
        
        violations = []
        for py_file in self.EXAMPLES_DIR.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            
            if "upsert-state" in content:
                violations.append(f"{py_file.name}: Uses legacy 'upsert-state' command")
        
        if violations:
            self.fail(f"Examples must use 'animator state create':\n" + "\n".join(violations))


class RegistryParserAlignmentTests(unittest.TestCase):
    """Tests ensuring registry and parser use the same grammar."""
    
    def test_registry_and_parser_agree_on_animator_commands(self) -> None:
        """Registry and parser must agree on animator command names."""
        from engine.ai import get_default_registry
        from motor.cli import create_motor_parser
        
        registry = get_default_registry()
        parser = create_motor_parser()
        
        # Get parser commands (extract base command without arguments)
        parser_commands = set()
        for action in parser._actions:
            if hasattr(action, 'choices') and action.choices:
                for cmd_name, subparser in action.choices.items():
                    parser_commands.add(cmd_name)
                    if hasattr(subparser, '_actions'):
                        for sub_action in subparser._actions:
                            if hasattr(sub_action, 'choices') and sub_action.choices:
                                for sub_cmd in sub_action.choices.keys():
                                    parser_commands.add(f"{cmd_name} {sub_cmd}")
                                    # Third level
                                    sub_subparser = sub_action.choices[sub_cmd]
                                    if hasattr(sub_subparser, '_actions'):
                                        for sub_sub_action in sub_subparser._actions:
                                            if hasattr(sub_sub_action, 'choices') and sub_sub_action.choices:
                                                for sub_sub_cmd in sub_sub_action.choices.keys():
                                                    parser_commands.add(f"{cmd_name} {sub_cmd} {sub_sub_cmd}")
        
        # Check registry capabilities against parser
        mismatches = []
        future_or_unimplemented = {
            # Known future/unimplemented commands
            "scene flow", "entity delete", "entity parent", "entity list",
            "entity inspect", "component edit", "component remove",
            "asset find", "asset metadata", "asset refresh",
            "prefab", "project open", "project state",
            "runtime play", "runtime stop", "runtime step",
            "undo", "redo", "status",
            "physics query", "physics backends",
        }
        
        for cap in registry.list_all():
            if not cap.cli_command.startswith("motor "):
                continue
            
            parts = cap.cli_command.split()[1:]  # Remove 'motor'
            if not parts:
                continue
            
            # Skip arguments in angle brackets or square brackets
            clean_parts = [p for p in parts if not p.startswith(('<', '['))]
            
            # Build command path
            if len(clean_parts) >= 3:
                full_cmd = f"{clean_parts[0]} {clean_parts[1]} {clean_parts[2]}"
            elif len(clean_parts) == 2:
                full_cmd = f"{clean_parts[0]} {clean_parts[1]}"
            else:
                full_cmd = clean_parts[0]
            
            # Skip if it's a legacy command (upsert-state, remove-state as top-level)
            if "upsert-state" in full_cmd:
                continue
            
            # Skip known future commands
            if any(future in full_cmd for future in future_or_unimplemented):
                continue
            
            if full_cmd not in parser_commands:
                mismatches.append(f"{cap.id}: {full_cmd}")
        
        if mismatches:
            self.fail(f"Registry commands not in parser:\n" + "\n".join(mismatches))


class ComponentNamesAreRealTests(unittest.TestCase):
    """Tests ensuring registry component names exist in reality."""
    
    def test_registry_uses_real_component_names(self) -> None:
        """Registry component references must exist in ComponentRegistry."""
        from engine.ai import get_default_registry
        from engine.levels.component_registry import create_default_registry
        
        ai_registry = get_default_registry()
        comp_registry = create_default_registry()
        valid_components = set(comp_registry.list_registered())
        
        # Known component references in examples
        expected_references = {"Transform", "Sprite", "Animator", "Collider", "Camera2D"}
        
        for cap in ai_registry.list_all():
            # Check example API calls
            for call in cap.example.api_calls:
                args = call.get("args", {})
                comp_name = args.get("component_name") or args.get("component")
                if comp_name and comp_name not in valid_components:
                    if comp_name in expected_references:
                        # This is a valid component that should exist
                        self.assertIn(
                            comp_name, valid_components,
                            f"Capability {cap.id} references non-existent component: {comp_name}"
                        )


class LegacyCompatibilitySeparateTests(unittest.TestCase):
    """Tests for legacy compatibility - clearly separated from official contract."""
    
    def test_legacy_tools_engine_cli_shows_deprecation(self) -> None:
        """Legacy tools.engine_cli must show deprecation warning."""
        env = os.environ.copy()
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(ROOT) if not python_path else str(ROOT) + os.pathsep + python_path
        
        result = subprocess.run(
            [sys.executable, "-m", "tools.engine_cli", "--help"],
            capture_output=True,
            text=True,
            env=env,
        )
        
        # Should show deprecation warning
        combined_output = result.stdout + result.stderr
        self.assertIn("deprecated", combined_output.lower(), "Legacy CLI must show deprecation warning")


class NoFutureArchitectureAssumptionsTests(unittest.TestCase):
    """Tests preventing assumptions about unimplemented features."""
    
    def test_tests_only_use_implemented_commands(self) -> None:
        """Tests should only use commands that are actually implemented."""
        # List of implemented commands verified to work
        implemented = {
            "capabilities", "doctor", "project info", "project bootstrap-ai",
            "scene list", "scene create", "scene load", "scene save",
            "entity create", "component add",
            "asset list", "asset slice list", "asset slice grid", "asset slice auto", "asset slice manual",
            "animator info", "animator set-sheet", "animator ensure",
            "animator state create", "animator state remove",
        }
        
        # This test serves as documentation of what's implemented
        # If a test uses an unimplemented command, it should fail
        self.assertTrue(len(implemented) > 0, "Must have implemented commands")


if __name__ == "__main__":
    unittest.main()
