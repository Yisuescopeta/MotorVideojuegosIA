from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "queen" / "scripts" / "run_opencode_subagent.py"


def load_dispatch_module():
    spec = importlib.util.spec_from_file_location("queen_dispatch", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_builder_result() -> dict:
    return {
        "builder_id": "builder-test",
        "status": "completed",
        "phase_status": "completed",
        "files_changed": ["example.txt"],
        "tests_added_or_modified": [],
        "tests_deliberately_not_changed": [],
        "commands_run": ["py -m unittest tests.test_queen_dispatch -v"],
        "write_scope_violations": [],
        "risks": [],
    }


def final_task_event(subagent_type: str = "builder", task_result: str | None = None) -> dict:
    return {
        "type": "tool_use",
        "tool": "task",
        "status": "completed",
        "input": {"subagent_type": subagent_type},
        "output": {"task_result": task_result if task_result is not None else json.dumps(valid_builder_result())},
        "metadata": {"backend": "opencode", "session": "s1", "model": "openai/gpt-5.4"},
    }


def real_opencode_task_event(subagent_type: str = "builder", task_result: str | None = None) -> dict:
    payload = task_result if task_result is not None else json.dumps(valid_builder_result())
    return {
        "type": "tool_use",
        "sessionID": "parent-top-level",
        "part": {
            "tool": "task",
            "state": {
                "status": "completed",
                "input": {"subagent_type": subagent_type},
                "output": f"<task><task_result>{payload}</task_result></task>",
                "metadata": {
                    "parentSessionId": "parent-from-metadata",
                    "sessionId": "child-session",
                    "model": {"providerID": "openai", "modelID": "gpt-5.4"},
                },
            },
        },
    }


class QueenDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dispatch = load_dispatch_module()

    def test_real_jsonl_task_event_with_trailing_root_events_outputs_compact_result(self) -> None:
        stdout = "\n".join([
            json.dumps({"type": "step_start", "sessionID": "parent-top-level"}),
            json.dumps(real_opencode_task_event()),
            json.dumps({"type": "text", "text": "root final success"}),
        ])
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")
        with mock.patch.object(self.dispatch, "resolve_opencode_executable", return_value="opencode"):
            with mock.patch.object(self.dispatch, "run_opencode", return_value=completed):
                with mock.patch.object(sys, "argv", ["run", "--role", "builder", "--repo-root", str(ROOT), "--prompt", "go"]):
                    with mock.patch("sys.stdout") as out, mock.patch("sys.stderr") as err:
                        self.assertEqual(self.dispatch.main(), 0)
        parsed = json.loads("".join(call.args[0] for call in out.write.call_args_list if call.args))
        self.assertEqual(parsed["builder_id"], "builder-test")
        metadata = json.loads("".join(call.args[0] for call in err.write.call_args_list if call.args))
        self.assertEqual(metadata["backend"], "opencode")
        self.assertEqual(metadata["role"], "builder")
        self.assertEqual(metadata["parent_session"], "parent-from-metadata")
        self.assertEqual(metadata["child_session"], "child-session")
        self.assertEqual(metadata["model"], "openai/gpt-5.4")

    def test_normalized_event_shape_still_supported(self) -> None:
        stdout = json.dumps([{"type": "assistant_delta", "text": "x"}, final_task_event()])
        task_result, metadata = self.dispatch.extract_task_result(stdout, "builder")
        self.assertEqual(json.loads(task_result)["builder_id"], "builder-test")
        self.assertEqual(metadata["backend"], "opencode")

    def test_trailing_root_success_after_task_is_ignored(self) -> None:
        stdout = json.dumps([final_task_event(), {"type": "assistant", "status": "completed"}])
        task_result, _metadata = self.dispatch.extract_task_result(stdout, "builder")
        self.assertEqual(json.loads(task_result)["builder_id"], "builder-test")

    def test_no_task_fake_success_is_process_failure(self) -> None:
        stdout = json.dumps([{"type": "assistant", "status": "completed", "text": "success"}])
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")
        with mock.patch.object(self.dispatch, "resolve_opencode_executable", return_value="opencode"):
            with mock.patch.object(self.dispatch, "run_opencode", return_value=completed):
                with mock.patch.object(sys, "argv", ["run", "--role", "builder", "--repo-root", str(ROOT), "--prompt", "go"]):
                    with mock.patch("sys.stderr"):
                        self.assertEqual(self.dispatch.main(), 5)

    def test_multiple_task_events_are_process_failure(self) -> None:
        stdout = json.dumps([final_task_event(), final_task_event("planner")])
        with self.assertRaises(self.dispatch.ProcessOutputError):
            self.dispatch.extract_task_result(stdout, "builder")

    def test_task_role_mismatch_is_process_failure(self) -> None:
        stdout = json.dumps([final_task_event("planner")])
        with self.assertRaises(self.dispatch.ProcessOutputError):
            self.dispatch.extract_task_result(stdout, "builder")

    def test_unknown_role_is_config_error(self) -> None:
        with mock.patch.object(sys, "argv", ["run", "--role", "does_not_exist", "--repo-root", str(ROOT), "--prompt", "go"]):
            with mock.patch("sys.stderr"):
                self.assertEqual(self.dispatch.main(), 2)

    def test_missing_opencode_executable_is_config_error(self) -> None:
        with mock.patch.object(self.dispatch.shutil, "which", return_value=None):
            with mock.patch.object(sys, "argv", ["run", "--role", "builder", "--repo-root", str(ROOT), "--prompt", "go"]):
                with mock.patch("sys.stderr"):
                    self.assertEqual(self.dispatch.main(), 2)

    def test_empty_truncated_and_non_json_process_output_is_process_failure(self) -> None:
        for stdout in ("", "{", "not-json"):
            with self.subTest(stdout=stdout):
                completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")
                with mock.patch.object(self.dispatch, "resolve_opencode_executable", return_value="opencode"):
                    with mock.patch.object(self.dispatch, "run_opencode", return_value=completed):
                        with mock.patch.object(sys, "argv", ["run", "--role", "builder", "--repo-root", str(ROOT), "--prompt", "go"]):
                            with mock.patch("sys.stderr"):
                                self.assertEqual(self.dispatch.main(), 5)

    def test_nonzero_process_exit_code_is_process_failure(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=17, stdout="", stderr="boom")
        with mock.patch.object(self.dispatch, "resolve_opencode_executable", return_value="opencode"):
            with mock.patch.object(self.dispatch, "run_opencode", return_value=completed):
                with mock.patch.object(sys, "argv", ["run", "--role", "builder", "--repo-root", str(ROOT), "--prompt", "go"]):
                    with mock.patch("sys.stderr"):
                        self.assertEqual(self.dispatch.main(), 4)

    def test_timeout_exit_code(self) -> None:
        with mock.patch.object(self.dispatch, "resolve_opencode_executable", return_value="opencode"):
            with mock.patch.object(self.dispatch, "run_opencode", side_effect=subprocess.TimeoutExpired("opencode", 1)):
                with mock.patch.object(sys, "argv", ["run", "--role", "builder", "--repo-root", str(ROOT), "--prompt", "go", "--timeout", "1"]):
                    with mock.patch("sys.stderr"):
                        self.assertEqual(self.dispatch.main(), 3)

    def test_invalid_contract_exit_code(self) -> None:
        event = final_task_event(task_result=json.dumps({"status": "completed"}))
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps([event]), stderr="")
        with mock.patch.object(self.dispatch, "resolve_opencode_executable", return_value="opencode"):
            with mock.patch.object(self.dispatch, "run_opencode", return_value=completed):
                with mock.patch.object(sys, "argv", ["run", "--role", "builder", "--repo-root", str(ROOT), "--prompt", "go"]):
                    with mock.patch("sys.stderr"):
                        self.assertEqual(self.dispatch.main(), 6)

    def test_task_result_empty_truncated_and_non_json_rejected(self) -> None:
        cases = {"": 5, "{": 6, "not-json": 6}
        for task_result, exit_code in cases.items():
            with self.subTest(task_result=task_result):
                event = real_opencode_task_event(task_result=task_result)
                completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps([event]), stderr="")
                with mock.patch.object(self.dispatch, "resolve_opencode_executable", return_value="opencode"):
                    with mock.patch.object(self.dispatch, "run_opencode", return_value=completed):
                        with mock.patch.object(sys, "argv", ["run", "--role", "builder", "--repo-root", str(ROOT), "--prompt", "go"]):
                            with mock.patch("sys.stderr"):
                                self.assertEqual(self.dispatch.main(), exit_code)

    def test_fallback_selection_does_not_mask_native_child_failures(self) -> None:
        for state in ("native_timeout", "native_permission_denied", "native_invalid_output", "native_process_failed"):
            with self.subTest(state=state):
                self.assertFalse(self.dispatch.should_use_fallback(state))
        self.assertTrue(self.dispatch.should_use_fallback("missing_native_tool"))
        self.assertTrue(self.dispatch.should_use_fallback("unknown_agent_type"))
        self.assertTrue(self.dispatch.should_use_fallback("native_ready", agent_type_known=False))

    def test_run_opencode_uses_shell_false_and_dispatcher_command(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch.object(self.dispatch.subprocess, "run", return_value=completed) as run:
            self.dispatch.run_opencode(ROOT, "prompt", 7, executable="opencode")
        _args, kwargs = run.call_args
        self.assertEqual(kwargs["shell"], False)
        self.assertEqual(kwargs["timeout"], 7)
        self.assertTrue(_args[0][0].lower().endswith(("opencode", "opencode.cmd", "opencode.exe")))
        self.assertIn("queen-codex-dispatch", _args[0])
        self.assertIn("--format", _args[0])
        self.assertIn("json", _args[0])


if __name__ == "__main__":
    unittest.main()
