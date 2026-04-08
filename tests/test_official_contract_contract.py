"""
tests/test_official_contract_contract.py - Official contract safety net

Guarantees for the AI-facing interface:
1. doctor is strictly read-only (passes read_only=True to EngineAPI)
2. status field flows end-to-end: registry → capabilities CLI → bootstrap → doctor
3. Schema v3: counts, implemented/planned split are consistent everywhere
4. Bootstrap generates from registry status, not from hardcoded lists
5. Planned capabilities are NOT executable via the parser
6. Implemented capabilities have working parser commands

These tests are the FIRST LINE OF DEFENSE against regressions.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engine.ai import get_default_registry
from motor.cli import create_motor_parser

ROOT = Path(__file__).resolve().parents[1]


class _ContractTestMixin:
    """Shared setup for subprocess-based contract tests."""

    def _run_motor(self, *args: str, project: Path | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
        """Run motor CLI command. Uses project path if given, else cwd."""
        cmd = [sys.executable, "-m", "motor"] + list(args)
        env = os.environ.copy()
        pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(ROOT) if not pp else str(ROOT) + os.pathsep + pp
        target_cwd = str(project) if project else (str(cwd) if cwd else str(project))
        return subprocess.run(
            cmd, capture_output=True, text=True, env=env,
            cwd=str(project) if project else (cwd or ROOT)
        )

    def _parse_json_output(self, stdout: str) -> dict:
        """Extract JSON from stdout (strips leading non-JSON text)."""
        out = stdout
        if "{" in out:
            out = out[out.index("{"):]
        return json.loads(out)

    def _create_test_project(self, workspace: Path, name: str = "TestProject") -> Path:
        """Create a minimal valid test project."""
        project = workspace / name
        project.mkdir(parents=True, exist_ok=True)
        (project / "project.json").write_text(
            json.dumps({
                "name": name,
                "version": 2,
                "engine_version": "2026.03",
                "template": "empty",
                "paths": {
                    "assets": "assets", "levels": "levels",
                    "prefabs": "prefabs", "scripts": "scripts",
                    "settings": "settings", "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }),
            encoding="utf-8",
        )
        for d in ["assets", "levels", "scripts", "settings", ".motor"]:
            (project / d).mkdir(parents=True, exist_ok=True)
        return project


# =============================================================================
# Contract 1: doctor is strictly read-only
# =============================================================================

class DoctorReadOnlyContractTests(_ContractTestMixin, unittest.TestCase):
    """Contract: doctor must never mutate project or global state."""

    def test_doctor_passes_read_only_to_engine_api(self) -> None:
        """doctor must pass read_only=True to EngineAPI so no global storage is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Ensure global storage does NOT exist before
            home = Path.home()
            global_dir = home / ".motorvideojuegosia"
            recents = global_dir / "recent_projects.json"
            global_existed_before = global_dir.exists()
            recents_existed_before = recents.exists()

            # Run doctor
            result = self._run_motor("doctor", "--project", str(project), "--json", project=project)
            self.assertEqual(result.returncode, 0, f"doctor should succeed: {result.stderr}")

            # Verify global storage was NOT created
            if not global_existed_before:
                self.assertFalse(
                    global_dir.exists(),
                    "doctor must NOT create ~/.motorvideojuegosia/ (EngineAPI must use read_only=True)"
                )
            if not recents_existed_before:
                self.assertFalse(
                    recents.exists(),
                    "doctor must NOT create recent_projects.json"
                )

    def test_doctor_does_not_create_project_state_dir(self) -> None:
        """doctor must not create .motor/ editor state directory for clean project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))
            motor_dir = project / ".motor"

            # .motor may exist but editor_state.json should not be created
            motor_dir.mkdir(exist_ok=True)

            # Run doctor
            result = self._run_motor("doctor", "--project", str(project), "--json", project=project)
            self.assertEqual(result.returncode, 0)

            # editor_state.json should NOT be created by doctor
            editor_state = motor_dir / "editor_state.json"
            self.assertFalse(
                editor_state.exists(),
                "doctor must NOT create .motor/editor_state.json (read-only check)"
            )

    def test_doctor_is_idempotent_across_clean_runs(self) -> None:
        """Multiple doctor runs on clean project should produce identical results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Run 1
            r1 = self._run_motor("doctor", "--project", str(project), "--json", project=project)
            self.assertEqual(r1.returncode, 0)
            d1 = self._parse_json_output(r1.stdout)

            # Run 2, 3, 4
            results = []
            for _ in range(3):
                r = self._run_motor("doctor", "--project", str(project), "--json", project=project)
                self.assertEqual(r.returncode, 0)
                results.append(self._parse_json_output(r.stdout))

            # status and checks should be identical
            self.assertEqual(d1.get("data", {}).get("status"),
                           results[0].get("data", {}).get("status"))
            self.assertEqual(d1.get("data", {}).get("issues"),
                           results[0].get("data", {}).get("issues"))
            self.assertEqual(d1.get("data", {}).get("warnings"),
                           results[0].get("data", {}).get("warnings"))

    def test_doctor_does_not_create_levels_dir_if_missing(self) -> None:
        """doctor must not auto-create directories that are missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Remove levels dir if it exists
            levels_dir = project / "levels"
            if levels_dir.exists():
                import shutil
                shutil.rmtree(levels_dir)

            # Run doctor
            result = self._run_motor("doctor", "--project", str(project), "--json", project=project)
            self.assertEqual(result.returncode, 0)

            # levels/ should NOT be created
            self.assertFalse(
                levels_dir.exists(),
                "doctor must NOT create missing directories"
            )


# =============================================================================
# Contract 2: status field flows end-to-end
# =============================================================================

class StatusEndToEndContractTests(_ContractTestMixin, unittest.TestCase):
    """Contract: status field is present and correct in every layer."""

    def test_capabilities_cli_includes_status(self) -> None:
        """motor capabilities --json must include status for EVERY capability."""
        result = self._run_motor("capabilities", "--json")
        self.assertEqual(result.returncode, 0, f"capabilities should work: {result.stderr}")

        data = self._parse_json_output(result.stdout)
        caps = data.get("data", {}).get("capabilities", [])
        self.assertGreater(len(caps), 0, "Should have capabilities")

        for cap in caps:
            with self.subTest(cap=cap.get("id", "?")):
                self.assertIn(
                    "status", cap,
                    f"Capability {cap.get('id')} missing 'status' field in CLI output"
                )
                self.assertIn(
                    cap["status"], {"implemented", "planned", "deprecated"},
                    f"Invalid status value: {cap['status']}"
                )

    def test_capabilities_cli_status_matches_registry(self) -> None:
        """motor capabilities --json status must match the registry."""
        registry = get_default_registry()

        result = self._run_motor("capabilities", "--json")
        data = self._parse_json_output(result.stdout)
        cli_caps = {c["id"]: c["status"] for c in data.get("data", {}).get("capabilities", [])}

        mismatches = []
        for cap in registry.list_all():
            cli_status = cli_caps.get(cap.id)
            if cli_status is None:
                mismatches.append(f"{cap.id}: not in CLI output")
            elif cli_status != cap.status:
                mismatches.append(f"{cap.id}: CLI={cli_status} registry={cap.status}")

        self.assertEqual(
            len(mismatches), 0,
            f"Status mismatch between registry and CLI:\n" + "\n".join(mismatches)
        )

    def test_bootstrap_respects_registry_status(self) -> None:
        """Bootstrap must generate capabilities with status matching registry exactly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Generate bootstrap
            result = self._run_motor("project", "bootstrap-ai", "--project", str(project), project=project)
            self.assertEqual(result.returncode, 0, f"bootstrap should work: {result.stderr}")

            motor_ai = json.loads((project / "motor_ai.json").read_text(encoding="utf-8"))
            bootstrap_impl = {c["id"]: c["status"] for c in motor_ai.get("implemented_capabilities", [])}
            bootstrap_plan = {c["id"]: c["status"] for c in motor_ai.get("planned_capabilities", [])}
            bootstrap_all = {**bootstrap_impl, **bootstrap_plan}

            registry = get_default_registry()
            mismatches = []
            for cap in registry.list_all():
                bs_status = bootstrap_all.get(cap.id)
                if bs_status is None:
                    mismatches.append(f"{cap.id}: missing from bootstrap output")
                elif bs_status != cap.status:
                    mismatches.append(f"{cap.id}: bootstrap={bs_status} registry={cap.status}")

            self.assertEqual(
                len(mismatches), 0,
                f"Status mismatch between registry and bootstrap:\n" + "\n".join(mismatches)
            )

    def test_doctor_reads_status_from_bootstrap(self) -> None:
        """doctor must correctly count implemented/planned from bootstrap file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Generate bootstrap
            self._run_motor("project", "bootstrap-ai", "--project", str(project), project=project)

            # Read what bootstrap generated
            motor_ai = json.loads((project / "motor_ai.json").read_text(encoding="utf-8"))
            expected_impl = len(motor_ai.get("implemented_capabilities", []))
            expected_plan = len(motor_ai.get("planned_capabilities", []))

            # Run doctor
            result = self._run_motor("doctor", "--project", str(project), "--json", project=project)
            self.assertEqual(result.returncode, 0)
            data = self._parse_json_output(result.stdout)
            checks = data.get("data", {}).get("checks", {})

            self.assertEqual(
                checks.get("motor_ai_implemented_count"), expected_impl,
                "Doctor must report implemented count matching bootstrap"
            )
            self.assertEqual(
                checks.get("motor_ai_planned_count"), expected_plan,
                "Doctor must report planned count matching bootstrap"
            )


# =============================================================================
# Contract 3: schema v3 consistency
# =============================================================================

class SchemaV3ContractTests(_ContractTestMixin, unittest.TestCase):
    """Contract: schema v3 is self-consistent everywhere."""

    def test_bootstrap_counts_match_list_lengths(self) -> None:
        """capability_counts must equal actual list lengths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))
            self._run_motor("project", "bootstrap-ai", "--project", str(project), project=project)

            motor_ai = json.loads((project / "motor_ai.json").read_text(encoding="utf-8"))
            impl_list = motor_ai.get("implemented_capabilities", [])
            plan_list = motor_ai.get("planned_capabilities", [])
            counts = motor_ai.get("capability_counts", {})

            self.assertEqual(counts.get("implemented"), len(impl_list),
                           "capability_counts.implemented must match list length")
            self.assertEqual(counts.get("planned"), len(plan_list),
                           "capability_counts.planned must match list length")
            self.assertEqual(
                counts.get("total"), counts.get("implemented", 0) + counts.get("planned", 0),
                "capability_counts.total must equal implemented + planned"
            )

    def test_doctor_counts_match_schema_v3(self) -> None:
        """doctor checks must match schema v3 structure exactly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))
            self._run_motor("project", "bootstrap-ai", "--project", str(project), project=project)

            motor_ai = json.loads((project / "motor_ai.json").read_text(encoding="utf-8"))
            impl = len(motor_ai.get("implemented_capabilities", []))
            plan = len(motor_ai.get("planned_capabilities", []))
            total = impl + plan

            result = self._run_motor("doctor", "--project", str(project), "--json", project=project)
            data = self._parse_json_output(result.stdout)
            checks = data.get("data", {}).get("checks", {})

            self.assertEqual(checks.get("motor_ai_capabilities_count"), total,
                           "Doctor total count must match schema v3")
            self.assertEqual(checks.get("motor_ai_implemented_count"), impl,
                           "Doctor implemented count must match schema v3")
            self.assertEqual(checks.get("motor_ai_planned_count"), plan,
                           "Doctor planned count must match schema v3")

    def test_no_duplicate_capability_ids_in_bootstrap(self) -> None:
        """Bootstrap must not produce duplicate capability IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))
            self._run_motor("project", "bootstrap-ai", "--project", str(project), project=project)

            motor_ai = json.loads((project / "motor_ai.json").read_text(encoding="utf-8"))

            seen = set()
            duplicates = []
            for c in motor_ai.get("implemented_capabilities", []):
                if c["id"] in seen:
                    duplicates.append(c["id"])
                seen.add(c["id"])
            for c in motor_ai.get("planned_capabilities", []):
                if c["id"] in seen:
                    duplicates.append(c["id"])
                seen.add(c["id"])

            self.assertEqual(len(duplicates), 0, f"Duplicate IDs in bootstrap: {duplicates}")

    def test_bootstrap_schema_version_is_3(self) -> None:
        """Bootstrap must generate schema_version = 3."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))
            self._run_motor("project", "bootstrap-ai", "--project", str(project), project=project)

            motor_ai = json.loads((project / "motor_ai.json").read_text(encoding="utf-8"))
            self.assertEqual(motor_ai.get("schema_version"), 3,
                           "Bootstrap must generate schema_version 3")
            self.assertIn("implemented_capabilities", motor_ai)
            self.assertIn("planned_capabilities", motor_ai)
            self.assertIn("capability_counts", motor_ai)


# =============================================================================
# Contract 4: planned capabilities are NOT executable
# =============================================================================

class PlannedNotExecutableContractTests(unittest.TestCase):
    """Contract: planned capabilities must NOT be valid executable commands."""

    def test_planned_capabilities_not_executable(self) -> None:
        """No planned capability should have a working parser command."""
        registry = get_default_registry()
        parser = create_motor_parser()

        # Get ALL parser commands (up to 3 levels deep)
        parser_commands = set()
        for action in parser._actions:
            if hasattr(action, 'choices') and action.choices:
                for cmd_name, subparser in action.choices.items():
                    parser_commands.add(cmd_name)
                    if hasattr(subparser, '_actions'):
                        for sa in subparser._actions:
                            if hasattr(sa, 'choices') and sa.choices:
                                for sub_cmd, sub_sp in sa.choices.items():
                                    parser_commands.add(f"{cmd_name} {sub_cmd}")
                                    if hasattr(sub_sp, '_actions'):
                                        for ssa in sub_sp._actions:
                                            if hasattr(ssa, 'choices') and ssa.choices:
                                                for ss_cmd in ssa.choices.keys():
                                                    parser_commands.add(f"{cmd_name} {sub_cmd} {ss_cmd}")

        violations = []
        for cap in registry.list_planned():
            if not cap.cli_command.startswith("motor "):
                continue

            # Extract clean command parts (strip <args> and [optional])
            parts = cap.cli_command.split()[1:]
            clean = [p for p in parts if not p.startswith(('<', '['))]

            if not clean:
                continue

            # Build full command path
            if len(clean) >= 3:
                full = f"{clean[0]} {clean[1]} {clean[2]}"
            elif len(clean) == 2:
                full = f"{clean[0]} {clean[1]}"
            else:
                full = clean[0]

            if full in parser_commands:
                violations.append(
                    f"{cap.id} ({cap.cli_command}): is 'planned' but '{full}' exists in parser"
                )

        self.assertEqual(
            len(violations), 0,
            "Planned capabilities must NOT be executable. "
            "If the command works, mark the capability as 'implemented':\n" +
            "\n".join(f"  - {v}" for v in violations)
        )


# =============================================================================
# Contract 5: implemented capabilities have working parser commands
# =============================================================================

class ImplementedHaveParserContractTests(unittest.TestCase):
    """Contract: every implemented capability has a parser command."""

    def test_implemented_have_parser(self) -> None:
        """Every implemented capability must have a corresponding parser command."""
        registry = get_default_registry()
        parser = create_motor_parser()

        parser_commands = set()
        for action in parser._actions:
            if hasattr(action, 'choices') and action.choices:
                for cmd_name, subparser in action.choices.items():
                    parser_commands.add(cmd_name)
                    if hasattr(subparser, '_actions'):
                        for sa in subparser._actions:
                            if hasattr(sa, 'choices') and sa.choices:
                                for sub_cmd, sub_sp in sa.choices.items():
                                    parser_commands.add(f"{cmd_name} {sub_cmd}")
                                    if hasattr(sub_sp, '_actions'):
                                        for ssa in sub_sp._actions:
                                            if hasattr(ssa, 'choices') and ssa.choices:
                                                for ss_cmd in ssa.choices.keys():
                                                    parser_commands.add(f"{cmd_name} {sub_cmd} {ss_cmd}")

        missing = []
        for cap in registry.list_implemented():
            if not cap.cli_command.startswith("motor "):
                continue

            parts = cap.cli_command.split()[1:]
            clean = [p for p in parts if not p.startswith(('<', '['))]

            if not clean:
                continue

            found = False
            if len(clean) >= 3:
                if f"{clean[0]} {clean[1]} {clean[2]}" in parser_commands:
                    found = True
            if not found and len(clean) >= 2:
                if f"{clean[0]} {clean[1]}" in parser_commands:
                    found = True
            if not found:
                if clean[0] in parser_commands:
                    found = True

            if not found:
                missing.append(f"{cap.id}: '{cap.cli_command}' has no parser match")

        self.assertEqual(
            len(missing), 0,
            "Implemented capabilities must have parser commands:\n" +
            "\n".join(f"  - {m}" for m in missing)
        )


# =============================================================================
# Contract 6: bootstrap respects registry exactly (no hardcoded lists)
# =============================================================================

class BootstrapFromRegistryContractTests(_ContractTestMixin, unittest.TestCase):
    """Contract: bootstrap generates from registry, not from hardcoded assumptions."""

    def test_bootstrap_implemented_equals_registry_implemented(self) -> None:
        """Number of implemented capabilities in bootstrap must equal registry count."""
        registry = get_default_registry()
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))
            self._run_motor("project", "bootstrap-ai", "--project", str(project), project=project)

            motor_ai = json.loads((project / "motor_ai.json").read_text(encoding="utf-8"))
            impl_ids = {c["id"] for c in motor_ai.get("implemented_capabilities", [])}

            registry_impl = {cap.id for cap in registry.list_implemented()}
            extra_in_bootstrap = impl_ids - registry_impl
            missing_from_bootstrap = registry_impl - impl_ids

            self.assertEqual(
                len(extra_in_bootstrap), 0,
                f"Bootstrap has capabilities not in registry: {extra_in_bootstrap}"
            )
            self.assertEqual(
                len(missing_from_bootstrap), 0,
                f"Bootstrap is missing capabilities from registry: {missing_from_bootstrap}"
            )

    def test_bootstrap_planned_equals_registry_planned(self) -> None:
        """Number of planned capabilities in bootstrap must equal registry count."""
        registry = get_default_registry()
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))
            self._run_motor("project", "bootstrap-ai", "--project", str(project), project=project)

            motor_ai = json.loads((project / "motor_ai.json").read_text(encoding="utf-8"))
            plan_ids = {c["id"] for c in motor_ai.get("planned_capabilities", [])}

            registry_plan = {cap.id for cap in registry.list_planned()}
            extra = plan_ids - registry_plan
            missing = registry_plan - plan_ids

            self.assertEqual(len(extra), 0, f"Bootstrap has extra planned: {extra}")
            self.assertEqual(len(missing), 0, f"Bootstrap missing planned: {missing}")

    def test_capability_counts_reflect_registry(self) -> None:
        """capability_counts in schema v3 must match registry."""
        registry = get_default_registry()
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))
            self._run_motor("project", "bootstrap-ai", "--project", str(project), project=project)

            motor_ai = json.loads((project / "motor_ai.json").read_text(encoding="utf-8"))
            counts = motor_ai.get("capability_counts", {})

            self.assertEqual(
                counts.get("implemented"), len(list(registry.list_implemented())),
                "capability_counts.implemented must match registry"
            )
            self.assertEqual(
                counts.get("planned"), len(list(registry.list_planned())),
                "capability_counts.planned must match registry"
            )


# =============================================================================
# Contract 7: legacy compatibility is read-only
# =============================================================================

class LegacyCompatibilityContractTests(_ContractTestMixin, unittest.TestCase):
    """Contract: legacy interfaces are clearly marked and separated from official contract."""

    def test_no_implemented_capability_uses_legacy_command(self) -> None:
        """No implemented capability may reference a legacy command."""
        registry = get_default_registry()
        legacy_commands = {"upsert-state", "remove-state"}

        violations = []
        for cap in registry.list_implemented():
            for legacy in legacy_commands:
                if legacy in cap.cli_command:
                    violations.append(f"{cap.id}: uses legacy command '{legacy}'")

        self.assertEqual(
            len(violations), 0,
            "Implemented capabilities must not use legacy commands:\n" +
            "\n".join(f"  - {v}" for v in violations)
        )

    def test_doctor_accepts_legacy_schema(self) -> None:
        """doctor must gracefully handle legacy v1/v2 schemas (read-only compat)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self._create_test_project(Path(tmpdir))

            # Write legacy v1 schema
            legacy = {
                "schema_version": 1,
                "engine": {"name": "Motor", "version": "1.0"},
                "capabilities": {
                    "capabilities": [
                        {"id": "scene:create", "summary": "Create scene"},
                    ]
                },
            }
            (project / "motor_ai.json").write_text(json.dumps(legacy), encoding="utf-8")
            (project / "START_HERE_AI.md").write_text("# Test\n", encoding="utf-8")

            result = self._run_motor("doctor", "--project", str(project), "--json", project=project)
            self.assertEqual(result.returncode, 0, "doctor must accept legacy schema")

            data = self._parse_json_output(result.stdout)
            checks = data.get("data", {}).get("checks", {})
            self.assertEqual(checks.get("motor_ai_schema_version"), 1,
                           "doctor should detect legacy schema_version 1")


if __name__ == "__main__":
    unittest.main()
