import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.agent import (
    AgentActionStatus,
    AgentCommandPolicy,
    AgentCommandRequest,
    AgentPermissionMode,
    AgentProviderRequest,
    AgentProviderResolver,
    AgentProviderResponse,
    AgentSessionMigrationError,
    AgentSessionService,
    FakeLLMProvider,
    OpenAICompatibleChatProvider,
    OpenAIProvider,
    ReplayLLMProvider,
)
from engine.agent.memory import AgentMemoryStore
from engine.agent.store import AgentSessionStore
from engine.agent.types import (
    AgentContentBlock,
    AgentEvent,
    AgentEventKind,
    AgentRuntimeConfig,
    AgentToolCall,
    AgentTurnStatus,
    AgentUsageRecord,
    new_id,
)
from engine.ai import get_default_registry
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
        self._env_patch = patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "",
                "OPENCODE_GO_API_KEY": "",
                "CODEX_HOME": "",
            },
            clear=False,
        )
        self._env_patch.start()

    def tearDown(self) -> None:
        self._env_patch.stop()
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

    def test_confirm_actions_handles_multiple_pending_tools_without_transcript_marker(self) -> None:
        provider = ReplayLLMProvider(
            [
                AgentProviderResponse.from_text(
                    "write both",
                    [
                        AgentToolCall("tool-write-one", "write_file", {"path": "one.txt", "content": "one"}),
                        AgentToolCall("tool-write-two", "write_file", {"path": "two.txt", "content": "two"}),
                    ],
                    stop_reason="tool_use",
                    provider_id="replay",
                ),
                AgentProviderResponse.from_text("all done", provider_id="replay"),
            ]
        )
        service = AgentSessionService(project_root=self.project, provider=provider)
        session = service.create_session(permission_mode=AgentPermissionMode.CONFIRM_ACTIONS.value, provider_id="replay")

        updated = service.send_message(session["session_id"], "write files")

        pending = [item for item in updated["pending_actions"] if item["status"] == AgentActionStatus.PENDING.value]
        self.assertEqual(len(pending), 2)
        self.assertEqual([message["role"] for message in updated["messages"]], ["user", "assistant"])
        self.assertNotIn("Action pending approval", json.dumps(updated["messages"]))
        self.assertEqual(len([event for event in updated["events"] if event["kind"] == "provider_started"]), 1)

        first = service.approve_action(session["session_id"], pending[0]["action_id"], True)

        self.assertEqual((self.project / "one.txt").read_text(encoding="utf-8"), "one")
        self.assertFalse((self.project / "two.txt").exists())
        self.assertEqual(len([event for event in first["events"] if event["kind"] == "provider_started"]), 1)
        remaining = [item for item in first["pending_actions"] if item["status"] == AgentActionStatus.PENDING.value]
        self.assertEqual(len(remaining), 1)

        final = service.approve_action(session["session_id"], remaining[0]["action_id"], True)

        self.assertEqual((self.project / "two.txt").read_text(encoding="utf-8"), "two")
        self.assertEqual(len([event for event in final["events"] if event["kind"] == "provider_started"]), 2)
        self.assertEqual([message["role"] for message in final["messages"]], ["user", "assistant", "tool", "tool", "assistant"])
        self.assertEqual(final["messages"][-1]["content"], "all done")

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
        lowercase_reference_dir = self.project / "claude code"
        lowercase_reference_dir.mkdir()
        (lowercase_reference_dir / "README.md").write_text("reference", encoding="utf-8")
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        git_result = service.send_message(session["session_id"], "read .git/config")
        reference_result = service.send_message(session["session_id"], "read Claude Code/README.md")
        lowercase_reference_result = service.send_message(session["session_id"], "read claude code/README.md")

        git_tool = [message for message in git_result["messages"] if message["role"] == "tool"][-1]
        reference_tool = [message for message in reference_result["messages"] if message["role"] == "tool"][-1]
        lowercase_reference_tool = [message for message in lowercase_reference_result["messages"] if message["role"] == "tool"][-1]
        self.assertFalse(git_tool["tool_result"]["success"])
        self.assertFalse(reference_tool["tool_result"]["success"])
        self.assertFalse(lowercase_reference_tool["tool_result"]["success"])
        self.assertIn("protected project path", git_tool["tool_result"]["error"])
        self.assertIn("protected project path", reference_tool["tool_result"]["error"])
        self.assertIn("protected project path", lowercase_reference_tool["tool_result"]["error"])

    def test_session_id_paths_are_validated_before_file_access(self) -> None:
        store = AgentSessionStore(self.project)
        memory_store = AgentMemoryStore(self.project)

        with self.assertRaisesRegex(ValueError, "Invalid agent session id"):
            store.load_session("../x")
        with self.assertRaisesRegex(ValueError, "Invalid agent session id"):
            store.append_event("../x", AgentEvent(new_id("event"), AgentEventKind.MESSAGE_ADDED))
        with self.assertRaisesRegex(ValueError, "Invalid agent session id"):
            memory_store.save_session_summary("../x", "summary")
        with self.assertRaisesRegex(ValueError, "Invalid agent session id"):
            memory_store.append_usage("../x", AgentUsageRecord(new_id("agent-usage"), "fake"))

    def test_edit_file_preview_replace_all_matches_execution(self) -> None:
        target = self.project / "replace.txt"
        target.write_text("alpha beta alpha", encoding="utf-8")
        service = AgentSessionService(project_root=self.project)
        call = AgentToolCall(
            "tool-edit",
            "edit_file",
            {"path": "replace.txt", "old_text": "alpha", "new_text": "omega", "replace_all": True},
        )

        prepared = service.tools.prepare(call, service._tool_context(), require_confirmation=True)

        self.assertIsNone(prepared.blocked_result)
        self.assertIn("-alpha beta alpha", prepared.preview)
        self.assertIn("+omega beta omega", prepared.preview)

    def test_edit_file_rejects_empty_old_text_without_writing(self) -> None:
        target = self.project / "empty-old.txt"
        target.write_text("abc", encoding="utf-8")
        service = AgentSessionService(project_root=self.project)
        call = AgentToolCall(
            "tool-edit-empty",
            "edit_file",
            {"path": "empty-old.txt", "old_text": "", "new_text": "x"},
        )

        prepared = service.tools.prepare(call, service._tool_context(), require_confirmation=False)
        result = service.tools.execute(call, service._tool_context())

        self.assertIsNotNone(prepared.blocked_result)
        self.assertIn("old_text is required", prepared.blocked_result.error)
        self.assertFalse(result.success)
        self.assertEqual(target.read_text(encoding="utf-8"), "abc")

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
            self.assertTrue(any(provider["provider_id"] == "openai" for provider in api.list_agent_providers()))
            self.assertEqual(api.get_agent_usage(session_id)["session_id"], session_id)
            self.assertEqual(api.inspect_agent_session(session_id)["session_id"], session_id)
        finally:
            api.shutdown()

    def test_run_command_policy_accepts_only_allowlisted_profiles(self) -> None:
        policy = AgentCommandPolicy()

        unittest_decision = policy.decide(
            AgentCommandRequest(command="py -m unittest tests.test_agent_service -v", project_root=self.project)
        )
        motor_decision = policy.decide(
            AgentCommandRequest(command="py -m motor doctor --project . --json", project_root=self.project)
        )

        self.assertTrue(unittest_decision.allowed)
        self.assertEqual(unittest_decision.profile, "python_tests")
        self.assertTrue(motor_decision.allowed)
        self.assertEqual(motor_decision.profile, "motor_cli_read")

        blocked = [
            "py -c print(1)",
            "python -c print(1)",
            "powershell Get-ChildItem",
            "cmd /c dir",
            "bash -lc ls",
            "git reset --hard",
            "git clean -fd",
            "git add .",
            "git commit -m x",
            "rm -rf tmp",
            "del /s tmp",
            "Remove-Item tmp",
            "py -m motor doctor --project . --json | more",
            "py -m motor doctor --project . --json > out.txt",
            "py -m motor doctor --project . --json && echo ok",
            "py -m motor doctor --project %USERPROFILE% --json",
            "py -m motor doctor --project Claude Code --json",
        ]
        for command in blocked:
            with self.subTest(command=command):
                self.assertFalse(policy.decide(AgentCommandRequest(command=command, project_root=self.project)).allowed)

    def test_confirm_actions_creates_pending_run_command_for_allowed_profile(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.CONFIRM_ACTIONS.value)

        updated = service.send_message(session["session_id"], "run py -m motor --help")

        pending = [item for item in updated["pending_actions"] if item["status"] == AgentActionStatus.PENDING.value]
        self.assertEqual(len(pending), 1)
        self.assertIn('"profile": "motor_cli_read"', pending[0]["preview"])
        self.assertIn('"argv"', pending[0]["preview"])

    def test_full_access_does_not_bypass_run_command_policy(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        updated = service.send_message(session["session_id"], "run powershell Get-ChildItem")

        tool_messages = [message for message in updated["messages"] if message["role"] == "tool"]
        self.assertFalse(tool_messages[-1]["tool_result"]["success"])
        self.assertIn("Blocked executable", tool_messages[-1]["tool_result"]["error"])

    def test_provider_metadata_marks_fake_as_offline_test_only(self) -> None:
        metadata = FakeLLMProvider.metadata.to_dict()

        self.assertEqual(metadata["provider_kind"], "test")
        self.assertTrue(metadata["offline"])
        self.assertTrue(metadata["test_only"])

    def test_provider_resolver_reports_unknown_provider_explicitly(self) -> None:
        resolver = AgentProviderResolver([FakeLLMProvider()])

        with self.assertRaisesRegex(ValueError, "Available providers: fake"):
            resolver.resolve("missing")

    def test_default_provider_list_includes_openai_as_online_credentialed_provider(self) -> None:
        service = AgentSessionService(project_root=self.project)

        providers = {provider["provider_id"]: provider for provider in service.list_providers()}

        self.assertIn("fake", providers)
        self.assertIn("openai", providers)
        self.assertIn("opencode-go", providers)
        self.assertEqual(providers["openai"]["provider_kind"], "online")
        self.assertTrue(providers["openai"]["online"])
        self.assertTrue(providers["openai"]["requires_credentials"])
        self.assertTrue(providers["openai"]["supports_streaming"])
        self.assertTrue(providers["opencode-go"]["login_supported"])
        self.assertEqual(providers["opencode-go"]["auth_status"], "missing")

    def test_list_agent_tools_exposes_argument_schemas(self) -> None:
        service = AgentSessionService(project_root=self.project)

        tools = {tool["name"]: tool for tool in service.list_tools()}

        read_schema = tools["read_file"]["parameters_schema"]
        write_schema = tools["write_file"]["parameters_schema"]
        self.assertEqual(read_schema["required"], ["path"])
        self.assertIn("path", read_schema["properties"])
        self.assertEqual(write_schema["required"], ["path", "content"])
        self.assertFalse(write_schema["additionalProperties"])

    def test_online_provider_payloads_use_declared_tool_schemas(self) -> None:
        service = AgentSessionService(project_root=self.project)
        tools = service.list_tools()
        request = AgentProviderRequest("session", "turn", [], tools)

        chat_provider = OpenAICompatibleChatProvider(
            provider_id="chat-test",
            base_url="https://example.invalid/v1/chat/completions",
            default_model="chat-model",
            api_key="sk-test",
        )
        chat_payload = chat_provider._build_payload(
            request,
            AgentRuntimeConfig(provider_id="chat-test", model="chat-model"),
            stream=False,
        )

        openai_provider = OpenAIProvider(api_key="sk-test")
        openai_payload = openai_provider._build_payload(
            request,
            AgentRuntimeConfig(provider_id="openai", model="gpt-test"),
            stream=False,
        )

        chat_read = next(tool for tool in chat_payload["tools"] if tool["function"]["name"] == "read_file")
        openai_read = next(tool for tool in openai_payload["tools"] if tool["name"] == "read_file")
        self.assertEqual(chat_read["function"]["parameters"]["required"], ["path"])
        self.assertIn("path", chat_read["function"]["parameters"]["properties"])
        self.assertFalse(chat_read["function"]["parameters"]["additionalProperties"])
        self.assertEqual(openai_read["parameters"]["required"], ["path"])
        self.assertIn("path", openai_read["parameters"]["properties"])
        self.assertFalse(openai_read["parameters"]["additionalProperties"])

    def test_openai_status_reads_codex_managed_auth_from_auth_json(self) -> None:
        global_state_dir = self.root / "global"
        auth_path = global_state_dir / "codex" / "auth.json"
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_text(
            json.dumps(
                {
                    "auth_mode": "chatgpt",
                    "OPENAI_API_KEY": "sk-codex-bridge-test-1234567890",
                    "planType": "plus",
                }
            ),
            encoding="utf-8",
        )

        service = AgentSessionService(project_root=self.project, global_state_dir=global_state_dir)
        status = service.get_provider_status("openai")

        self.assertEqual(status["auth_status"], "configured")
        self.assertEqual(status["credential_source"], "codex_chatgpt")
        self.assertEqual(status["auth_method"], "chatgpt")
        self.assertTrue(status["runtime_ready"])
        self.assertEqual(status["plan_type"], "plus")
        self.assertEqual(service.login_service.api_key("openai"), "sk-codex-bridge-test-1234567890")

    def test_openai_provider_fails_without_credentials(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            service = AgentSessionService(project_root=self.project, global_state_dir=self.root / "global")
            with self.assertRaisesRegex(RuntimeError, "configured credential"):
                service.create_session(provider_id="openai")

    def test_opencode_go_provider_requires_login(self) -> None:
        service = AgentSessionService(project_root=self.project, global_state_dir=self.root / "global")

        with self.assertRaisesRegex(RuntimeError, "requires a configured API key"):
            service.create_session(provider_id="opencode-go")

    def test_login_command_does_not_write_transcript_and_requests_secure_input(self) -> None:
        service = AgentSessionService(project_root=self.project, global_state_dir=self.root / "global")
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        updated = service.send_message(session["session_id"], "/login opencode-go")

        self.assertEqual(updated["messages"], [])
        self.assertEqual(updated["command_result"]["action"], "open_login")
        self.assertEqual(updated["command_result"]["provider_id"], "opencode-go")

    def test_openai_login_command_returns_codex_launch_payload(self) -> None:
        service = AgentSessionService(project_root=self.project, global_state_dir=self.root / "global")
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        with patch.object(service.login_service.codex_auth_store, "_resolve_cli_command", return_value="codex"):
            updated = service.send_message(session["session_id"], "/login openai")

        self.assertEqual(updated["messages"], [])
        self.assertEqual(updated["command_result"]["action"], "launch_codex_login")
        self.assertEqual(updated["command_result"]["provider_id"], "openai")
        self.assertEqual(updated["command_result"]["command"], ["codex", "login"])
        self.assertEqual(service.get_provider_status()["default_provider_id"], "openai")

    def test_openai_device_login_command_returns_device_auth_payload(self) -> None:
        service = AgentSessionService(project_root=self.project, global_state_dir=self.root / "global")
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        with patch.object(service.login_service.codex_auth_store, "_resolve_cli_command", return_value="codex"):
            updated = service.send_message(session["session_id"], "/login openai device")

        self.assertEqual(updated["command_result"]["action"], "launch_codex_login")
        self.assertTrue(updated["command_result"]["device_auth"])
        self.assertEqual(updated["command_result"]["command"], ["codex", "login", "--device-auth"])

    def test_list_slash_commands_exposes_formal_metadata(self) -> None:
        service = AgentSessionService(project_root=self.project)

        commands = {item["name"]: item for item in service.list_slash_commands()}

        self.assertIn("help", commands)
        self.assertIn("status", commands)
        self.assertIn("context", commands)
        self.assertEqual(commands["help"]["category"], "ayuda")
        self.assertIn("ctx", commands["context"]["aliases"])
        self.assertEqual(commands["provider"]["argument_hint"], "[provider_id]")

    def test_suggest_slash_commands_returns_full_catalog_for_single_slash(self) -> None:
        service = AgentSessionService(project_root=self.project)

        suggestions = service.suggest_slash_commands("/")
        names = [item["name"] for item in suggestions]

        self.assertIn("help", names)
        self.assertIn("status", names)
        self.assertIn("verify", names)
        self.assertGreaterEqual(len(names), 10)

    def test_suggest_slash_commands_matches_aliases(self) -> None:
        service = AgentSessionService(project_root=self.project)

        suggestions = service.suggest_slash_commands("/ctx")

        self.assertTrue(suggestions)
        self.assertEqual(suggestions[0]["name"], "context")

    def test_single_slash_command_returns_catalog_message(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        updated = service.send_message(session["session_id"], "/")

        self.assertIn("/help", updated["messages"][-1]["content"])
        self.assertIn("/status", updated["messages"][-1]["content"])

    def test_unknown_slash_command_returns_helpful_error(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        updated = service.send_message(session["session_id"], "/missing")

        self.assertEqual(updated["messages"][-1]["role"], "assistant")
        self.assertIn("Unknown command: /missing", updated["messages"][-1]["content"])

    def test_new_slash_command_creates_new_session_and_cancels_previous(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        updated = service.send_message(session["session_id"], "/new")

        self.assertNotEqual(updated["session_id"], session["session_id"])
        self.assertEqual(updated["command_result"]["action"], "new_session")
        self.assertTrue(service.get_session(session["session_id"])["cancelled"])

    def test_chat_rejects_api_key_like_input_without_persisting_it(self) -> None:
        service = AgentSessionService(project_root=self.project, global_state_dir=self.root / "global")
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)
        secret = "sk-testsecretvalue1234567890"

        with self.assertRaisesRegex(RuntimeError, "Secrets are not accepted"):
            service.send_message(session["session_id"], secret)

        stored = service.get_session(session["session_id"])
        self.assertNotIn(secret, json.dumps(stored))

    def test_login_stores_secret_outside_project_and_sets_default_provider(self) -> None:
        service = AgentSessionService(project_root=self.project, global_state_dir=self.root / "global")
        if not service.credential_store.supports_local_secrets():
            self.skipTest("Local secret storage requires Windows DPAPI")
        secret = "sk-opencodego-test-secret-123456789"

        result = service.login_provider("opencode-go", api_key=secret)
        status = service.get_provider_status("opencode-go")

        self.assertEqual(result["provider"]["auth_status"], "configured")
        self.assertEqual(status["credential_source"], "user_local")
        self.assertEqual(service.login_service.api_key("opencode-go"), secret)
        self.assertFalse((self.project / ".motor" / "agent_state" / "agent_credentials.json").exists())
        self.assertNotIn(secret, (self.root / "global" / "agent_credentials.json").read_text(encoding="utf-8"))
        default_status = service.get_provider_status()
        self.assertEqual(default_status["default_provider_id"], "opencode-go")

    def test_codex_managed_login_sets_default_openai_when_bridge_key_is_available(self) -> None:
        global_state_dir = self.root / "global"
        service = AgentSessionService(project_root=self.project, global_state_dir=global_state_dir)
        auth_path = global_state_dir / "codex" / "auth.json"

        def _fake_run_login(*args, **kwargs):
            auth_path.parent.mkdir(parents=True, exist_ok=True)
            auth_path.write_text(
                json.dumps(
                    {
                        "auth_mode": "chatgpt",
                        "OPENAI_API_KEY": "sk-managed-openai-test-1234567890",
                        "planType": "pro",
                    }
                ),
                encoding="utf-8",
            )
            return service.login_service.codex_auth_store.load_snapshot()

        with patch.object(service.login_service.codex_auth_store, "run_login", side_effect=_fake_run_login):
            result = service.login_provider("openai", api_key="", credential_source="codex_chatgpt")

        self.assertEqual(result["provider"]["credential_source"], "codex_chatgpt")
        self.assertTrue(result["provider"]["runtime_ready"])
        self.assertEqual(result["settings"]["default_provider_id"], "openai")
        self.assertEqual(service.login_service.api_key("openai"), "sk-managed-openai-test-1234567890")

    def test_logout_removes_secret_and_resets_default_provider(self) -> None:
        service = AgentSessionService(project_root=self.project, global_state_dir=self.root / "global")
        if not service.credential_store.supports_local_secrets():
            self.skipTest("Local secret storage requires Windows DPAPI")
        service.login_provider("opencode-go", api_key="sk-opencodego-test-secret-123456789")

        result = service.logout_provider("opencode-go")

        self.assertEqual(result["provider"]["auth_status"], "missing")
        self.assertEqual(service.login_service.api_key("opencode-go"), "")
        self.assertEqual(service.get_provider_status()["default_provider_id"], "fake")

    def test_logout_openai_uses_codex_logout_when_auth_is_codex_managed(self) -> None:
        global_state_dir = self.root / "global"
        auth_path = global_state_dir / "codex" / "auth.json"
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_text(
            json.dumps(
                {
                    "auth_mode": "chatgpt",
                    "OPENAI_API_KEY": "sk-codex-managed-logout-1234567890",
                }
            ),
            encoding="utf-8",
        )
        service = AgentSessionService(project_root=self.project, global_state_dir=global_state_dir)
        service.set_default_provider("openai")

        with patch.object(service.login_service.codex_auth_store, "run_logout") as mock_logout:
            result = service.logout_provider("openai")

        mock_logout.assert_called_once()
        self.assertEqual(result["settings"]["default_provider_id"], "fake")

    def test_openai_compatible_provider_maps_chat_tool_calls_and_usage(self) -> None:
        class StaticChatProvider(OpenAICompatibleChatProvider):
            def _post_json(self, payload):
                return {
                    "model": payload["model"],
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "need file",
                                "tool_calls": [
                                    {
                                        "id": "call-1",
                                        "type": "function",
                                        "function": {"name": "read_file", "arguments": "{\"path\":\"project.json\"}"},
                                    }
                                ],
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
                }

        provider = StaticChatProvider(
            provider_id="chat-test",
            base_url="https://example.invalid/v1/chat/completions",
            default_model="chat-model",
            api_key="sk-test",
        )

        response = provider.run_turn(
            AgentProviderRequest("session", "turn", [], [{"name": "read_file", "description": ""}]),
            AgentRuntimeConfig(provider_id="chat-test", model="chat-model"),
        )

        self.assertEqual(response.provider_id, "chat-test")
        self.assertEqual(response.tool_calls[0].tool_name, "read_file")
        self.assertEqual(response.tool_calls[0].args["path"], "project.json")
        self.assertEqual(response.usage["total_tokens"], 5)

    def test_replay_provider_runs_deterministic_multi_turn_contract(self) -> None:
        (self.project / "notes.txt").write_text("replay context", encoding="utf-8")
        provider = ReplayLLMProvider(
            [
                AgentProviderResponse.from_text(
                    "scripted read",
                    [AgentToolCall("tool-replay-read", "read_file", {"path": "notes.txt"})],
                    stop_reason="tool_use",
                    provider_id="replay",
                ),
                AgentProviderResponse.from_text("scripted final", provider_id="replay"),
            ]
        )
        service = AgentSessionService(project_root=self.project, provider=provider)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value, provider_id="replay")

        updated = service.send_message(session["session_id"], "ignored")

        roles = [message["role"] for message in updated["messages"]]
        self.assertEqual(roles, ["user", "assistant", "tool", "assistant"])
        self.assertEqual(updated["messages"][-1]["content"], "scripted final")
        self.assertEqual(updated["provider_metadata"]["provider_kind"], "test")

    def test_streaming_replay_provider_records_delta_events_and_final_message(self) -> None:
        provider = ReplayLLMProvider(
            [AgentProviderResponse.from_text("streamed final", provider_id="replay")],
            streaming=True,
        )
        service = AgentSessionService(project_root=self.project, provider=provider)
        session = service.create_session(
            permission_mode=AgentPermissionMode.FULL_ACCESS.value,
            provider_id="replay",
            stream=True,
        )

        updated = service.send_message(session["session_id"], "stream")

        self.assertEqual(updated["messages"][-1]["content"], "streamed final")
        event_kinds = [event["kind"] for event in updated["events"]]
        self.assertIn("provider_stream_started", event_kinds)
        self.assertIn("assistant_delta", event_kinds)
        self.assertIn("provider_stream_completed", event_kinds)

    def test_usage_records_are_persisted_when_provider_returns_usage(self) -> None:
        provider = ReplayLLMProvider(
            [
                AgentProviderResponse(
                    [AgentContentBlock.text_block("usage final")],
                    provider_id="replay",
                    model="replay-model",
                    usage={"input_tokens": 3, "output_tokens": 4, "total_tokens": 7},
                )
            ]
        )
        service = AgentSessionService(project_root=self.project, provider=provider)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value, provider_id="replay")

        updated = service.send_message(session["session_id"], "usage")
        usage = service.get_usage(session["session_id"])

        self.assertEqual(len(updated["usage_records"]), 1)
        self.assertEqual(usage["totals"]["input_tokens"], 3)
        self.assertEqual(usage["totals"]["output_tokens"], 4)
        self.assertEqual(usage["totals"]["total_tokens"], 7)
        self.assertEqual(usage["totals"]["status"], "usage_recorded_cost_unknown")

    def test_compact_slash_command_stores_memory_without_protected_paths(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        for index in range(14):
            service.send_message(session["session_id"], f"remember item {index} .git Claude Code")
        compacted = service.send_message(session["session_id"], "/compact")

        self.assertTrue(compacted["memory_summary"])
        self.assertNotIn(".git", compacted["memory_summary"])
        self.assertNotIn("Claude Code", compacted["memory_summary"])
        self.assertTrue((self.project / ".motor" / "agent_state" / "memory" / f"{session['session_id']}.json").exists())

    def test_corrupt_memory_file_reports_error_without_breaking_session(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)
        memory_path = self.project / ".motor" / "agent_state" / "memory" / f"{session['session_id']}.json"
        memory_path.write_text("{not-json", encoding="utf-8")

        updated = service.send_message(session["session_id"], "/memory")

        payload = json.loads(updated["messages"][-1]["content"])
        self.assertEqual(payload["status"], "memory_error")
        self.assertIn("corrupt", payload["memory"]["errors"][0].lower())
        self.assertEqual(memory_path.read_text(encoding="utf-8"), "{not-json")

    def test_full_access_run_command_uses_command_runner_audit(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        updated = service.send_message(session["session_id"], "run py --version")

        tool_messages = [message for message in updated["messages"] if message["role"] == "tool"]
        self.assertTrue(tool_messages[-1]["tool_result"]["success"])
        self.assertIn("command_runner", tool_messages[-1]["tool_result"]["data"])
        self.assertTrue((self.project / ".motor" / "agent_state" / "command_audit.jsonl").exists())

    def test_status_discloses_offline_test_provider(self) -> None:
        service = AgentSessionService(project_root=self.project)
        session = service.create_session(permission_mode=AgentPermissionMode.FULL_ACCESS.value)

        updated = service.send_message(session["session_id"], "/status")

        self.assertIn("kind=test", updated["messages"][-1]["content"])
        self.assertIn("test_only=True", updated["messages"][-1]["content"])

    def test_agent_editor_capability_does_not_promote_from_runtime_as_core_api(self) -> None:
        capability = get_default_registry().get("agent:editor_panel")

        self.assertIsNotNone(capability)
        self.assertNotIn("EngineAPI.from_runtime", capability.api_methods)
        self.assertNotIn("EditorLiveAgentEnginePort", capability.api_methods)
        self.assertIn("AgentAPI.get_agent_session", capability.api_methods)

    def test_legacy_session_migrates_to_v2_with_backup_and_event_log(self) -> None:
        store = AgentSessionStore(self.project)
        legacy_id = "agent-session-aaaaaaaaaaaa"
        legacy_path = store.sessions_dir / f"{legacy_id}.json"
        legacy_path.write_text(
            json.dumps(
                {
                    "session_id": legacy_id,
                    "permission_mode": "confirm_actions",
                    "provider_id": "fake",
                    "messages": [{"message_id": "msg-1", "role": "user", "content": "read project.json"}],
                    "pending_actions": [],
                    "events": [],
                }
            ),
            encoding="utf-8",
        )

        session = store.load_session(legacy_id)

        self.assertEqual(session.schema_version, 2)
        self.assertTrue((store.sessions_dir / f"{legacy_id}.legacy-v1.bak").exists())
        self.assertTrue(session.messages[0].content_blocks)
        audit = store.audit_path.read_text(encoding="utf-8")
        self.assertIn("session_migrated", audit)

    def test_legacy_pending_action_migrates_to_suspended_turn(self) -> None:
        store = AgentSessionStore(self.project)
        legacy_id = "agent-session-bbbbbbbbbbbb"
        legacy_path = store.sessions_dir / f"{legacy_id}.json"
        legacy_path.write_text(
            json.dumps(
                {
                    "session_id": legacy_id,
                    "permission_mode": "confirm_actions",
                    "provider_id": "fake",
                    "messages": [],
                    "pending_actions": [
                        {
                            "action_id": "action-1",
                            "tool_call": {
                                "tool_call_id": "tool-1",
                                "tool_name": "write_file",
                                "args": {"path": "out.txt", "content": "x"},
                            },
                            "reason": "legacy approval",
                            "preview": "preview",
                            "status": "pending",
                        }
                    ],
                    "events": [],
                }
            ),
            encoding="utf-8",
        )

        session = store.load_session(legacy_id)

        self.assertIsNotNone(session.active_turn)
        self.assertIsNotNone(session.suspended_turn)
        self.assertEqual(session.active_turn.status, AgentTurnStatus.SUSPENDED)
        self.assertEqual(session.suspended_turn.action_id, "action-1")
        self.assertEqual(session.pending_actions[0].turn_id, session.suspended_turn.turn_id)

    def test_corrupt_legacy_session_is_not_overwritten(self) -> None:
        store = AgentSessionStore(self.project)
        legacy_id = "agent-session-cccccccccccc"
        legacy_path = store.sessions_dir / f"{legacy_id}.json"
        raw = "{not-json"
        legacy_path.write_text(raw, encoding="utf-8")

        with self.assertRaises(AgentSessionMigrationError):
            store.load_session(legacy_id)

        self.assertEqual(legacy_path.read_text(encoding="utf-8"), raw)
        self.assertFalse((store.sessions_dir / f"{legacy_id}.legacy-v1.bak").exists())


if __name__ == "__main__":
    unittest.main()
