import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
