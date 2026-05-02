import unittest
from pathlib import Path

from motor.cli import create_motor_parser

ROOT = Path(__file__).resolve().parents[1]


class RepositoryGovernanceTests(unittest.TestCase):
    def test_governance_files_exist(self) -> None:
        expected = [
            ROOT / "LICENSE",
            ROOT / "CONTRIBUTING.md",
            ROOT / "SECURITY.md",
            ROOT / ".github" / "pull_request_template.md",
            ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.md",
            ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.md",
        ]
        for path in expected:
            self.assertTrue(path.exists(), msg=f"Missing governance file: {path.name}")

    def test_readme_mentions_governance_documents(self) -> None:
        source = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("LICENSE", source)
        self.assertIn("CONTRIBUTING.md", source)
        self.assertIn("SECURITY.md", source)

    def test_primary_docs_describe_current_contract_and_classification(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8").lower()
        technical = (ROOT / "docs" / "TECHNICAL.md").read_text(encoding="utf-8").lower()
        combined = "\n".join((readme, architecture, technical))

        for phrase in (
            "schema_version = 2",
            "scenemanager",
            "engineapi",
            "core obligatorio",
            "modulos oficiales opcionales",
            "experimental/tooling",
        ):
            self.assertIn(phrase, combined)

        self.assertIn("engine/rl", combined)
        self.assertIn("sync_from_edit_world()", combined)
        self.assertIn("docs/module_taxonomy.md", readme)

    def test_module_taxonomy_doc_exists_and_names_key_subsystems(self) -> None:
        path = ROOT / "docs" / "module_taxonomy.md"
        self.assertTrue(path.exists(), msg="Missing canonical module taxonomy doc")

        source = path.read_text(encoding="utf-8").lower()

        for phrase in (
            "core obligatorio",
            "modulos oficiales opcionales",
            "experimental/tooling",
            "ecs",
            "scene",
            "scenemanager",
            "serializacion",
            "editor base",
            "jerarquia",
            "engineapi",
            "assets",
            "prefabs",
            "tilemap",
            "audio",
            "ui",
            "box2d",
            "engine/rl",
            "multiagente",
        ):
            self.assertIn(phrase, source)

    def test_issue_templates_have_front_matter(self) -> None:
        templates = [
            ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.md",
            ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.md",
        ]
        for path in templates:
            source = path.read_text(encoding="utf-8")
            self.assertTrue(source.startswith("---\n"), msg=f"Missing front matter in {path.name}")

    def test_security_policy_uses_private_reporting_without_placeholder(self) -> None:
        source = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertNotIn("TODO", source)
        self.assertTrue(
            "GitHub Security Advisories" in source or "private vulnerability reporting" in source,
            msg="SECURITY.md should point to a private reporting channel",
        )

    def test_manual_genre_recipes_use_only_current_public_surfaces(self) -> None:
        source = (ROOT / "docs" / "agents.md").read_text(encoding="utf-8")
        start = source.find("## Recetas manuales seguras por genero")
        end = source.find("Para gameplay runtime usa", start)
        self.assertGreater(start, -1, msg="Missing safe manual genre recipes section")
        self.assertGreater(end, start, msg="Safe manual genre recipes section should end before runtime guidance")
        section = source[start:end]

        for phrase in (
            "Top-down",
            "Puzzle",
            "Main menu",
            "EngineAPI.create_canvas",
            "EngineAPI.create_ui_text",
            "EngineAPI.create_ui_button",
            "emit_event",
            "set_position",
            "spawn_entity",
            "No crees `run_game.py`",
        ):
            self.assertIn(phrase, section)

        for unsupported in (
            "motor game topdown",
            "motor game puzzle",
            "motor game shmup",
            "motor recipe run topdown",
        ):
            self.assertIn(unsupported, section)
            self.assertIn("no uses", section.lower())

        parser = create_motor_parser()
        public_commands = _public_leaf_commands(parser)
        expected_commands = {
            ("scene", "create"),
            ("entity", "create"),
            ("component", "add"),
            ("component", "edit"),
            ("runtime", "play"),
            ("runtime", "step"),
            ("ai", "compliance"),
        }
        for command in expected_commands:
            self.assertIn(command, public_commands)

        self.assertNotIn("run_game.py` como solucion", section.lower())


def _public_leaf_commands(parser) -> set[tuple[str, ...]]:
    commands: set[tuple[str, ...]] = set()

    def walk(current_parser, prefix: tuple[str, ...]) -> None:
        sub_actions = [
            action
            for action in getattr(current_parser, "_actions", [])
            if isinstance(getattr(action, "choices", None), dict) and action.choices
        ]
        if not sub_actions:
            if prefix:
                commands.add(prefix)
            return
        for action in sub_actions:
            for name, subparser in action.choices.items():
                walk(subparser, (*prefix, name))

    walk(parser, ())
    return commands


if __name__ == "__main__":
    unittest.main()
