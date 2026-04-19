from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from engine.agent.engine_port import AgentEnginePort, EngineAPIAgentEnginePort
from engine.agent.provider import AgentProviderResolver, FakeLLMProvider, LLMProvider
from engine.agent.runtime import AgentRuntime
from engine.agent.store import AgentSessionStore
from engine.agent.tools import AgentToolContext, AgentToolRegistry
from engine.agent.types import (
    AgentActionStatus,
    AgentEvent,
    AgentEventKind,
    AgentMessage,
    AgentMessageRole,
    AgentPermissionMode,
    AgentRuntimeConfig,
    AgentSession,
    AgentTurnStatus,
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
        engine_port: AgentEnginePort | None = None,
        max_iterations_per_turn: int = 8,
    ) -> None:
        self.api = api
        self.project_root = self._resolve_project_root(project_root)
        self.provider = provider if provider is not None else FakeLLMProvider()
        self.provider_resolver = AgentProviderResolver([self.provider])
        self.tools = tool_registry if tool_registry is not None else AgentToolRegistry()
        self.engine_port = engine_port if engine_port is not None else (
            EngineAPIAgentEnginePort(api) if api is not None else None
        )
        self.store = AgentSessionStore(self.project_root)
        self.runtime = AgentRuntime(
            tools=self.tools,
            provider_resolver=self.provider_resolver,
            tool_context_factory=self._tool_context,
            append_event=self._append_event,
            max_iterations_per_turn=max_iterations_per_turn,
        )

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
            runtime_config=AgentRuntimeConfig(
                provider_id=provider_id or self.provider.provider_id,
                max_iterations_per_turn=self.runtime.max_iterations_per_turn,
            ),
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
        if any(action.status == AgentActionStatus.PENDING for action in session.pending_actions):
            raise RuntimeError("Resolve pending agent actions before sending a new message.")

        self.runtime.start_turn(session, content)
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
            self.runtime.resolve_action(session, action, False)
        else:
            self.runtime.resolve_action(session, action, True)
        session.updated_at = utc_now_iso()
        self.store.save_session(session)
        return session.to_dict()

    def cancel_session(self, session_id: str) -> dict[str, Any]:
        session = self.store.load_session(session_id)
        session.cancelled = True
        if session.active_turn is not None:
            session.active_turn.status = AgentTurnStatus.CANCELLED
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
        session.active_turn = None
        session.suspended_turn = None
        session.updated_at = utc_now_iso()
        return session.to_dict()

    def _tool_context(self) -> AgentToolContext:
        return AgentToolContext(project_root=self.project_root, api=self.api, engine_port=self.engine_port)

    def _append_event(self, session: AgentSession, kind: AgentEventKind, data: dict[str, Any]) -> None:
        event = AgentEvent(new_id("event"), kind, data=data)
        session.events.append(event)
        self.store.append_event(session.session_id, event)
