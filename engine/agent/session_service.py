from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from engine.agent.AgentSlashCommands import AgentSlashCommandRegistry
from engine.agent.credentials import (
    AgentCredentialStore,
    AgentProviderLoginService,
    AgentProviderSettingsStore,
)
from engine.agent.engine_port import AgentEnginePort, EngineAPIAgentEnginePort
from engine.agent.memory import AgentCompactionService, AgentMemoryStore
from engine.agent.provider import (
    AgentProviderResolver,
    FakeLLMProvider,
    LLMProvider,
    OpenAIProvider,
    create_opencode_go_provider,
)
from engine.agent.runtime import AgentRuntime
from engine.agent.store import AgentSessionStore
from engine.agent.tools import AgentToolContext, AgentToolRegistry
from engine.agent.types import (
    AgentActionStatus,
    AgentEvent,
    AgentEventKind,
    AgentPermissionMode,
    AgentRuntimeConfig,
    AgentSession,
    AgentTurnStatus,
    new_id,
    utc_now_iso,
)

if TYPE_CHECKING:
    from engine.api import EngineAPI

SECRET_INPUT_PATTERN = re.compile(r"\b(sk-[A-Za-z0-9_\-]{12,}|[A-Za-z0-9_\-]{32,})\b")


class AgentSessionService:
    def __init__(
        self,
        *,
        api: "EngineAPI | None" = None,
        project_root: str | Path | None = None,
        provider: LLMProvider | None = None,
        tool_registry: AgentToolRegistry | None = None,
        engine_port: AgentEnginePort | None = None,
        global_state_dir: str | Path | None = None,
        max_iterations_per_turn: int = 8,
    ) -> None:
        self.api = api
        self.project_root = self._resolve_project_root(project_root)
        self.global_state_dir = self._resolve_global_state_dir(global_state_dir)
        self.credential_store = AgentCredentialStore(self.global_state_dir)
        self.provider_settings_store = AgentProviderSettingsStore(self.project_root)
        self.login_service = AgentProviderLoginService(
            credential_store=self.credential_store,
            settings_store=self.provider_settings_store,
        )
        self.provider = provider if provider is not None else FakeLLMProvider()
        providers: list[LLMProvider] = [
            self.provider,
            FakeLLMProvider(),
            OpenAIProvider(api_key_getter=lambda: self.login_service.api_key("openai")),
            create_opencode_go_provider(
                api_key_getter=lambda: self.login_service.api_key("opencode-go"),
                base_url_getter=lambda: self.login_service.default_provider_settings().get("base_url", ""),
            ),
        ]
        deduped: dict[str, LLMProvider] = {}
        for item in providers:
            deduped[item.provider_id] = item
        self.provider_resolver = AgentProviderResolver(list(deduped.values()))
        self.tools = tool_registry if tool_registry is not None else AgentToolRegistry()
        self.engine_port = engine_port if engine_port is not None else (
            EngineAPIAgentEnginePort(api) if api is not None else None
        )
        self.store = AgentSessionStore(self.project_root)
        self.memory_store = AgentMemoryStore(self.project_root)
        self.compaction = AgentCompactionService(self.memory_store)
        self.runtime = AgentRuntime(
            tools=self.tools,
            provider_resolver=self.provider_resolver,
            tool_context_factory=self._tool_context,
            append_event=self._append_event,
            max_iterations_per_turn=max_iterations_per_turn,
        )
        self.slash_commands = AgentSlashCommandRegistry(self)

    def _resolve_project_root(self, project_root: str | Path | None) -> Path:
        if project_root is not None:
            return Path(project_root).expanduser().resolve()
        if self.api is not None and getattr(self.api, "project_service", None) is not None:
            return self.api.project_service.project_root.resolve()
        return Path.cwd().resolve()

    def _resolve_global_state_dir(self, global_state_dir: str | Path | None) -> Path:
        if global_state_dir is not None:
            return Path(global_state_dir).expanduser().resolve()
        if self.api is not None and getattr(self.api, "project_service", None) is not None:
            return self.api.project_service.global_state_dir.resolve()
        env_override = __import__("os").environ.get("MOTORVIDEOJUEGOSIA_HOME", "").strip()
        if env_override:
            return Path(env_override).expanduser().resolve()
        return (Path.home() / ".motorvideojuegosia").resolve()

    def create_session(
        self,
        *,
        permission_mode: str = AgentPermissionMode.CONFIRM_ACTIONS.value,
        title: str = "",
        provider_id: str = "fake",
        model: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        mode = AgentPermissionMode(str(permission_mode))
        settings = self.provider_settings_store.load()
        selected_provider_id = provider_id or self.provider.provider_id
        if selected_provider_id in {"default", "project_default"}:
            selected_provider_id = str(settings.get("default_provider_id", "fake") or "fake")
        if selected_provider_id == "fake" and selected_provider_id not in self.provider_resolver.list_provider_ids():
            selected_provider_id = self.provider.provider_id
        provider = self.provider_resolver.resolve(selected_provider_id)
        provider_metadata = self._provider_metadata(provider.provider_id)
        configured_model = model or (
            str(settings.get("model", "")) if provider.provider_id == settings.get("default_provider_id") else ""
        )
        runtime_config = AgentRuntimeConfig(
            provider_id=provider.provider_id,
            max_iterations_per_turn=self.runtime.max_iterations_per_turn,
            model=configured_model or str(provider_metadata.get("default_model", "")),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=bool(stream or (provider.provider_id == settings.get("default_provider_id") and settings.get("stream"))),
        )
        if provider.provider_id == "openai" and provider_metadata.get("auth_status") == "configured" and not provider_metadata.get("runtime_ready", False):
            raise RuntimeError(
                "OpenAI provider detected Codex-managed authentication, but no reusable API key bridge is available yet. Complete Codex login again or configure an API key."
            )
        if hasattr(provider, "validate_runtime_config"):
            getattr(provider, "validate_runtime_config")(runtime_config)
        session = AgentSession(
            session_id=new_id("agent-session"),
            permission_mode=mode,
            provider_id=provider.provider_id,
            title=title or "Agent Session",
            runtime_config=runtime_config,
            provider_metadata=provider_metadata,
        )
        self._append_event(
            session,
            AgentEventKind.SESSION_CREATED,
            {"permission_mode": mode.value, "provider": provider_metadata},
        )
        self.store.save_session(session)
        return session.to_dict()

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self.store.load_session(session_id).to_dict()

    def list_tools(self) -> list[dict[str, Any]]:
        return self.tools.list_specs()

    def list_slash_commands(self) -> list[dict[str, Any]]:
        return self.slash_commands.list_commands()

    def suggest_slash_commands(self, input_text: str) -> list[dict[str, Any]]:
        return self.slash_commands.suggest(input_text)

    def is_slash_command_query(self, input_text: str) -> bool:
        return self.slash_commands.is_command_query(input_text)

    def list_providers(self) -> list[dict[str, object]]:
        return [self._provider_metadata(str(provider["provider_id"])) for provider in self.provider_resolver.list_provider_metadata()]

    def login_provider(
        self,
        provider_id: str,
        *,
        api_key: str,
        base_url: str = "",
        model: str = "",
        credential_source: str = "user_local",
        device_auth: bool = False,
    ) -> dict[str, Any]:
        result = self.login_service.login(
            provider_id,
            api_key=api_key,
            base_url=base_url,
            model=model,
            credential_source=credential_source,
            device_auth=device_auth,
        )
        return {**result, "provider": self._provider_metadata(str(result["provider"]["provider_id"]))}

    def logout_provider(self, provider_id: str) -> dict[str, Any]:
        result = self.login_service.logout(provider_id)
        return {**result, "provider": self._provider_metadata(str(result["provider"]["provider_id"]))}

    def get_provider_status(self, provider_id: str = "") -> dict[str, Any]:
        if provider_id:
            return self._provider_metadata(provider_id)
        settings = self.provider_settings_store.load()
        return {
            "default_provider_id": settings.get("default_provider_id", "fake"),
            "settings": settings,
            "providers": self.list_providers(),
        }

    def prepare_managed_provider_login(self, provider_id: str, *, device_auth: bool = False) -> dict[str, Any]:
        self.provider_resolver.resolve(provider_id)
        prepared = self.login_service.prepare_managed_login(provider_id, device_auth=device_auth)
        self.login_service.set_default_provider(provider_id)
        provider = self._provider_metadata(provider_id)
        message = (
            "Complete the Codex device login flow and return to the editor when it finishes."
            if device_auth
            else "Complete the Codex login flow in the opened window and then return to the editor."
        )
        return {
            "action": "launch_codex_login",
            "provider_id": provider_id,
            "provider": provider,
            "command": prepared["command"],
            "codex_home": prepared["codex_home"],
            "device_auth": prepared["device_auth"],
            "message": message,
        }

    def set_default_provider(self, provider_id: str, *, model: str = "", base_url: str = "") -> dict[str, Any]:
        self.provider_resolver.resolve(provider_id)
        settings = self.login_service.set_default_provider(provider_id, model=model, base_url=base_url)
        return {"settings": settings, "provider": self._provider_metadata(provider_id)}

    def send_message(self, session_id: str, message: str) -> dict[str, Any]:
        session = self.store.load_session(session_id)
        if session.cancelled:
            raise RuntimeError("Agent session is cancelled.")
        content = str(message or "").strip()
        if not content:
            raise ValueError("message is required")
        if SECRET_INPUT_PATTERN.search(content):
            raise RuntimeError("Secrets are not accepted in agent chat. Use /login in the panel or CLI --api-key-stdin.")

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

    def compact_session(self, session_id: str) -> dict[str, Any]:
        session = self.store.load_session(session_id)
        result = self.compaction.compact(session)
        session.updated_at = utc_now_iso()
        self._append_event(session, AgentEventKind.MESSAGE_ADDED, {"role": "system", "compaction": result})
        self.store.save_session(session)
        return {"session": session.to_dict(), "compaction": result}

    def get_usage(self, session_id: str) -> dict[str, Any]:
        session = self.store.load_session(session_id)
        total_input = sum(record.input_tokens or 0 for record in session.usage_records)
        total_output = sum(record.output_tokens or 0 for record in session.usage_records)
        total_tokens = sum(record.total_tokens or 0 for record in session.usage_records)
        return {
            "session_id": session.session_id,
            "records": [record.to_dict() for record in session.usage_records],
            "totals": {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "total_tokens": total_tokens,
                "estimated_cost": None,
                "currency": "",
                "status": "unknown" if not session.usage_records else "usage_recorded_cost_unknown",
            },
        }

    def inspect_session(self, session_id: str) -> dict[str, Any]:
        session = self.store.load_session(session_id)
        pending_count = len([action for action in session.pending_actions if action.status == AgentActionStatus.PENDING])
        return {
            "session_id": session.session_id,
            "schema_version": session.schema_version,
            "message_count": len(session.messages),
            "pending_action_count": pending_count,
            "provider_id": session.provider_id,
            "provider_metadata": dict(session.provider_metadata),
            "runtime_config": session.runtime_config.to_dict(),
            "has_memory_summary": bool(session.memory_summary),
            "usage_record_count": len(session.usage_records),
            "active_turn": session.active_turn.to_dict() if session.active_turn is not None else None,
            "suspended_turn": session.suspended_turn.to_dict() if session.suspended_turn is not None else None,
            "cancelled": session.cancelled,
        }

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
        return self.slash_commands.handle(session, content)

    def _tool_context(self) -> AgentToolContext:
        return AgentToolContext(project_root=self.project_root, api=self.api, engine_port=self.engine_port)

    def _handle_login_command(self, session: AgentSession, arg: str) -> dict[str, Any]:
        parts = [item.strip().lower() for item in arg.split() if item.strip()]
        provider_id = parts[0] if parts else "opencode-go"
        mode = parts[1] if len(parts) > 1 else ""
        if provider_id == "status":
            result = self.get_provider_status()
        else:
            provider_id = "opencode-go" if provider_id in {"opencode", "opencodego", "go"} else provider_id
            if provider_id == "openai" and mode not in {"api-key", "apikey", "key"}:
                result = self.prepare_managed_provider_login(
                    provider_id,
                    device_auth=mode in {"device", "device-auth", "code", "headless"},
                )
            else:
                self.provider_resolver.resolve(provider_id)
                status = self._provider_metadata(provider_id)
                result = {
                    "action": "open_login",
                    "provider_id": provider_id,
                    "provider": status,
                    "message": f"Enter API key for {provider_id} in the secure login input.",
                }
        session.updated_at = utc_now_iso()
        return {**session.to_dict(), "command_result": result}

    def _handle_logout_command(self, session: AgentSession, arg: str) -> dict[str, Any]:
        provider_id = arg.strip() or str(self.provider_settings_store.load().get("default_provider_id", "opencode-go"))
        result = self.logout_provider(provider_id)
        session.provider_id = "fake"
        session.runtime_config = AgentRuntimeConfig(
            provider_id="fake",
            max_iterations_per_turn=session.runtime_config.max_iterations_per_turn,
            model="fake",
            stream=False,
            compaction_message_budget=session.runtime_config.compaction_message_budget,
        )
        session.provider_metadata = self._provider_metadata("fake")
        session.updated_at = utc_now_iso()
        return {**session.to_dict(), "command_result": result}

    def _provider_metadata(self, provider_id: str) -> dict[str, object]:
        metadata = self.provider_resolver.metadata_for(provider_id).to_dict()
        if metadata.get("login_supported"):
            status = self.login_service.status(provider_id).to_dict()
            settings = self.provider_settings_store.load()
            metadata.update(status)
            if provider_id == settings.get("default_provider_id"):
                metadata["base_url"] = settings.get("base_url", metadata.get("base_url", ""))
                metadata["default_model"] = settings.get("model", metadata.get("default_model", ""))
        return metadata

    def _append_event(self, session: AgentSession, kind: AgentEventKind, data: dict[str, Any]) -> AgentEvent:
        event = AgentEvent(new_id("event"), kind, data=data)
        session.events.append(event)
        self.store.append_event(session.session_id, event)
        return event

    def get_usage_from_session(self, session: AgentSession) -> dict[str, Any]:
        total_input = sum(record.input_tokens or 0 for record in session.usage_records)
        total_output = sum(record.output_tokens or 0 for record in session.usage_records)
        total_tokens = sum(record.total_tokens or 0 for record in session.usage_records)
        return {
            "session_id": session.session_id,
            "record_count": len(session.usage_records),
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_tokens,
            "estimated_cost": None,
            "currency": "",
            "status": "unknown" if not session.usage_records else "usage_recorded_cost_unknown",
        }


def json_dump_line(data: dict[str, Any]) -> str:
    import json

    return json.dumps(data, ensure_ascii=True, sort_keys=True)
