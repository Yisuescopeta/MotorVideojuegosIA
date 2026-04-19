from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from engine.agent.provider import AgentProviderResponse, FakeLLMProvider, LLMProvider
from engine.agent.store import AgentSessionStore
from engine.agent.tools import AgentToolContext, AgentToolRegistry
from engine.agent.types import (
    AgentActionRequest,
    AgentActionStatus,
    AgentEvent,
    AgentEventKind,
    AgentMessage,
    AgentMessageRole,
    AgentPermissionMode,
    AgentSession,
    AgentToolCall,
    new_id,
    utc_now_iso,
)

if TYPE_CHECKING:
    from engine.api import EngineAPI


class AgentSessionService:
    def __init__(
        self,
        *,
        api: "EngineAPI | None" = None,
        project_root: str | Path | None = None,
        provider: LLMProvider | None = None,
        tool_registry: AgentToolRegistry | None = None,
    ) -> None:
        self.api = api
        self.project_root = self._resolve_project_root(project_root)
        self.provider = provider if provider is not None else FakeLLMProvider()
        self.tools = tool_registry if tool_registry is not None else AgentToolRegistry()
        self.store = AgentSessionStore(self.project_root)

    def _resolve_project_root(self, project_root: str | Path | None) -> Path:
        if project_root is not None:
            return Path(project_root).expanduser().resolve()
        if self.api is not None and getattr(self.api, "project_service", None) is not None:
            return self.api.project_service.project_root.resolve()
        return Path.cwd().resolve()

    def create_session(
        self,
        *,
        permission_mode: str = AgentPermissionMode.CONFIRM_ACTIONS.value,
        title: str = "",
        provider_id: str = "fake",
    ) -> dict[str, Any]:
        mode = AgentPermissionMode(str(permission_mode))
        session = AgentSession(
            session_id=new_id("agent-session"),
            permission_mode=mode,
            provider_id=provider_id or self.provider.provider_id,
            title=title or "Agent Session",
        )
        self._append_event(session, AgentEventKind.SESSION_CREATED, {"permission_mode": mode.value})
        self.store.save_session(session)
        return session.to_dict()

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self.store.load_session(session_id).to_dict()

    def list_tools(self) -> list[dict[str, Any]]:
        return self.tools.list_specs()

    def send_message(self, session_id: str, message: str) -> dict[str, Any]:
        session = self.store.load_session(session_id)
        if session.cancelled:
            raise RuntimeError("Agent session is cancelled.")
        content = str(message or "").strip()
        if not content:
            raise ValueError("message is required")

        slash_response = self._handle_slash_command(session, content)
        if slash_response is not None:
            self.store.save_session(session)
            return slash_response

        session.messages.append(AgentMessage(new_id("msg"), AgentMessageRole.USER, content))
        self._append_event(session, AgentEventKind.MESSAGE_ADDED, {"role": AgentMessageRole.USER.value})

        provider_response = self.provider.generate(session, self.list_tools())
        session.messages.append(
            AgentMessage(
                new_id("msg"),
                AgentMessageRole.ASSISTANT,
                provider_response.content,
                tool_calls=list(provider_response.tool_calls),
            )
        )
        self._append_event(session, AgentEventKind.MESSAGE_ADDED, {"role": AgentMessageRole.ASSISTANT.value})
        self._process_tool_calls(session, provider_response)
        session.updated_at = utc_now_iso()
        self.store.save_session(session)
        return session.to_dict()

    def approve_action(self, session_id: str, action_id: str, approved: bool) -> dict[str, Any]:
        session = self.store.load_session(session_id)
        action = next((item for item in session.pending_actions if item.action_id == action_id), None)
        if action is None:
            raise KeyError(f"Agent action not found: {action_id}")
        if action.status != AgentActionStatus.PENDING:
            raise RuntimeError(f"Agent action is not pending: {action_id}")

        action.resolved_at = utc_now_iso()
        if not approved:
            action.status = AgentActionStatus.REJECTED
            session.messages.append(
                AgentMessage(new_id("msg"), AgentMessageRole.ASSISTANT, f"Action rejected: {action.tool_call.tool_name}")
            )
            self._append_event(session, AgentEventKind.ACTION_REJECTED, {"action_id": action_id})
            session.updated_at = utc_now_iso()
            self.store.save_session(session)
            return session.to_dict()

        action.status = AgentActionStatus.APPROVED
        self._append_event(session, AgentEventKind.ACTION_APPROVED, {"action_id": action_id})
        result = self._execute_tool_call(action.tool_call)
        action.result = result
        action.status = AgentActionStatus.EXECUTED if result.success else AgentActionStatus.FAILED
        session.messages.append(
            AgentMessage(
                new_id("msg"),
                AgentMessageRole.TOOL,
                result.output if result.success else result.error,
                tool_result=result,
            )
        )
        session.updated_at = utc_now_iso()
        self.store.save_session(session)
        return session.to_dict()

    def cancel_session(self, session_id: str) -> dict[str, Any]:
        session = self.store.load_session(session_id)
        session.cancelled = True
        self._append_event(session, AgentEventKind.SESSION_CANCELLED, {})
        session.updated_at = utc_now_iso()
        self.store.save_session(session)
        return session.to_dict()

    def _handle_slash_command(self, session: AgentSession, content: str) -> dict[str, Any] | None:
        if not content.startswith("/"):
            return None
        parts = content.split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        if command == "/help":
            body = "Commands: /help, /status, /permissions <confirm_actions|full_access>, /clear, /tools."
        elif command == "/status":
            pending_count = len([action for action in session.pending_actions if action.status == AgentActionStatus.PENDING])
            body = f"Session {session.session_id} | mode={session.permission_mode.value} | pending={pending_count}"
        elif command == "/permissions":
            if arg:
                session.permission_mode = AgentPermissionMode(arg)
                body = f"Permission mode set to {session.permission_mode.value}."
            else:
                body = f"Permission mode: {session.permission_mode.value}."
        elif command == "/clear":
            session.messages.clear()
            session.pending_actions.clear()
            body = "Session messages and pending actions cleared."
        elif command == "/tools":
            body = "\n".join(tool["name"] for tool in self.list_tools())
        else:
            body = f"Unknown command: {command}"
        session.messages.append(AgentMessage(new_id("msg"), AgentMessageRole.USER, content))
        session.messages.append(AgentMessage(new_id("msg"), AgentMessageRole.ASSISTANT, body))
        session.updated_at = utc_now_iso()
        return session.to_dict()

    def _process_tool_calls(self, session: AgentSession, response: AgentProviderResponse) -> None:
        for call in response.tool_calls:
            if session.permission_mode == AgentPermissionMode.CONFIRM_ACTIONS and self.tools.requires_confirmation(call.tool_name):
                preview = self._preview_tool_call(call)
                action = AgentActionRequest(
                    action_id=new_id("agent-action"),
                    tool_call=call,
                    reason=f"{call.tool_name} requires confirmation in confirm_actions mode.",
                    preview=preview,
                )
                session.pending_actions.append(action)
                session.messages.append(
                    AgentMessage(
                        new_id("msg"),
                        AgentMessageRole.ASSISTANT,
                        f"Action pending approval: {call.tool_name} ({action.action_id})",
                    )
                )
                self._append_event(
                    session,
                    AgentEventKind.ACTION_REQUESTED,
                    {"action_id": action.action_id, "tool_name": call.tool_name},
                )
                continue
            result = self._execute_tool_call(call)
            session.messages.append(
                AgentMessage(
                    new_id("msg"),
                    AgentMessageRole.TOOL,
                    result.output if result.success else result.error,
                    tool_result=result,
                )
            )
            self._append_event(
                session,
                AgentEventKind.TOOL_CALLED,
                {"tool_name": call.tool_name, "success": result.success},
            )

    def _tool_context(self) -> AgentToolContext:
        return AgentToolContext(project_root=self.project_root, api=self.api)

    def _preview_tool_call(self, call: AgentToolCall) -> str:
        try:
            return self.tools.preview(call, self._tool_context())
        except Exception as exc:
            return f"Preview failed: {exc}"

    def _execute_tool_call(self, call: AgentToolCall):
        return self.tools.execute(call, self._tool_context())

    def _append_event(self, session: AgentSession, kind: AgentEventKind, data: dict[str, Any]) -> None:
        event = AgentEvent(new_id("event"), kind, data=data)
        session.events.append(event)
        self.store.append_event(session.session_id, event)
