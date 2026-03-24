import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(os.getcwd())

from tools.engine_cli import _ensure_opencode_artifact_dir, parse_args


class EngineCliTests(unittest.TestCase):
    def test_opencode_ask_subcommand_parses_expected_arguments(self) -> None:
        args = parse_args(
            [
                "opencode",
                "ask",
                "--session",
                "sess_123",
                "--agent",
                "plan",
                "--prompt-file",
                "docs/prompt.txt",
                "--out",
                "artifacts/opencode/custom",
            ]
        )

        self.assertEqual(args.command, "opencode")
        self.assertEqual(args.opencode_command, "ask")
        self.assertEqual(args.session, "sess_123")
        self.assertEqual(args.agent, "plan")
        self.assertEqual(args.prompt_file, "docs/prompt.txt")
        self.assertEqual(args.out, "artifacts/opencode/custom")

    def test_opencode_approvals_subcommand_parses_response_arguments(self) -> None:
        args = parse_args(
            [
                "opencode",
                "approvals",
                "--session",
                "sess_123",
                "--permission-id",
                "perm_9",
                "--response",
                "allow",
                "--remember",
            ]
        )

        self.assertEqual(args.command, "opencode")
        self.assertEqual(args.opencode_command, "approvals")
        self.assertEqual(args.permission_id, "perm_9")
        self.assertEqual(args.response, "allow")
        self.assertTrue(args.remember)

    def test_opencode_sessions_subcommand_parses_output_argument(self) -> None:
        args = parse_args(["opencode", "sessions", "--out", "artifacts/opencode/sessions"])
        self.assertEqual(args.command, "opencode")
        self.assertEqual(args.opencode_command, "sessions")
        self.assertEqual(args.out, "artifacts/opencode/sessions")

    def test_opencode_messages_subcommand_parses_limit_and_output(self) -> None:
        args = parse_args(["opencode", "messages", "--session", "sess_123", "--limit", "25", "--out", "artifacts/opencode/messages"])
        self.assertEqual(args.command, "opencode")
        self.assertEqual(args.opencode_command, "messages")
        self.assertEqual(args.session, "sess_123")
        self.assertEqual(args.limit, 25)
        self.assertEqual(args.out, "artifacts/opencode/messages")

    def test_opencode_artifact_dir_generation_uses_timestamp_prefix_and_session_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                artifact_dir = _ensure_opencode_artifact_dir("sess:123/demo")
                self.assertTrue(artifact_dir.exists())
                self.assertEqual(artifact_dir.parent.name, "opencode")
                self.assertIn("_sess_123_demo", artifact_dir.name)
            finally:
                os.chdir(previous_cwd)

    def test_validate_scene_subcommand(self) -> None:
        exit_code = os.system("py -3 tools/engine_cli.py validate --target scene --path levels/demo_level.json")
        self.assertEqual(exit_code, 0)

    def test_smoke_subcommand_produces_expected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "smoke"
            exit_code = os.system(
                f'py -3 tools/engine_cli.py smoke --scene levels/demo_level.json --frames 2 --seed 7 --out-dir "{out_dir.as_posix()}"'
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue((out_dir / "smoke_migrated_scene.json").exists())
            self.assertTrue((out_dir / "smoke_debug_dump.json").exists())
            self.assertTrue((out_dir / "smoke_profile.json").exists())

            profile_report = json.loads((out_dir / "smoke_profile.json").read_text(encoding="utf-8"))
            debug_dump = json.loads((out_dir / "smoke_debug_dump.json").read_text(encoding="utf-8"))

        self.assertEqual(profile_report["frames"], 2)
        self.assertEqual(debug_dump["pass"], "Debug")


if __name__ == "__main__":
    unittest.main()
