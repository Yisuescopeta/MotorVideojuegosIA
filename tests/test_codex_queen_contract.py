from __future__ import annotations

import importlib.util
import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents" / "skills" / "queen"
AGENT_DIR = ROOT / ".codex" / "agents"
RESULT_FIXTURES = ROOT / "tests" / "fixtures" / "queen_results"
EXPECTED_AGENTS = {
    "context_recon",
    "test_strategist_fast", "test_strategist", "test_strategist_deep",
    "planner_fast", "planner", "planner_deep",
    "builder_fast", "builder", "builder_deep",
    "documenter", "validator",
    "code_reviewer_fast", "code_reviewer", "code_reviewer_deep",
    "ai_friendliness", "committer",
    "godot_source_analyzer", "godot_gap_analyzer", "godot_adapter",
}
READ_ONLY = {
    "context_recon", "test_strategist_fast", "test_strategist", "test_strategist_deep",
    "planner_fast", "planner", "planner_deep", "validator",
    "code_reviewer_fast", "code_reviewer", "code_reviewer_deep",
    "ai_friendliness", "godot_source_analyzer", "godot_gap_analyzer",
}
WRITERS = EXPECTED_AGENTS - READ_ONLY
MANDATORY_SCHEMAS = {
    "context_recon", "test_strategist", "planner", "builder", "documenter",
    "validator", "code_reviewer", "ai_friendliness", "committer",
    "godot_source_analyzer", "godot_gap_analyzer", "godot_adapter",
    "queen_task_result",
}


