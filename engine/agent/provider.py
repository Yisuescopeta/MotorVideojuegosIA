from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Protocol

from engine.agent.types import (
    AgentContentBlock,
    AgentMessage,
    AgentMessageRole,
    AgentRuntimeConfig,
    AgentToolCall,
    AgentToolResult,
    new_id,
)


@dataclass(frozen=True)
class AgentProviderRequest:
    session_id: str
    turn_id: str
    messages: list[AgentMessage]
    available_tools: list[dict]
    iteration: int = 0


@dataclass(frozen=True)
class AgentProviderResponse:
    content_blocks: list[AgentContentBlock] = field(default_factory=list)
    stop_reason: str = "end_turn"
    provider_id: str = "fake"

    @property
    def content(self) -> str:
        return "\n".join(block.text for block in self.content_blocks if block.text).strip()

    @property
    def tool_calls(self) -> list[AgentToolCall]:
        calls: list[AgentToolCall] = []
        for block in self.content_blocks:
            if block.tool_use is not None:
                calls.append(block.tool_use.tool_call)
        return calls

    @classmethod
    def from_text(
        cls,
        content: str,
        tool_calls: list[AgentToolCall] | None = None,
        *,
        stop_reason: str = "end_turn",
        provider_id: str = "fake",
    ) -> "AgentProviderResponse":
        blocks: list[AgentContentBlock] = []
        if content:
            blocks.append(AgentContentBlock.text_block(content))
        for call in tool_calls or []:
            blocks.append(AgentContentBlock.tool_use_block(call))
        return cls(blocks, stop_reason=stop_reason, provider_id=provider_id)


class LLMProvider(Protocol):
    provider_id: str

    def run_turn(self, request: AgentProviderRequest, config: AgentRuntimeConfig) -> AgentProviderResponse:
        ...


class FakeLLMProvider:
    """Deterministic provider for tests and offline editor usage."""

    provider_id = "fake"

    def run_turn(self, request: AgentProviderRequest, config: AgentRuntimeConfig) -> AgentProviderResponse:
        last_message = request.messages[-1] if request.messages else None
        if last_message is not None and last_message.role == AgentMessageRole.TOOL and last_message.tool_result is not None:
            return self._respond_to_tool_result(last_message.tool_result)

        last_user = next((message for message in reversed(request.messages) if message.role == AgentMessageRole.USER), None)
        text = (last_user.content if last_user is not None else "").strip()
        lowered = text.lower()
        if not text:
            return AgentProviderResponse.from_text("No input received.", provider_id=self.provider_id)
        call = self._parse_tool_call(text, lowered)
        if call is not None:
            return AgentProviderResponse.from_text(
                f"Tool requested: {call.tool_name}",
                [call],
                stop_reason="tool_use",
                provider_id=self.provider_id,
            )
        tool_names = ", ".join(sorted(tool["name"] for tool in request.available_tools)[:8])
        return AgentProviderResponse.from_text(
            "Fake provider ready. Use commands like 'read README.md', 'list engine', "
            f"'search Transform in engine', 'write path :: content', or slash commands. Tools: {tool_names}.",
            provider_id=self.provider_id,
        )

    def generate(self, session, available_tools: list[dict]) -> AgentProviderResponse:
        """Compatibility wrapper for v1 callers."""
        return self.run_turn(
            AgentProviderRequest(
                session_id=str(getattr(session, "session_id", "")),
                turn_id="legacy",
                messages=list(getattr(session, "messages", [])),
                available_tools=available_tools,
            ),
            AgentRuntimeConfig(provider_id=self.provider_id),
        )

    def _respond_to_tool_result(self, result: AgentToolResult) -> AgentProviderResponse:
        if result.success:
            output = (result.output or "").strip().replace("\n", " ")
            if len(output) > 220:
                output = output[:220] + "..."
            return AgentProviderResponse.from_text(
                f"Tool result received for {result.tool_name}: {output}",
                provider_id=self.provider_id,
            )
        message = (result.error or "unknown error").strip().replace("\n", " ")
        return AgentProviderResponse.from_text(
            f"Tool {result.tool_name} failed: {message}",
            provider_id=self.provider_id,
        )

    def _parse_tool_call(self, text: str, lowered: str) -> AgentToolCall | None:
        if lowered.startswith("read "):
            return AgentToolCall(new_id("tool"), "read_file", {"path": text[5:].strip()})
        if lowered.startswith("list "):
            return AgentToolCall(new_id("tool"), "list_files", {"path": text[5:].strip() or "."})
        if lowered.startswith("search "):
            body = text[7:].strip()
            if " in " in body:
                pattern, path = body.rsplit(" in ", 1)
            else:
                pattern, path = body, "."
            return AgentToolCall(new_id("tool"), "search_text", {"pattern": pattern.strip(), "path": path.strip()})
        if lowered.startswith("write ") and " :: " in text:
            path, content = text[6:].split(" :: ", 1)
            return AgentToolCall(new_id("tool"), "write_file", {"path": path.strip(), "content": content})
        if lowered.startswith("edit ") and " :: " in text:
            path, rest = text[5:].split(" :: ", 1)
            if " => " in rest:
                old_text, new_text = rest.split(" => ", 1)
                return AgentToolCall(
                    new_id("tool"),
                    "edit_file",
                    {"path": path.strip(), "old_text": old_text, "new_text": new_text},
                )
        if lowered.startswith("run "):
            return AgentToolCall(new_id("tool"), "run_command", {"command": text[4:].strip()})
        if lowered == "git status":
            return AgentToolCall(new_id("tool"), "git_status", {})
        if lowered.startswith("git diff"):
            parts = shlex.split(text)
            return AgentToolCall(new_id("tool"), "git_diff", {"path": parts[2] if len(parts) > 2 else ""})
        if lowered.startswith("git stage "):
            return AgentToolCall(new_id("tool"), "git_stage", {"paths": [text[10:].strip()]})
        if lowered.startswith("git commit "):
            return AgentToolCall(new_id("tool"), "git_commit", {"message": text[11:].strip()})
        if lowered in {"engine context", "context"}:
            return AgentToolCall(new_id("tool"), "engine_context", {})
        if lowered in {"engine capabilities", "capabilities"}:
            return AgentToolCall(new_id("tool"), "engine_capabilities", {})
        return None


class AgentProviderResolver:
    def __init__(self, providers: list[LLMProvider] | None = None) -> None:
        configured = providers or [FakeLLMProvider()]
        self._providers = {provider.provider_id: provider for provider in configured}

    def resolve(self, provider_id: str) -> LLMProvider:
        selected = str(provider_id or "fake")
        provider = self._providers.get(selected)
        if provider is None:
            raise ValueError(f"Agent provider is not available offline: {selected}")
        return provider

    def list_provider_ids(self) -> list[str]:
        return sorted(self._providers)
