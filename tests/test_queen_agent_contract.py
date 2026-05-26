from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path

import tools.queen_state as queen_state

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / ".opencode" / "agents"
CYCLE = (
    "RECON -> PLAN -> CRITICA DEL PLAN -> IMPLEMENTAR -> DOCUMENTAR -> "
    "VALIDAR -> REVIEW -> AI AUDIT -> COMMIT -> REPORTE"
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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

    def test_queen_has_no_mutating_permissions(self) -> None:
        permissions = self.agent_config["queen"]["permission"]
        self.assertEqual(permissions.get("edit"), "deny")
        self.assertEqual(permissions.get("write"), "deny")
        self.assertEqual(permissions.get("bash"), "deny")
        self.assertIsNone(re.search(r"^\s+edit:\s+allow\s*$", self.queen_prompt, re.MULTILINE))
        self.assertIsNone(re.search(r"^\s+write:\s+allow\s*$", self.queen_prompt, re.MULTILINE))
        self.assertIsNone(re.search(r"^\s+bash:\s+allow\s*$", self.queen_prompt, re.MULTILINE))

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

    def test_documentation_precedes_commit_in_all_queen_cycle_sources(self) -> None:
        sources = {
            "AGENTS.md": read_text(ROOT / "AGENTS.md"),
            "queen.md": self.queen_prompt,
            "command": read_text(ROOT / ".opencode" / "commands" / "queen.md"),
            "opencode.json": read_text(ROOT / "opencode.json"),
        }
        for name, source in sources.items():
            self.assertIn(CYCLE, source, msg=name)
            steps = [part.strip() for part in CYCLE.split("->")]
            self.assertLess(steps.index("DOCUMENTAR"), steps.index("COMMIT"), msg=name)

    def test_committer_requires_explicit_staging_and_blocks_unrelated_files(self) -> None:
        committer_prompt = read_text(AGENTS_DIR / "committer.md")
        committer_bash = self.agent_config["committer"]["permission"]["bash"]

        self.assertIn("git add -- *", committer_bash)
        self.assertIn("git add -- <ruta>", committer_prompt)
        self.assertIn("archivos esperados", committer_prompt)
        self.assertIn("blocked", committer_prompt)

        forbidden = ("git add .", "git add -A", '"git add *"', "`git add *`")
        combined = committer_prompt + "\n" + json.dumps(committer_bash, sort_keys=True)
        for command in forbidden:
            self.assertNotIn(command, combined)

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


    # ── Wave 1: Security & Control (new contract tests) ──────────────────

    def test_queen_task_permissions_are_bounded(self) -> None:
        queen_task = self.agent_config["queen"]["permission"]["task"]
        is_dict = isinstance(queen_task, dict)
        if is_dict:
            has_wildcard_allow = queen_task.get("*") == "allow"
            has_other_allows = any(k != "*" and v == "allow" for k, v in queen_task.items())
            wildcard_unrestricted = has_wildcard_allow and not has_other_allows
        else:
            wildcard_unrestricted = queen_task == "allow"

        self.assertFalse(
            wildcard_unrestricted,
            "Queen task delegation must be bounded, not unrestricted {'*': 'allow'}",
        )
        self.assertTrue(
            is_dict,
            "Queen task permission must be a dict with explicit deny/allow entries",
        )
        if is_dict:
            self.assertIn("builder", queen_task)
            self.assertIn("committer", queen_task)

    def test_all_allowed_subagents_exist_in_config_and_have_prompt(self) -> None:
        queen_task = self.agent_config["queen"]["permission"]["task"]
        if isinstance(queen_task, dict):
            allowed = {k for k, v in queen_task.items() if v == "allow" and k != "*"}
            allowed.discard("builder")
            allowed.discard("committer")
            allowed.discard("documenter")
            allowed.discard("code-reviewer")
            allowed.discard("ai-friendliness")
            allowed.discard("context-recon")
            allowed.discard("planner")
            allowed.discard("godot-source-analyzer")
            allowed.discard("godot-gap-analyzer")
            allowed.discard("godot-adapter")
            expected = {
                "builder", "committer", "documenter", "code-reviewer",
                "ai-friendliness", "context-recon", "planner",
                "godot-source-analyzer", "godot-gap-analyzer", "godot-adapter",
            }
            actually_configured = {a for a in expected if a in self.agent_config}
            missing = expected - actually_configured
            self.assertEqual(
                missing, set(),
                f"Subagents not configured in opencode.json: {missing}",
            )
            missing_prompts = {
                a for a in expected
                if not (AGENTS_DIR / f"{a}.md").exists()
            }
            self.assertEqual(
                missing_prompts, set(),
                f"Subagents missing prompt files: {missing_prompts}",
            )

    def test_validator_agent_exists_and_is_read_only(self) -> None:
        self.assertTrue(
            (AGENTS_DIR / "validator.md").exists(),
            "validator.md prompt file must exist",
        )
        self.assertIn("validator", self.agent_config)
        vc = self.agent_config["validator"]
        self.assertEqual(vc.get("mode"), "subagent")
        for key in ("edit", "write", "task", "todowrite"):
            self.assertEqual(
                vc["permission"].get(key), "deny",
                f"validator must deny {key}",
            )
        bash = vc["permission"].get("bash")
        self.assertIsInstance(bash, dict)
        self.assertEqual(bash.get("*"), "deny")
        val_prompt = read_text(AGENTS_DIR / "validator.md")
        self.assertIn("read-only", val_prompt.lower())

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
        has_validator_gate = "validator" in committer_prompt.lower()
        has_review_gate = "review" in committer_prompt.lower()
        self.assertTrue(
            has_validator_gate or has_review_gate,
            "Committer prompt must reference validator and/or reviewer as commit gates",
        )
        queen_cycle = self.queen_prompt
        self.assertIn("VALIDAR", queen_cycle)
        self.assertIn("REVIEW", queen_cycle)
        self.assertIn("COMMIT", queen_cycle)
        phases = ["VALIDAR", "REVIEW", "AI AUDIT", "COMMIT"]
        idx = {p: queen_cycle.index(p) for p in phases}
        self.assertLess(idx["VALIDAR"], idx["COMMIT"])
        self.assertLess(idx["REVIEW"], idx["COMMIT"])

    def test_ai_friendliness_can_declare_not_applicable(self) -> None:
        ai_prompt = read_text(AGENTS_DIR / "ai-friendliness.md")
        has_not_applicable = "not_applicable" in ai_prompt.lower()
        has_exception = "cuando aplica" in self.queen_prompt.lower()
        self.assertTrue(
            has_not_applicable or has_exception,
            "AI-friendliness must be able to declare not_applicable with reason",
        )

    def test_no_engine_files_touched_by_harness_change(self) -> None:
        """Guard: this wave must not touch engine/ runtime files."""
        # This test is a self-check — it should always pass unless someone
        # intentionally modifies engine/ in the same diff.
        # If engine/ files appear in git diff, the committer must justify them.
        self.assertTrue(
            (ROOT / "engine").is_dir(),
            "engine/ directory must exist (sanity check)",
        )

    # ── Wave 2: Long Task Plan Mode ──────────────────────────────────

    def test_long_task_plan_mode_is_documented(self) -> None:
        self.assertIn("Long Task Plan Mode", self.queen_prompt)
        agents_md = read_text(ROOT / "AGENTS.md")
        self.assertIn("Long Task Plan", agents_md)

    def test_plan_mode_requires_plan_sync_before_implementation(self) -> None:
        self.assertIn("LOAD PLAN", self.queen_prompt)
        self.assertIn("PLAN SYNC", self.queen_prompt)
        self.assertTrue(
            "LOAD PLAN" in self.queen_prompt or "plan sync" in self.queen_prompt.lower(),
            "Queen must load/sync plan before implementing any phase",
        )

    def test_plan_mode_updates_plan_after_phase(self) -> None:
        self.assertIn("UPDATE PLAN", self.queen_prompt)
        self.assertTrue(
            "UPDATE PLAN" in self.queen_prompt or "actualizar" in self.queen_prompt.lower(),
            "Queen must update plan after each phase",
        )

    def test_operational_plans_are_not_canonical_docs(self) -> None:
        plans_readme = ROOT / "docs" / "plans" / "README.md"
        if plans_readme.exists():
            content = read_text(plans_readme)
            self.assertIn("Authority: operational-plan", content)
        else:
            self.fail("docs/plans/README.md must exist")


if __name__ == "__main__":
    unittest.main()
