from pathlib import Path
import unittest


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
