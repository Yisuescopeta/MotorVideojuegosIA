from __future__ import annotations

from typing import Any

from engine.agent import AgentSessionService
from engine.api._context import EngineAPIComponent
from engine.api.types import ActionResult


class AgentAPI(EngineAPIComponent):
    """Experimental clean-room agent surface exposed through EngineAPI."""

    def _agent_service(self) -> AgentSessionService:
        service = getattr(self.api, "_agent_session_service", None)
        if service is None:
            project_root = self.project_service.project_root if self.project_service is not None else self.api._project_root
            service = AgentSessionService(api=self.api, project_root=project_root)
            setattr(self.api, "_agent_session_service", service)
        return service

    def create_agent_session(
        self,
        permission_mode: str = "confirm_actions",
        title: str = "",
        provider_id: str = "fake",
        model: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> ActionResult:
        data = self._agent_service().create_session(
            permission_mode=permission_mode,
            title=title,
            provider_id=provider_id,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )
        return self.ok("Agent session created", data)

    def send_agent_message(self, session_id: str, message: str) -> ActionResult:
        data = self._agent_service().send_message(session_id, message)
        return self.ok("Agent message processed", data)

    def get_agent_session(self, session_id: str) -> dict[str, Any]:
        return self._agent_service().get_session(session_id)

    def approve_agent_action(self, session_id: str, action_id: str, approved: bool) -> ActionResult:
        data = self._agent_service().approve_action(session_id, action_id, approved)
        return self.ok("Agent action resolved", data)

    def cancel_agent_session(self, session_id: str) -> ActionResult:
        data = self._agent_service().cancel_session(session_id)
        return self.ok("Agent session cancelled", data)

    def list_agent_tools(self) -> list[dict[str, Any]]:
        return self._agent_service().list_tools()

    def list_agent_providers(self) -> list[dict[str, object]]:
        return self._agent_service().list_providers()

    def login_agent_provider(
        self,
        provider_id: str,
        credential_source: str = "user_local",
        base_url: str = "",
        model: str = "",
        api_key: str = "",
        device_auth: bool = False,
    ) -> ActionResult:
        if credential_source not in {"user_local", "codex_chatgpt", "codex_api_key"}:
            return self.fail(f"Unsupported agent credential source: {credential_source}")
        data = self._agent_service().login_provider(
            provider_id,
            api_key=api_key,
            base_url=base_url,
            model=model,
            credential_source=credential_source,
            device_auth=device_auth,
        )
        return self.ok("Agent provider logged in", data)

    def logout_agent_provider(self, provider_id: str) -> ActionResult:
        data = self._agent_service().logout_provider(provider_id)
        return self.ok("Agent provider logged out", data)

    def get_agent_provider_status(self, provider_id: str = "") -> dict[str, Any]:
        return self._agent_service().get_provider_status(provider_id)

    def set_agent_default_provider(self, provider_id: str, model: str = "", base_url: str = "") -> ActionResult:
        data = self._agent_service().set_default_provider(provider_id, model=model, base_url=base_url)
        return self.ok("Agent default provider updated", data)

    def compact_agent_session(self, session_id: str) -> ActionResult:
        data = self._agent_service().compact_session(session_id)
        return self.ok("Agent session compacted", data)

    def get_agent_usage(self, session_id: str) -> dict[str, Any]:
        return self._agent_service().get_usage(session_id)

    def inspect_agent_session(self, session_id: str) -> dict[str, Any]:
        return self._agent_service().inspect_session(session_id)
