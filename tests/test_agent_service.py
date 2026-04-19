import json
import tempfile
import unittest
from pathlib import Path

from engine.agent import AgentActionStatus, AgentPermissionMode, AgentProviderRequest, AgentProviderResponse, AgentSessionService
from engine.agent.types import AgentToolCall, new_id
from engine.api import EngineAPI


def _make_project(root: Path) -> Path:
    project = root / "AgentProject"
    project.mkdir(parents=True, exist_ok=True)
    (project / "project.json").write_text(
        json.dumps(
            {
                "name": "AgentProject",
                "version": 2,
                "engine_version": "2026.03",
                "template": "empty",
                "paths": {
                    "assets": "assets",
                    "levels": "levels",
                    "prefabs": "prefabs",
                    "scripts": "scripts",
                    "settings": "settings",
                    "meta": ".motor/meta",
                    "build": ".motor/build",
                },
            }
        ),
        encoding="utf-8",
    )
    for name in ("assets", "levels", "prefabs", "scripts", "settings"):
        (project / name).mkdir(exist_ok=True)
    return project


class AgentSessionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.project = _make_project(self.root)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_confirm_actions_creates_pending_write_and_approval_applies(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.CONFIRM_ACTIONS.value)

        updated = service.send_message(session["session_id"], "write notes/todo.txt :: hello")

        pending = [item for item in updated["pending_actions"] if item["status"] == AgentActionStatus.PENDING.value]
        self.assertEqual(len(pending), 1)
        self.assertIn("notes/todo.txt", pending[0]["preview"])
        self.assertFalse((self.project / "notes" / "todo.txt").exists())

        approved = service.approve_action(session["session_id"], pending[0]["action_id"], True)

        self.assertTrue((self.project / "notes" / "todo.txt").exists())
        self.assertEqual((self.project / "notes" / "todo.txt").read_text(encoding="utf-8"), "hello")
        self.assertEqual(approved["pending_actions"][0]["status"], AgentActionStatus.EXECUTED.value)
        self.assertTrue((self.project / ".motor" / "agent_state" / "audit.jsonl").exists())

    def test_full_access_executes_write_without_confirmation(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        updated = service.send_message(session["session_id"], "write out.txt :: full")

        self.assertEqual(updated["pending_actions"], [])
        self.assertEqual((self.project / "out.txt").read_text(encoding="utf-8"), "full")
        self.assertEqual(updated["messages"][-1]["role"], "assistant")
        self.assertIn("Tool result received for write_file", updated["messages"][-1]["content"])

    def test_tool_result_reenters_provider_until_final_response(self) -> None:
        (self.project / "notes.txt").write_text("context", encoding="utf-8")
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        updated = service.send_message(session["session_id"], "read notes.txt")

        roles = [message["role"] for message in updated["messages"]]
        self.assertEqual(roles, ["user", "assistant", "tool", "assistant"])
        self.assertIn("Tool result received for read_file", updated["messages"][-1]["content"])
        provider_events = [event for event in updated["events"] if event["kind"] == "provider_started"]
        self.assertEqual(len(provider_events), 2)

    def test_rejecting_pending_action_resumes_with_tool_result(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.CONFIRM_ACTIONS.value)
        updated = service.send_message(session["session_id"], "write notes/reject.txt :: no")
        pending = [item for item in updated["pending_actions"] if item["status"] == AgentActionStatus.PENDING.value]

        rejected = service.approve_action(session["session_id"], pending[0]["action_id"], False)

        self.assertFalse((self.project / "notes" / "reject.txt").exists())
        self.assertEqual(rejected["pending_actions"][0]["status"], AgentActionStatus.REJECTED.value)
        tool_messages = [message for message in rejected["messages"] if message["role"] == "tool"]
        self.assertFalse(tool_messages[-1]["tool_result"]["success"])
        self.assertIn("Action rejected by user", tool_messages[-1]["tool_result"]["error"])
        self.assertEqual(rejected["messages"][-1]["role"], "assistant")
        self.assertIn("Tool write_file failed", rejected["messages"][-1]["content"])

    def test_new_user_message_is_blocked_while_action_is_pending(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.CONFIRM_ACTIONS.value)
        service.send_message(session["session_id"], "write notes/pending.txt :: wait")

        with self.assertRaises(RuntimeError):
            service.send_message(session["session_id"], "read project.json")

    def test_session_is_versioned_and_writes_per_session_event_log(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        updated = service.send_message(session["session_id"], "list .")

        self.assertEqual(updated["schema_version"], 2)
        event_log = self.project / ".motor" / "agent_state" / "events" / f"{session['session_id']}.jsonl"
        self.assertTrue(event_log.exists())
        content = event_log.read_text(encoding="utf-8")
        self.assertIn("provider_started", content)
        self.assertIn("tool_result_added", content)

    def test_iteration_limit_stops_looping_provider(self) -> None:
        class LoopingProvider:
            provider_id = "loop"

            def run_turn(self, request: AgentProviderRequest, config) -> AgentProviderResponse:
                call = AgentToolCall(new_id("tool"), "read_file", {"path": "missing.txt"})
                return AgentProviderResponse.from_text("loop", [call], stop_reason="tool_use", provider_id=self.provider_id)

        service = AgentSessionService(project_root=self.project, provider=LoopingProvider(), max_iterations_per_turn=2)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value, provider_id="loop")

        updated = service.send_message(session["session_id"], "loop")

        self.assertEqual(updated["messages"][-1]["role"], "assistant")
        self.assertIn("iteration limit", updated["messages"][-1]["content"])
        self.assertTrue(any(event["kind"] == "turn_limit_reached" for event in updated["events"]))

    def test_path_outside_project_is_blocked(self) -> None:
        outside = self.root / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        updated = service.send_message(session["session_id"], f"read {outside.as_posix()}")

        tool_messages = [message for message in updated["messages"] if message["role"] == "tool"]
        self.assertFalse(tool_messages[-1]["tool_result"]["success"])
        self.assertIn("outside project root", tool_messages[-1]["tool_result"]["error"])

    def test_protected_project_paths_are_blocked(self) -> None:
        (self.project / ".git").mkdir()
        (self.project / ".git" / "config").write_text("[remote]\n", encoding="utf-8")
        reference_dir = self.project / "Claude Code"
        reference_dir.mkdir()
        (reference_dir / "README.md").write_text("reference", encoding="utf-8")
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        git_result = service.send_message(session["session_id"], "read .git/config")
        reference_result = service.send_message(session["session_id"], "read Claude Code/README.md")

        git_tool = [message for message in git_result["messages"] if message["role"] == "tool"][-1]
        reference_tool = [message for message in reference_result["messages"] if message["role"] == "tool"][-1]
        self.assertFalse(git_tool["tool_result"]["success"])
        self.assertFalse(reference_tool["tool_result"]["success"])
        self.assertIn("protected project path", git_tool["tool_result"]["error"])
        self.assertIn("protected project path", reference_tool["tool_result"]["error"])

    def test_engine_api_exposes_agent_surface_and_fake_tool_call(self) -> None:
        api = EngineAPI(project_root=self.project.as_posix(), global_state_dir=(self.root / "global").as_posix())
        try:
            created = api.create_agent_session(permission_mode="full_access")
            self.assertTrue(created["success"])
            session_id = created["data"]["session_id"]
            self.assertTrue(any(tool["name"] == "engine_capabilities" for tool in api.list_agent_tools()))

            result = api.send_agent_message(session_id, "capabilities")

            self.assertTrue(result["success"])
            tool_messages = [message for message in result["data"]["messages"] if message["role"] == "tool"]
            self.assertTrue(tool_messages)
            self.assertTrue(tool_messages[-1]["tool_result"]["success"])
        finally:
            api.shutdown()


if __name__ == "__main__":
    unittest.main()
