from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Protocol

from engine.agent.types import AgentSession, AgentToolCall, new_id


@dataclass(frozen=True)
class AgentProviderResponse:
    content: str
    tool_calls: list[AgentToolCall] = field(default_factory=list)


class LLMProvider(Protocol):
    provider_id: str

    def generate(self, session: AgentSession, available_tools: list[dict]) -> AgentProviderResponse:
        ...


class FakeLLMProvider:
    """Deterministic provider for tests and offline editor usage."""

    provider_id = "fake"

    def generate(self, session: AgentSession, available_tools: list[dict]) -> AgentProviderResponse:
        last_user = next((message for message in reversed(session.messages) if message.role.value == "user"), None)
        text = (last_user.content if last_user is not None else "").strip()
        lowered = text.lower()
        if not text:
            return AgentProviderResponse("No input received.")
        call = self._parse_tool_call(text, lowered)
        if call is not None:
            return AgentProviderResponse(f"Tool requested: {call.tool_name}", [call])
        tool_names = ", ".join(sorted(tool["name"] for tool in available_tools)[:8])
        return AgentProviderResponse(
            "Fake provider ready. Use commands like 'read README.md', 'list engine', "
            f"'search Transform in engine', 'write path :: content', or slash commands. Tools: {tool_names}."
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
