from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path

import tools.queen_state as queen_state

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / ".opencode" / "agents"
WORKFLOW_DOC = ROOT / "docs" / "queen_engine_workflow.md"
PERMISSION_SANDBOX = ROOT / "tests" / "fixtures" / "queen_permission_smoke" / "permission_sandbox.md"
NORMAL_CYCLE = (
    "RECON -> TEST CONTRACT -> PLAN -> CRITICA DEL PLAN -> IMPLEMENTAR -> "
    "DOCUMENTAR -> VALIDAR -> REVIEW -> AI AUDIT -> COMMIT -> REPORTE"
)
LONG_CYCLE = (
    "LOAD PLAN -> PLAN SYNC -> TEST CONTRACT -> IMPLEMENTAR FASE -> DOCUMENTAR -> "
    "VALIDAR -> REVIEW -> AI AUDIT -> UPDATE PLAN -> NEXT PHASE | COMMIT | BLOCK"
)
GOVERNANCE_COMMAND = (
    "py -m unittest tests.test_repository_governance tests.test_motor_cli_contract "
    "tests.test_start_here_ai_coherence -v"
)
TEST_CONTRACT_FIELDS = [
    "test_contract_id",
    "task_type",
    "subsystems",
    "existing_tests_authority",
    "new_or_modified_tests_required",
    "tests_that_must_not_be_relaxed",
    "minimum_focused_commands",
    "recommended_regression_commands",
    "manual_smoke_required",
    "acceptance_criteria",
    "risks",
    "auxiliary_inspection_commands_run",
    "auxiliary_inspection_results",
    "verdict",
    "verdict_reason",
]
CONTEXT_RECON_FIELDS = [
    "recon_id",
    "status",
    "files_reviewed",
    "subsystems",
    "expected_agents",
    "read_only_agents",
    "write_agents",
    "permissions_summary",
    "allowed_files",
    "forbidden_files",
    "relevant_tests",
    "relevant_docs",
    "risks",
    "blocked_reason",
]
QUEEN_FLOW_AGENTS = [
    "queen",
    "context-recon",
    "test-strategist",
    "test-strategist-fast",
    "test-strategist-deep",
    "planner",
    "planner-fast",
    "planner-deep",
    "builder",
    "builder-fast",
    "builder-deep",
    "validator",
    "documenter",
    "code-reviewer",
    "code-reviewer-fast",
    "code-reviewer-deep",
    "ai-friendliness",
    "committer",
]
EXPECTED_QUEEN_FLOW_MODELS = {
    "queen": "openai/gpt-5.5",
    "context-recon": "openai/gpt-5.4-mini",
    "validator": "openai/gpt-5.4-mini",
    "documenter": "openai/gpt-5.4-mini",
    "committer": "openai/gpt-5.4-mini",
    "ai-friendliness": "openai/gpt-5.4",
    "test-strategist": "openai/gpt-5.5",
    "test-strategist-fast": "openai/gpt-5.4-mini",
    "test-strategist-deep": "openai/gpt-5.5",
    "planner": "openai/gpt-5.5",
    "planner-fast": "openai/gpt-5.4-mini",
    "planner-deep": "openai/gpt-5.5",
    "builder": "openai/gpt-5.4",
    "builder-fast": "openai/gpt-5.4-mini",
    "builder-deep": "openai/gpt-5.5",
    "code-reviewer": "openai/gpt-5.5",
    "code-reviewer-fast": "openai/gpt-5.4",
    "code-reviewer-deep": "openai/gpt-5.5",
}
QUEEN_FLOW_PROMPT_FILES = {
    "queen": AGENTS_DIR / "queen.md",
    "context-recon": AGENTS_DIR / "context-recon.md",
    "test-strategist": AGENTS_DIR / "test-strategist.md",
    "test-strategist-fast": AGENTS_DIR / "test-strategist-fast.md",
    "test-strategist-deep": AGENTS_DIR / "test-strategist-deep.md",
    "planner": AGENTS_DIR / "planner.md",
    "planner-fast": AGENTS_DIR / "planner-fast.md",
    "planner-deep": AGENTS_DIR / "planner-deep.md",
    "builder": AGENTS_DIR / "builder.md",
    "builder-fast": AGENTS_DIR / "builder-fast.md",
    "builder-deep": AGENTS_DIR / "builder-deep.md",
    "validator": AGENTS_DIR / "validator.md",
    "documenter": AGENTS_DIR / "documenter.md",
    "code-reviewer": AGENTS_DIR / "code-reviewer.md",
    "code-reviewer-fast": AGENTS_DIR / "code-reviewer-fast.md",
    "code-reviewer-deep": AGENTS_DIR / "code-reviewer-deep.md",
    "ai-friendliness": AGENTS_DIR / "ai-friendliness.md",
    "committer": AGENTS_DIR / "committer.md",
    "queen-command": ROOT / ".opencode" / "commands" / "queen.md",
}
EXPECTED_SUBAGENTS = {
    "ai-friendliness",
    "builder",
    "code-reviewer",
    "committer",
    "context-recon",
    "documenter",
    "godot-adapter",
    "godot-gap-analyzer",
    "godot-source-analyzer",
    "planner",
    "planner-fast",
    "planner-deep",
    "test-strategist",
    "test-strategist-fast",
    "test-strategist-deep",
    "validator",
    "builder-fast",
    "builder-deep",
    "code-reviewer-fast",
    "code-reviewer-deep",
}
QUEEN_ROUTED_VARIANTS = {
    "test-strategist": ["test-strategist-fast", "test-strategist-deep"],
    "planner": ["planner-fast", "planner-deep"],
    "builder": ["builder-fast", "builder-deep"],
    "code-reviewer": ["code-reviewer-fast", "code-reviewer-deep"],
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(text: str) -> str:
    match = re.match(r"---\n(?P<body>[\s\S]*?)\n---", text)
    if not match:
        return ""
    return match.group("body")


def cycle_index(cycle: str, phase: str) -> int:
    return [part.strip() for part in cycle.split("->")].index(phase)


class QueenAgentContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(read_text(ROOT / "opencode.json"))
        self.agent_config = self.config["agent"]
        self.queen_prompt = read_text(AGENTS_DIR / "queen.md")

    def test_agents_referenced_by_queen_exist_in_opencode_config(self) -> None:
        configured = set(self.agent_config)
        referenced = {
            name
            for name in configured
            if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", self.queen_prompt)
        }
        self.assertIn("context-recon", referenced)
        self.assertIn("test-strategist", referenced)
        self.assertIn("committer", referenced)
        self.assertTrue(referenced <= configured)

    def test_each_configured_agent_has_prompt_file(self) -> None:
        missing = sorted(name for name in self.agent_config if not (AGENTS_DIR / f"{name}.md").exists())
        self.assertEqual(missing, [])

    def test_context_recon_path_and_permissions_are_read_only(self) -> None:
        self.assertTrue((AGENTS_DIR / "context-recon.md").exists())
        self.assertFalse((ROOT / ".opencode" / "agent" / "context-recon.md").exists())

        permissions = self.agent_config["context-recon"]["permission"]
        for key in ("read", "glob", "grep"):
            self.assertEqual(permissions.get(key), "allow", msg=key)
        for key in ("bash", "edit", "write", "webfetch", "websearch", "task", "todowrite"):
            self.assertEqual(permissions.get(key), "deny", msg=key)

        prompt = read_text(AGENTS_DIR / "context-recon.md")
        for line in ("read: allow", "glob: allow", "grep: allow"):
            self.assertIn(line, prompt)
        for line in (
            "bash: deny",
            "edit: deny",
            "write: deny",
            "webfetch: deny",
            "websearch: deny",
            "task: deny",
            "todowrite: deny",
        ):
            self.assertIn(line, prompt)

    def test_context_recon_has_verifiable_output_contract(self) -> None:
        prompt = read_text(AGENTS_DIR / "context-recon.md")
        self.assertIn("Return exactly one JSON object", prompt)
        for field in CONTEXT_RECON_FIELDS:
            self.assertIn(f'"{field}"', prompt)
        self.assertIn('"status": "completed|partial|blocked|failed"', prompt)
        self.assertIn("Empty output is invalid", prompt)
        self.assertIn("Non-parseable output is invalid", prompt)
        self.assertIn("If you cannot inspect files", prompt)
        self.assertIn("Always return visible output to Queen", prompt)
        self.assertIn("Do not run bash", prompt)
        self.assertIn("Do not delegate", prompt)

    def test_queen_has_no_mutating_permissions_and_only_safe_git_bash(self) -> None:
        permissions = self.agent_config["queen"]["permission"]
        self.assertEqual(permissions.get("edit"), "deny")
        self.assertEqual(permissions.get("write"), "deny")

        bash = permissions.get("bash")
        self.assertIsInstance(bash, dict)
        self.assertEqual(bash.get("*"), "deny")
        for command in ("git diff *", "git status *", "git log *"):
            self.assertEqual(bash.get(command), "allow")
        for command in ("py -m unittest *", "py -m ruff check *", "py -m mypy *", "py -m motor *"):
            self.assertNotEqual(bash.get(command), "allow")

        self.assertIn("edit: deny", self.queen_prompt)
        self.assertIn("write: deny", self.queen_prompt)
        self.assertIsNone(re.search(r"^\s+edit:\s+allow\s*$", self.queen_prompt, re.MULTILINE))
        self.assertIsNone(re.search(r"^\s+write:\s+allow\s*$", self.queen_prompt, re.MULTILINE))

    def test_writer_agents_do_not_have_free_bash(self) -> None:
        for agent_name in ("builder", "godot-adapter"):
            permissions = self.agent_config[agent_name]["permission"]
            bash = permissions.get("bash")
            self.assertIsInstance(bash, dict, msg=agent_name)
            self.assertEqual(bash.get("*"), "deny", msg=agent_name)
            self.assertNotEqual(bash, "allow", msg=agent_name)
            for command in (
                "py -m unittest *",
                "py -m ruff check *",
                "py -m mypy *",
                "py -m motor *",
                "git diff *",
                "git status *",
                "git log *",
            ):
                self.assertEqual(bash.get(command), "allow", msg=f"{agent_name}: {command}")

            prompt = read_text(AGENTS_DIR / f"{agent_name}.md")
            self.assertNotIn("bash: allow", prompt)

    def test_normal_cycle_has_test_contract_and_docs_before_validation(self) -> None:
        sources = {
            "AGENTS.md": read_text(ROOT / "AGENTS.md"),
            "queen.md": self.queen_prompt,
            "command": read_text(ROOT / ".opencode" / "commands" / "queen.md"),
            "opencode.json": read_text(ROOT / "opencode.json"),
        }
        steps = [part.strip() for part in NORMAL_CYCLE.split("->")]
        for name, source in sources.items():
            self.assertIn(NORMAL_CYCLE, source, msg=name)
            self.assertLess(steps.index("RECON"), steps.index("TEST CONTRACT"), msg=name)
            self.assertLess(steps.index("TEST CONTRACT"), steps.index("PLAN"), msg=name)
            self.assertLess(steps.index("PLAN"), steps.index("IMPLEMENTAR"), msg=name)
            self.assertLess(steps.index("DOCUMENTAR"), steps.index("VALIDAR"), msg=name)
            self.assertLess(steps.index("VALIDAR"), steps.index("REVIEW"), msg=name)
            self.assertLess(steps.index("AI AUDIT"), steps.index("COMMIT"), msg=name)

    def test_long_task_cycle_records_ai_audit_before_advancing_or_closing(self) -> None:
        sources = {
            "queen.md": self.queen_prompt,
            "command": read_text(ROOT / ".opencode" / "commands" / "queen.md"),
            "queen_long_task_mode.md": read_text(ROOT / "docs" / "queen_long_task_mode.md"),
        }
        for name, source in sources.items():
            self.assertIn(LONG_CYCLE, source, msg=name)
            self.assertLess(source.index("TEST CONTRACT"), source.index("IMPLEMENTAR FASE"), msg=name)
            self.assertLess(source.index("DOCUMENTAR"), source.index("VALIDAR"), msg=name)
            self.assertLess(source.index("AI AUDIT"), source.index("UPDATE PLAN"), msg=name)
            self.assertIn("AI AUDIT", source[source.index("UPDATE PLAN") :], msg=name)

    def test_test_strategist_agent_exists_is_read_only_and_documents_schema(self) -> None:
        prompt_path = AGENTS_DIR / "test-strategist.md"
        self.assertTrue(prompt_path.exists(), "test-strategist.md prompt file must exist")
        self.assertIn("test-strategist", self.agent_config)

        config = self.agent_config["test-strategist"]
        self.assertEqual(config.get("mode"), "subagent")
        self.assertLessEqual(config.get("temperature", 1.0), 0.2)

        permissions = config["permission"]
        for key in ("read", "glob", "grep"):
            self.assertEqual(permissions.get(key), "allow", msg=key)
        for key in ("edit", "write", "task", "todowrite", "question", "webfetch", "websearch", "skill"):
            self.assertEqual(permissions.get(key), "deny", msg=key)

        bash = permissions.get("bash")
        self.assertIsInstance(bash, dict)
        self.assertEqual(bash.get("*"), "deny")
        for command in ("py -m unittest *", "git diff *", "git status *", "git log *"):
            self.assertEqual(bash.get(command), "allow")

        prompt = read_text(prompt_path)
        for field in TEST_CONTRACT_FIELDS:
            self.assertIn(f'"{field}"', prompt)
        self.assertIn("inspection only", prompt.lower())
        self.assertIn("not final validation", prompt.lower())
        self.assertIn("sufficient|insufficient|not_applicable", prompt)
        self.assertIn("verdict_reason", prompt)
        self.assertRegex(prompt.lower(), r"verdict_reason[\s\S]{0,160}reason")
        self.assertIn("Empty output is invalid", prompt)
        self.assertIn("Non-parseable output is invalid", prompt)
        self.assertIn("Output outside the JSON object is invalid", prompt)
        self.assertIn("Do not write any text before or after the JSON object", prompt)
        self.assertIn('"verdict": "insufficient"', prompt)
        self.assertIn("Never return silence", prompt)

    def test_builder_requires_approved_test_contract_and_cannot_relax_tests(self) -> None:
        prompt = read_text(AGENTS_DIR / "builder.md")
        self.assertIn("test contract", prompt.lower())
        self.assertIn("approved", prompt.lower())
        self.assertIn("docs-only trivial", prompt.lower())
        self.assertIn("tests_that_must_not_be_relaxed", prompt)
        self.assertIn("minimum_focused_commands", prompt)
        self.assertIn("Never relax tests", prompt)

    def test_builder_has_verifiable_output_contract(self) -> None:
        prompt = read_text(AGENTS_DIR / "builder.md")
        for field in (
            "builder_id",
            "status",
            "files_changed",
            "tests_added_or_modified",
            "tests_deliberately_not_changed",
            "commands_run",
            "write_scope_violations",
            "risks",
        ):
            self.assertIn(f'"{field}"', prompt)
        self.assertIn('"status": "completed|partial|blocked|failed"', prompt)
        self.assertIn("required writes and no file was written", prompt)
        self.assertIn("Empty output is invalid", prompt)

    def test_planner_consumes_test_contract(self) -> None:
        prompt = read_text(AGENTS_DIR / "planner.md")
        self.assertIn("test_contract", prompt)
        self.assertIn("existing_tests_authority", prompt)
        self.assertIn("minimum_focused_commands", prompt)

    def test_documenter_has_verifiable_output_contract(self) -> None:
        prompt = read_text(AGENTS_DIR / "documenter.md")
        for field in (
            "documenter_id",
            "status",
            "docs_changed",
            "reason",
            "canonical_docs_required",
            "operational_docs_required",
            "risks",
        ):
            self.assertIn(f'"{field}"', prompt)
        self.assertIn('"status": "completed|not_applicable|blocked|failed"', prompt)
        self.assertIn("devolver `not_applicable`", prompt)
        self.assertIn("Salida vacia o no parseable", prompt)

    def test_validator_validates_against_test_contract_after_documentation(self) -> None:
        prompt = read_text(AGENTS_DIR / "validator.md")
        self.assertIn("test contract", prompt.lower())
        self.assertIn("minimum_focused_commands", prompt)
        self.assertIn("recommended_regression_commands", prompt)
        self.assertIn(GOVERNANCE_COMMAND, prompt)
        self.assertIn("partial", prompt)
        self.assertIn("fail", prompt)
        self.assertIn("git diff", prompt)
        self.assertIn("relaxed", prompt.lower())

    def test_validator_cannot_pass_without_minimum_command_evidence(self) -> None:
        prompt = read_text(AGENTS_DIR / "validator.md")
        self.assertIn("`commands_run` no puede estar vacio", prompt)
        self.assertIn("Si no ejecuta comandos minimos aplicables", prompt)
        self.assertIn("nunca `pass`", prompt)
        self.assertIn("salida de comandos no es visible", prompt)
        self.assertIn('"results": "pass|fail|partial|not_run|blocked"', prompt)

    def test_code_reviewer_has_test_quality_truth_dimension(self) -> None:
        prompt = read_text(AGENTS_DIR / "code-reviewer.md")
        self.assertIn("Test Quality / Test Truth", prompt)
        self.assertIn("tests existing were relaxed", prompt)
        self.assertIn("test contract was respected", prompt)
        self.assertIn("must_fix: true", prompt)

    def test_code_reviewer_must_fix_missing_subagent_or_git_evidence(self) -> None:
        prompt = read_text(AGENTS_DIR / "code-reviewer.md")
        for phrase in (
            "Falta salida estructurada de un subagente obligatorio",
            "`builder` no demuestra escritura",
            "`validator` no demuestra ejecucion de comandos minimos aplicables",
            "ausencia de diff como exito sin comprobar `git status`",
            "vacio, no parseable o no cumple su contrato",
        ):
            self.assertIn(phrase, prompt)

    def test_primary_testing_commands_follow_unittest_contract(self) -> None:
        pyproject = tomllib.loads(read_text(ROOT / "pyproject.toml"))
        dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]
        self.assertFalse(any(dep.lower().startswith("pytest") for dep in dev_dependencies))

        prompt_sources = [
            read_text(path)
            for path in [
                AGENTS_DIR / "queen.md",
                AGENTS_DIR / "builder.md",
                AGENTS_DIR / "code-reviewer.md",
                AGENTS_DIR / "godot-adapter.md",
                AGENTS_DIR / "test-strategist.md",
                ROOT / ".opencode" / "commands" / "queen.md",
                ROOT / "AGENTS.md",
            ]
        ]
        combined = "\n".join(prompt_sources)
        self.assertIn("py -m unittest discover -s tests", combined)
        self.assertNotIn("py -m pytest", combined)

    def test_max_cycles_is_consistent(self) -> None:
        self.assertEqual(queen_state.DEFAULT_MAX_CYCLES, 5)
        for name, source in {
            "AGENTS.md": read_text(ROOT / "AGENTS.md"),
            "queen.md": self.queen_prompt,
            "tools/queen_state.py": read_text(ROOT / "tools" / "queen_state.py"),
        }.items():
            self.assertRegex(source, r"max_cycles\s*=?\s*5|Max cycles: \{DEFAULT_MAX_CYCLES\}", msg=name)

    def test_definition_of_done_and_final_states_are_documented(self) -> None:
        for name, source in {
            "AGENTS.md": read_text(ROOT / "AGENTS.md"),
            "queen.md": self.queen_prompt,
            "tools/queen_state.py": read_text(ROOT / "tools" / "queen_state.py"),
        }.items():
            self.assertIn("Definition of Done", source, msg=name)
            for state in ("completed", "partial", "blocked", "failed"):
                self.assertIn(state, source, msg=f"{name}: {state}")

    def test_queen_task_permissions_are_bounded(self) -> None:
        queen_task = self.agent_config["queen"]["permission"]["task"]
        self.assertIsInstance(queen_task, dict)
        self.assertEqual(queen_task.get("*"), "deny")
        for subagent in EXPECTED_SUBAGENTS:
            self.assertEqual(queen_task.get(subagent), "allow", msg=subagent)

    def test_model_router_variant_prompt_files_exist(self) -> None:
        for variants in QUEEN_ROUTED_VARIANTS.values():
            for variant in variants:
                self.assertTrue((AGENTS_DIR / f"{variant}.md").exists(), msg=variant)

    def test_model_router_variants_are_registered_in_opencode_config(self) -> None:
        for variants in QUEEN_ROUTED_VARIANTS.values():
            for variant in variants:
                self.assertIn(variant, self.agent_config)
                self.assertEqual(self.agent_config[variant]["mode"], "subagent", msg=variant)

    def test_queen_can_invoke_model_router_variants_and_denies_wildcard(self) -> None:
        queen_task = self.agent_config["queen"]["permission"]["task"]
        self.assertEqual(queen_task.get("*"), "deny")
        for variants in QUEEN_ROUTED_VARIANTS.values():
            for variant in variants:
                self.assertEqual(queen_task.get(variant), "allow", msg=variant)

    def test_model_router_variant_permissions_match_base_agents(self) -> None:
        keys_to_compare = (
            "read",
            "glob",
            "grep",
            "edit",
            "write",
            "task",
            "todowrite",
            "question",
            "webfetch",
            "websearch",
            "skill",
            "bash",
        )
        for base, variants in QUEEN_ROUTED_VARIANTS.items():
            base_permissions = self.agent_config[base]["permission"]
            for variant in variants:
                variant_permissions = self.agent_config[variant]["permission"]
                for key in keys_to_compare:
                    self.assertEqual(
                        variant_permissions.get(key),
                        base_permissions.get(key),
                        msg=f"{variant}: {key}",
                    )

    def test_model_router_agent_models_match_policy(self) -> None:
        for agent_name, expected_model in EXPECTED_QUEEN_FLOW_MODELS.items():
            self.assertEqual(self.agent_config[agent_name]["model"], expected_model, msg=agent_name)

    def test_model_router_frontmatter_matches_config(self) -> None:
        for agent_name, expected_model in EXPECTED_QUEEN_FLOW_MODELS.items():
            prompt_frontmatter = frontmatter(read_text(AGENTS_DIR / f"{agent_name}.md"))
            self.assertIn(f"model: {expected_model}", prompt_frontmatter, msg=agent_name)

    def test_queen_documents_model_router(self) -> None:
        for phrase in (
            "Model Router",
            "task_complexity",
            "risk_level",
            "reasoning_required",
            "selected_agents",
            "simple",
            "normal",
            "complex",
            "critical",
            "planner-deep",
            "code-reviewer-deep",
            "test-strategist-deep",
        ):
            self.assertIn(phrase, self.queen_prompt)

    def test_queen_selects_agent_variants_not_dynamic_config_edits(self) -> None:
        phrase = "Queen selects agent variants, not dynamic config edits"
        self.assertIn(phrase, self.queen_prompt)
        self.assertIn(phrase, read_text(ROOT / ".opencode" / "commands" / "queen.md"))

    def test_long_task_mode_recalculates_model_route_per_phase(self) -> None:
        long_task_doc = read_text(ROOT / "docs" / "queen_long_task_mode.md")
        self.assertIn("recalcula `model_route` al inicio de cada fase", long_task_doc)

    def test_model_router_variants_keep_output_contract_and_invalid_output_rules(self) -> None:
        for variants in QUEEN_ROUTED_VARIANTS.values():
            for variant in variants:
                prompt = read_text(AGENTS_DIR / f"{variant}.md")
                prompt_lower = prompt.lower()
                self.assertRegex(prompt_lower, r"same\s+output\s+contract|mismo contrato de salida")
                self.assertIn("TEST CONTRACT", prompt)
                self.assertRegex(prompt_lower, r"empty output|salida vacia")
                self.assertRegex(prompt_lower, r"non-parseable\s+output|no-parseable|no parseable")

    def test_all_allowed_subagents_exist_in_config_and_have_prompt(self) -> None:
        queen_task = self.agent_config["queen"]["permission"]["task"]
        allowed = {key for key, value in queen_task.items() if value == "allow"}
        self.assertEqual(allowed, EXPECTED_SUBAGENTS)
        missing_config = EXPECTED_SUBAGENTS - set(self.agent_config)
        self.assertEqual(missing_config, set())
        missing_prompts = {name for name in EXPECTED_SUBAGENTS if not (AGENTS_DIR / f"{name}.md").exists()}
        self.assertEqual(missing_prompts, set())

    def test_validator_agent_exists_and_is_read_only(self) -> None:
        self.assertTrue((AGENTS_DIR / "validator.md").exists(), "validator.md prompt file must exist")
        self.assertIn("validator", self.agent_config)
        config = self.agent_config["validator"]
        self.assertEqual(config.get("mode"), "subagent")
        for key in ("edit", "write", "task", "todowrite"):
            self.assertEqual(config["permission"].get(key), "deny", f"validator must deny {key}")
        bash = config["permission"].get("bash")
        self.assertIsInstance(bash, dict)
        self.assertEqual(bash.get("*"), "deny")
        val_prompt = read_text(AGENTS_DIR / "validator.md")
        self.assertIn("read-only", val_prompt.lower())

    def test_queen_blocks_for_insufficient_or_missing_test_contract(self) -> None:
        self.assertIn("verdict = insufficient", self.queen_prompt)
        self.assertIn("not_applicable", self.queen_prompt)
        self.assertIn("docs-only trivial", self.queen_prompt.lower())
        self.assertIn("cannot delegate implementation", self.queen_prompt.lower())

    def test_queen_blocks_empty_or_non_parseable_mandatory_subagent_output(self) -> None:
        for phrase in (
            "salida vacia",
            "salida no parseable",
            "no cumple su contrato",
            "marca la fase como `blocked`",
            "missing_subagent_result",
        ):
            self.assertIn(phrase, self.queen_prompt)

        for subagent in (
            "context-recon",
            "test-strategist",
            "planner",
            "builder",
            "documenter",
            "validator",
            "code-reviewer",
            "ai-friendliness",
        ):
            self.assertIn(f"`{subagent}`", self.queen_prompt)

    def test_context_recon_is_mandatory_in_structured_subagent_gate(self) -> None:
        match = re.search(
            r"Subagentes obligatorios con contrato de salida:\s*(?P<body>[\s\S]*?)\nReglas:",
            self.queen_prompt,
        )
        self.assertIsNotNone(match)
        gate_body = match.group("body")
        self.assertIn("- `context-recon`", gate_body)
        self.assertIn("RECON no puede considerarse completado", self.queen_prompt)
        self.assertIn("salida estructurada verificable de\n  `context-recon`", self.queen_prompt)
        self.assertIn("Queen debe bloquear si `context-recon`", self.queen_prompt)

    def test_queen_cannot_complete_without_structured_mandatory_subagent_result(self) -> None:
        for phrase in (
            "No puede haber `completed`",
            "salida vacia",
            "no verificable",
            "Queen no puede inferir exito por ausencia de cambios",
        ):
            self.assertIn(phrase, self.queen_prompt)
        self.assertRegex(self.queen_prompt, r"resultado\s+estructurado del subagente")

    def test_queen_flow_uses_expected_openai_models_for_provider_smoke(self) -> None:
        for agent_name in QUEEN_FLOW_AGENTS:
            self.assertEqual(
                self.agent_config[agent_name]["model"],
                EXPECTED_QUEEN_FLOW_MODELS[agent_name],
                msg=agent_name,
            )

        self.assertEqual(self.config["command"]["queen"]["model"], EXPECTED_QUEEN_FLOW_MODELS["queen"])

        for agent_name in QUEEN_FLOW_AGENTS:
            self.assertNotRegex(
                self.agent_config[agent_name]["model"],
                r"^opencode-go/deepseek-",
                msg=agent_name,
            )
        self.assertNotRegex(self.config["command"]["queen"]["model"], r"^opencode-go/deepseek-")

        for godot_agent in ("godot-source-analyzer", "godot-gap-analyzer", "godot-adapter"):
            self.assertRegex(
                self.agent_config[godot_agent]["model"],
                r"^opencode-go/deepseek-",
                msg=godot_agent,
            )

    def test_queen_flow_frontmatter_matches_expected_model(self) -> None:
        for prompt_name, prompt_path in QUEEN_FLOW_PROMPT_FILES.items():
            expected_model = (
                EXPECTED_QUEEN_FLOW_MODELS["queen"]
                if prompt_name == "queen-command"
                else EXPECTED_QUEEN_FLOW_MODELS[prompt_name]
            )
            prompt_frontmatter = frontmatter(read_text(prompt_path))
            self.assertIn(
                f"model: {expected_model}",
                prompt_frontmatter,
                msg=prompt_name,
            )

    def test_queen_flow_has_no_deepseek_model_drift(self) -> None:
        for prompt_name, prompt_path in QUEEN_FLOW_PROMPT_FILES.items():
            self.assertNotIn("opencode-go/deepseek", read_text(prompt_path), msg=prompt_name)

        queen_flow_config = {
            "agent": {name: self.agent_config[name] for name in QUEEN_FLOW_AGENTS},
            "command": {"queen": self.config["command"]["queen"]},
        }
        self.assertNotIn("opencode-go/deepseek", json.dumps(queen_flow_config), msg="opencode.json")

    def test_queen_can_block_for_clarification(self) -> None:
        question_perm = self.agent_config["queen"]["permission"].get("question")
        is_not_denied = question_perm != "deny"
        queen_prompt_has_blocked = "blocked_needs_clarification" in self.queen_prompt or "needs_clarificat" in self.queen_prompt
        self.assertTrue(
            is_not_denied or queen_prompt_has_blocked,
            "Queen must be able to block for clarification: either question allowed "
            "or blocked_needs_clarification fallback documented",
        )

    def test_commit_is_gated_by_validator_review_audit(self) -> None:
        committer_prompt = read_text(AGENTS_DIR / "committer.md")
        self.assertIn("validator", committer_prompt.lower())
        self.assertIn("review", committer_prompt.lower())
        self.assertIn("AI AUDIT", self.queen_prompt)
        for phase in ("VALIDAR", "REVIEW", "AI AUDIT", "COMMIT"):
            self.assertIn(phase, self.queen_prompt)
        self.assertLess(cycle_index(NORMAL_CYCLE, "VALIDAR"), cycle_index(NORMAL_CYCLE, "COMMIT"))
        self.assertLess(cycle_index(NORMAL_CYCLE, "REVIEW"), cycle_index(NORMAL_CYCLE, "COMMIT"))

    def test_ai_friendliness_can_declare_not_applicable(self) -> None:
        ai_prompt = read_text(AGENTS_DIR / "ai-friendliness.md")
        has_not_applicable = "not_applicable" in ai_prompt.lower()
        has_exception = "cuando aplica" in self.queen_prompt.lower()
        self.assertTrue(
            has_not_applicable or has_exception,
            "AI-friendliness must be able to declare not_applicable with reason",
        )

    def test_ai_friendliness_has_verifiable_output_or_not_applicable_reason(self) -> None:
        ai_prompt = read_text(AGENTS_DIR / "ai-friendliness.md")
        self.assertIn("Return exactly one JSON object", ai_prompt)
        self.assertIn("non-parseable output", ai_prompt)
        self.assertIn('"applicable": true', ai_prompt)
        self.assertIn('"not_applicable_reason"', ai_prompt)
        self.assertIn("If no score applies", ai_prompt)
        self.assertIn("not_applicable", ai_prompt)

    def test_permission_smoke_sandbox_fixture_exists_and_is_git_verifiable(self) -> None:
        self.assertTrue(PERMISSION_SANDBOX.exists())
        content = read_text(PERMISSION_SANDBOX)
        self.assertIn("Authority: test-fixture", content)
        self.assertIn("Queen/OpenCode permission smoke tests", content)
        self.assertIn("## Current marker", content)
        self.assertIn("initial", content)

    def test_no_engine_files_touched_by_harness_change(self) -> None:
        self.assertTrue((ROOT / "engine").is_dir(), "engine/ directory must exist")

    def test_long_task_plan_mode_is_documented(self) -> None:
        self.assertIn("Long Task Plan Mode", self.queen_prompt)
        agents_md = read_text(ROOT / "AGENTS.md")
        self.assertIn("Long Task Plan", agents_md)

    def test_plan_mode_requires_plan_sync_and_test_contract_before_implementation(self) -> None:
        self.assertIn("LOAD PLAN", self.queen_prompt)
        self.assertIn("PLAN SYNC", self.queen_prompt)
        self.assertLess(self.queen_prompt.index("TEST CONTRACT"), self.queen_prompt.index("IMPLEMENTAR FASE"))

    def test_plan_mode_updates_plan_after_ai_audit(self) -> None:
        self.assertIn("AI AUDIT", self.queen_prompt)
        self.assertIn("UPDATE PLAN", self.queen_prompt)
        self.assertLess(self.queen_prompt.index("AI AUDIT"), self.queen_prompt.index("UPDATE PLAN"))

    def test_operational_plans_are_not_canonical_docs(self) -> None:
        plans_readme = ROOT / "docs" / "plans" / "README.md"
        if plans_readme.exists():
            content = read_text(plans_readme)
            self.assertIn("Authority: operational-plan", content)
        else:
            self.fail("docs/plans/README.md must exist")

    def test_engine_workflow_doc_is_operational_and_linked(self) -> None:
        self.assertTrue(WORKFLOW_DOC.exists())
        workflow = read_text(WORKFLOW_DOC)
        self.assertIn("Authority: operational-workflow", workflow)
        for subsystem in (
            "docs-only",
            "CLI",
            "EngineAPI",
            "Scene/SceneManager/authoring",
            "schema/serialization/migrations",
            "physics/collision",
            "render",
            "editor/runtime",
            "export pipeline",
            "components/component registry",
            "experimental/tooling",
        ):
            self.assertIn(subsystem, workflow)

        for path in (ROOT / "AGENTS.md", ROOT / "docs" / "agents.md", ROOT / "docs" / "queen_long_task_mode.md"):
            self.assertIn("docs/queen_engine_workflow.md", read_text(path), msg=str(path))

        agents_md = read_text(ROOT / "AGENTS.md")
        self.assertLess(agents_md.count("docs-only"), 2, "AGENTS.md must link the matrix, not duplicate it")

    def test_engine_workflow_documents_git_verifiable_permission_smoke_sandbox(self) -> None:
        workflow = read_text(WORKFLOW_DOC)
        self.assertIn("no usar `.motor/queen_state`", workflow)
        self.assertIn("tests/fixtures/queen_permission_smoke/permission_sandbox.md", workflow)
        self.assertIn("lectura antes y despues", workflow)
        self.assertIn("git diff --name-only -- tests/fixtures/queen_permission_smoke/permission_sandbox.md", workflow)
        self.assertIn("git diff -- tests/fixtures/queen_permission_smoke/permission_sandbox.md", workflow)
        self.assertIn("git status --short -- tests/fixtures/queen_permission_smoke/permission_sandbox.md", workflow)
        self.assertIn("No usar solo `git diff --name-only`", workflow)
        self.assertIn("git status --short --untracked-files=all -- <ruta>", workflow)


if __name__ == "__main__":
    unittest.main()
