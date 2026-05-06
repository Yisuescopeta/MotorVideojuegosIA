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


if __name__ == "__main__":
    unittest.main()
