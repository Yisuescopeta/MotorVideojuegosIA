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
    ) -> ActionResult:
        data = self._agent_service().create_session(
            permission_mode=permission_mode,
            title=title,
            provider_id=provider_id,
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
