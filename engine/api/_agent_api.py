from __future__ import annotations

from typing import Union

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
        """Create a new AI agent session with specified configuration.

        Args:
            permission_mode: Permission handling mode. Options: "confirm_actions",
                "auto_approve", "read_only". Default "confirm_actions".
            title: Human-readable session title.
            provider_id: AI provider identifier (e.g. "fake", "openai", "anthropic").
            model: Model name string. Empty uses provider default.
            temperature: Sampling temperature (0.0-2.0). None uses provider default.
            max_tokens: Maximum output tokens. None uses provider default.
            stream: Whether to enable streaming responses.

        Returns:
            ActionResult with the created session data including session_id.
        """
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
        """Send a message to an agent session and receive the response.

        Args:
            session_id: Agent session identifier.
            message: User message text to send.

        Returns:
            ActionResult with the agent's response data.
        """
        data = self._agent_service().send_message(session_id, message)
        return self.ok("Agent message processed", data)

    def get_agent_session(self, session_id: str) -> dict[str, Union[str, int, float, bool, list, dict, None]]:
        """Retrieve the current state of an agent session.

        Args:
            session_id: Agent session identifier.

        Returns:
            Dictionary with session state, messages, and metadata.
        """
        return self._agent_service().get_session(session_id)

    def approve_agent_action(self, session_id: str, action_id: str, approved: bool) -> ActionResult:
        """Approve or reject a pending agent action that requires confirmation.

        Args:
            session_id: Agent session identifier.
            action_id: Unique action identifier to resolve.
            approved: True to approve the action, False to reject.

        Returns:
            ActionResult with the resolved action status.
        """
        data = self._agent_service().approve_action(session_id, action_id, approved)
        return self.ok("Agent action resolved", data)

    def cancel_agent_session(self, session_id: str) -> ActionResult:
        """Cancel and terminate an active agent session.

        Args:
            session_id: Agent session identifier.

        Returns:
            ActionResult confirming the session was cancelled.
        """
        data = self._agent_service().cancel_session(session_id)
        return self.ok("Agent session cancelled", data)

    def list_agent_tools(self) -> list[dict[str, Union[str, int, float, bool, list, dict, None]]]:
        """List all tools available to AI agents in the engine.

        Returns:
            List of tool definition dictionaries with name, description,
            parameters, etc.
        """
        return self._agent_service().list_tools()

    def list_agent_providers(self) -> list[dict[str, object]]:
        """List all configured AI provider integrations.

        Returns:
            List of provider info dictionaries with id, name, models, status, etc.
        """
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
        """Authenticate with an AI provider using the specified credential method.

        Args:
            provider_id: Provider identifier (e.g. "openai", "anthropic").
            credential_source: Credential source type: "user_local",
                "codex_chatgpt", or "codex_api_key".
            base_url: Custom API base URL (empty uses provider default).
            model: Default model for this provider.
            api_key: Direct API key (only used with "codex_api_key" source).
            device_auth: Whether to use device-code OAuth flow.

        Returns:
            ActionResult with login status and provider info.
        """
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
        """Log out and clear credentials for an AI provider.

        Args:
            provider_id: Provider identifier to log out.

        Returns:
            ActionResult confirming logout.
        """
        data = self._agent_service().logout_provider(provider_id)
        return self.ok("Agent provider logged out", data)

    def get_agent_provider_status(self, provider_id: str = "") -> dict[str, Union[str, int, float, bool, list, dict, None]]:
        """Get the authentication status of one or all AI providers.

        Args:
            provider_id: Specific provider identifier, or empty string for all.

        Returns:
            Dictionary with provider status information.
        """
        return self._agent_service().get_provider_status(provider_id)

    def set_agent_default_provider(self, provider_id: str, model: str = "", base_url: str = "") -> ActionResult:
        """Set the default AI provider and model for new agent sessions.

        Args:
            provider_id: Provider identifier to set as default.
            model: Default model name for the provider.
            base_url: Custom API base URL.

        Returns:
            ActionResult confirming the default provider was updated.
        """
        data = self._agent_service().set_default_provider(provider_id, model=model, base_url=base_url)
        return self.ok("Agent default provider updated", data)

    def compact_agent_session(self, session_id: str) -> ActionResult:
        """Compact an agent session's message history to reduce token usage.

        Args:
            session_id: Agent session identifier.

        Returns:
            ActionResult with compacted session data.
        """
        data = self._agent_service().compact_session(session_id)
        return self.ok("Agent session compacted", data)

    def get_agent_usage(self, session_id: str) -> dict[str, Union[str, int, float, bool, list, dict, None]]:
        """Get token usage statistics for an agent session.

        Args:
            session_id: Agent session identifier.

        Returns:
            Dictionary with prompt_tokens, completion_tokens, total_tokens,
            and cost information.
        """
        return self._agent_service().get_usage(session_id)

    def inspect_agent_session(self, session_id: str) -> dict[str, Union[str, int, float, bool, list, dict, None]]:
        """Get detailed inspection data for an agent session including raw messages.

        Args:
            session_id: Agent session identifier.

        Returns:
            Dictionary with full session inspection data.
        """
        return self._agent_service().inspect_session(session_id)
