import json
import re
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent


def _strip_jsonc_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    return text


class OpenCodeConfigTests(unittest.TestCase):
    def test_opencode_config_exists_and_contains_key_fields(self) -> None:
        config_path = REPO_ROOT / "opencode.jsonc"
        self.assertTrue(config_path.exists(), "opencode.jsonc must exist at repo root")

        data = json.loads(_strip_jsonc_comments(config_path.read_text(encoding="utf-8")))

        self.assertEqual(data["$schema"], "https://opencode.ai/config.json")
        self.assertIn("instructions", data)
        self.assertIn("permission", data)

        instructions = data["instructions"]
        self.assertIn("docs/architecture.md", instructions)
        self.assertIn("docs/cli.md", instructions)
        self.assertIn("docs/rl.md", instructions)
        self.assertIn("docs/opencode/*.md", instructions)

        permission = data["permission"]
        self.assertEqual(permission["*"], "ask")
        self.assertEqual(permission["external_directory"], "deny")
        self.assertEqual(permission["doom_loop"], "ask")

        bash_rules = permission["bash"]
        self.assertEqual(bash_rules["git push *"], "deny")
        self.assertEqual(bash_rules["rm *"], "deny")
        self.assertEqual(bash_rules["py -3 tools/engine_cli.py *"], "allow")
        self.assertEqual(bash_rules["py -3 tools/scenario_dataset_cli.py *"], "allow")
        self.assertEqual(bash_rules["py -3 tools/parallel_rollout_runner.py *"], "allow")

        edit_rules = permission["edit"]
        self.assertEqual(edit_rules["*"], "deny")
        self.assertEqual(edit_rules["docs/**"], "allow")
        self.assertEqual(edit_rules["engine/**"], "ask")

        read_rules = permission["read"]
        self.assertEqual(read_rules["*.env"], "deny")
        self.assertEqual(read_rules["*.env.*"], "deny")
        self.assertEqual(read_rules["*.env.example"], "allow")


if __name__ == "__main__":
    unittest.main()