def load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_validator_module():
    path = SKILL / "scripts" / "validate_result.py"
    spec = importlib.util.spec_from_file_location("queen_validate_result", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CodexQueenContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_toml(ROOT / ".codex" / "config.toml")
        cls.agent_configs = {
            path.stem: load_toml(path) for path in sorted(AGENT_DIR.glob("*.toml"))
        }
        cls.mapping = json.loads((SKILL / "references" / "agent_mapping.json").read_text(encoding="utf-8"))
        cls.contract = json.loads((SKILL / "references" / "queen_contract.json").read_text(encoding="utf-8"))
        cls.schemas = json.loads((SKILL / "references" / "result_schemas.json").read_text(encoding="utf-8"))
        cls.valid_results = json.loads((RESULT_FIXTURES / "valid_results.json").read_text(encoding="utf-8"))
        cls.invalid_results = json.loads((RESULT_FIXTURES / "invalid_contradictions.json").read_text(encoding="utf-8"))
        cls.validator = load_validator_module()

    def test_skill_exists_and_has_official_metadata(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: queen\n"))
        self.assertIn("description:", text)
        self.assertTrue((SKILL / "agents" / "openai.yaml").is_file())
        self.assertIn("La sesion raiz de Codex actua como Reina", text)

    def test_config_enables_native_auto_discovery_without_duplicate_registry(self) -> None:
        self.assertEqual(self.config["features"]["multi_agent"], True)
        self.assertEqual(self.config["agents"], {"max_threads": 3, "max_depth": 1})
        self.assertNotIn("queen", self.agent_configs)
        self.assertEqual(set(self.agent_configs), EXPECTED_AGENTS)

    def test_agent_toml_contracts_are_complete_and_unique(self) -> None:
        declared_names = []
        for name, config in self.agent_configs.items():
            self.assertEqual(config.get("name"), name)
            declared_names.append(config["name"])
            self.assertTrue(config.get("description", "").strip(), name)
            self.assertTrue(config.get("developer_instructions", "").strip(), name)
            self.assertNotIn("undefined", config["developer_instructions"], name)
            self.assertIn("Do not delegate", config["developer_instructions"], name)
            self.assertIn("phase completed != task completed", config["developer_instructions"], name)
            self.assertIn(f".opencode/agents/{name.replace('_', '-')}.md", config["developer_instructions"], name)
        self.assertEqual(len(declared_names), len(set(declared_names)))

    def test_agent_name_mapping_has_no_drift_and_preserves_opencode(self) -> None:
        mapping = self.mapping["agents"]
        self.assertEqual(set(mapping), EXPECTED_AGENTS)
        self.assertEqual(self.mapping["codex_root_role"], "queen")
        opencode_agents = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))["agent"]
        for codex_name, entry in mapping.items():
            self.assertEqual(entry["opencode"], codex_name.replace("_", "-"))
            self.assertIn(entry["opencode"], opencode_agents)
            self.assertTrue((ROOT / ".opencode" / "agents" / f"{entry['opencode']}.md").is_file())

    def test_sandbox_is_technical_and_scope_is_operational(self) -> None:
        for name in READ_ONLY:
            self.assertEqual(self.agent_configs[name]["sandbox_mode"], "read-only", name)
        for name in WRITERS:
            self.assertEqual(self.agent_configs[name]["sandbox_mode"], "workspace-write", name)
        for name in {"builder_fast", "builder", "builder_deep", "godot_adapter"}:
            instructions = self.agent_configs[name]["developer_instructions"]
            for term in ("allowed", "forbidden", "TEST CONTRACT", "write set"):
                self.assertIn(term, instructions, f"{name}: {term}")

    def test_models_and_reasoning_match_router_variants(self) -> None:
        fast = {"test_strategist_fast", "planner_fast", "builder_fast", "code_reviewer_fast"}
        standard = {"test_strategist", "planner", "builder", "code_reviewer"}
        deep = {"test_strategist_deep", "planner_deep", "builder_deep", "code_reviewer_deep"}
        for name in fast:
            self.assertEqual((self.agent_configs[name]["model"], self.agent_configs[name]["model_reasoning_effort"]), ("gpt-5.6-terra", "low"))
        for name in standard:
            self.assertEqual((self.agent_configs[name]["model"], self.agent_configs[name]["model_reasoning_effort"]), ("gpt-5.6", "high"))
        for name in deep:
            self.assertEqual((self.agent_configs[name]["model"], self.agent_configs[name]["model_reasoning_effort"]), ("gpt-5.6", "xhigh"))
        for name, config in self.agent_configs.items():
            self.assertNotIn("openai/", config["model"], name)
            self.assertNotRegex(config["model"], r"gpt-5\.[45](?:-mini)?$")

    def test_router_has_all_four_routes_and_escalation_guards(self) -> None:
        self.assertEqual(set(self.contract["router"]), {"simple", "normal", "complex", "critical"})
        router_text = (SKILL / "references" / "model_router.md").read_text(encoding="utf-8")
        for term in ("previous_failed_cycles", "must_fix", "validator", "test_strategist_deep", "builder_deep"):
            self.assertIn(term, router_text)

    def test_workflow_continuity_and_final_states(self) -> None:
        self.assertEqual(self.contract["max_cycles"], 5)
        self.assertEqual(set(self.contract["phase_statuses"]), {"completed", "blocked", "failed", "skipped", "not_applicable"})
        self.assertEqual(set(self.contract["task_statuses"]), {"completed", "partial", "blocked", "failed"})
        self.assertEqual(self.contract["exceptional_stop"], "planning_only")
        transitions = self.contract["automatic_transitions"]
        self.assertEqual(transitions["PLAN.approved"], "PLAN_CRITIQUE")
        self.assertEqual(transitions["REVIEW.approved"], "AI_AUDIT")
        self.assertEqual(transitions["UPDATE_PLAN.continue_next_phase"], "NEXT_PHASE")
        self.assertIn("PLAN", self.contract["forbidden_final_after"])
        self.assertIn("REVIEW", self.contract["forbidden_final_after"])
        self.assertEqual(self.contract["commit_prerequisites"], ["validator_pass", "review_approved", "ai_audit_approved_or_not_applicable"])

    def test_test_contract_and_result_schemas_are_machine_readable(self) -> None:
        self.assertTrue(MANDATORY_SCHEMAS <= set(self.schemas["agent_types"]))
        required = self.schemas["agent_types"]["test_strategist"]["required"]
        for field in ("existing_tests_authority", "tests_that_must_not_be_relaxed", "minimum_focused_commands", "verdict"):
            self.assertIn(field, required)
        self.assertEqual(self.schemas["agent_types"]["test_strategist"]["properties"]["verdict"]["enum"], ["sufficient", "insufficient", "not_applicable"])
        self.assertEqual(self.schemas["schema_version"], 2)
        permissions = self.schemas["agent_types"]["context_recon"]["properties"]["permissions_summary"]
        self.assertIn("array", permissions["type"])
        planner_step = self.schemas["agent_types"]["planner"]["properties"]["steps"]["items"]
        self.assertIn("estimated_complexity", planner_step["required"])
        review_finding = self.schemas["agent_types"]["code_reviewer"]["properties"]["findings"]["items"]
        self.assertIn("must_fix", review_finding["required"])
        ai_scores = self.schemas["agent_types"]["ai_friendliness"]["properties"]["scores"]
        self.assertEqual(set(ai_scores["required"]), {"serialization", "public_api", "documentation", "compliance"})

    def test_validator_rejects_empty_non_json_missing_and_invalid_enum(self) -> None:
        with self.assertRaises(self.validator.ContractError):
            self.validator.parse_result_text("")
        with self.assertRaises(self.validator.ContractError):
            self.validator.parse_result_text("not-json")
        with self.assertRaises(self.validator.ContractError):
            self.validator.validate_result("builder", {})
        invalid = self.valid_builder_result()
        invalid["status"] = "ok"
        with self.assertRaises(self.validator.ContractError):
            self.validator.validate_result("builder", invalid)

    def test_validator_accepts_valid_result_and_alias(self) -> None:
        result = self.valid_builder_result()
        self.validator.validate_result("builder", result)
        self.validator.validate_result("builder-deep", result)

    def test_validator_accepts_realistic_fixture_for_every_schema(self) -> None:
        self.assertEqual(set(self.valid_results), set(self.schemas["agent_types"]))
        for agent_type, result in self.valid_results.items():
            with self.subTest(agent_type=agent_type):
                self.validator.validate_result(agent_type, result)

    def test_validator_rejects_semantic_contradiction_fixtures(self) -> None:
        self.assertGreaterEqual(len(self.invalid_results), len(MANDATORY_SCHEMAS))
        for fixture in self.invalid_results:
            with self.subTest(name=fixture["name"]):
                with self.assertRaises(self.validator.ContractError):
                    self.validator.validate_result(fixture["agent_type"], fixture["result"])

    def test_destructive_commands_are_explicitly_forbidden_for_writers(self) -> None:
        destructive = (
            "git reset --hard", "git clean -fd", "git checkout -- .", "git restore .",
            "rm -rf", "del /s", "rmdir /s", "git push --force",
        )
        for name in WRITERS:
            instructions = self.agent_configs[name]["developer_instructions"]
            for command in destructive:
                self.assertIn(command, instructions, f"{name}: {command}")

    def test_docs_explain_parent_runtime_can_override_child_sandbox(self) -> None:
        for path in (ROOT / "docs" / "agents.md", ROOT / "docs" / "queen_engine_workflow.md"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("parent/root runtime", text, str(path))
            self.assertIn("effective child sandbox", text, str(path))

    def test_review_scratch_cleanup_preserves_required_reports(self) -> None:
        sdd = ROOT / ".superpowers" / "sdd"
        self.assertFalse((sdd / "make-review-package.ps1").exists())
        self.assertTrue((sdd / "task-1-brief.md").is_file())
        self.assertTrue((sdd / "task-1-report.md").is_file())

    def test_godot_agents_load_specialized_skill(self) -> None:
        self.assertTrue((ROOT / ".agents" / "skills" / "godot-feature-adapter" / "SKILL.md").is_file())
        for name in ("godot_source_analyzer", "godot_gap_analyzer", "godot_adapter"):
            self.assertIn(".agents/skills/godot-feature-adapter/SKILL.md", self.agent_configs[name]["developer_instructions"])

    @staticmethod
    def valid_builder_result() -> dict:
        return {
            "builder_id": "builder-test",
            "status": "completed",
            "phase_status": "completed",
            "files_changed": ["example.txt"],
            "tests_added_or_modified": [],
            "tests_deliberately_not_changed": [],
            "commands_run": ["test"],
            "write_scope_violations": [],
            "risks": [],
        }

if __name__ == "__main__":
    unittest.main()
