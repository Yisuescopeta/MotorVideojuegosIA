from __future__ import annotations

import json
import os
import shlex
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol

from engine.agent.credentials import DEFAULT_OPENCODE_GO_BASE_URL, DEFAULT_OPENCODE_GO_MODEL

from engine.agent.types import (
    AgentContentBlock,
    AgentMessage,
    AgentMessageRole,
    AgentRuntimeConfig,
    AgentToolCall,
    AgentToolResult,
    new_id,
)


def _validated_https_url(url: str, provider_id: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(f"{provider_id} provider requires an https base URL.")
    return url


@dataclass(frozen=True)
class AgentProviderMetadata:
    provider_id: str
    provider_kind: str = "custom"
    offline: bool = True
    online: bool = False
    requires_credentials: bool = False
    test_only: bool = False
    supports_tools: bool = True
    supports_streaming: bool = False
    supports_tool_calls: bool = True
    supports_usage: bool = False
    default_model: str = ""
    auth_status: str = "missing"
    credential_source: str = "none"
    base_url: str = ""
    login_supported: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "provider_kind": self.provider_kind,
            "offline": self.offline,
            "online": self.online,
            "requires_credentials": self.requires_credentials,
            "test_only": self.test_only,
            "supports_tools": self.supports_tools,
            "supports_streaming": self.supports_streaming,
            "supports_tool_calls": self.supports_tool_calls,
            "supports_usage": self.supports_usage,
            "default_model": self.default_model,
            "auth_status": self.auth_status,
            "credential_source": self.credential_source,
            "base_url": self.base_url,
            "login_supported": self.login_supported,
        }


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
    model: str = ""
    usage: dict[str, object] = field(default_factory=dict)

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


@dataclass(frozen=True)
class AgentProviderStreamEvent:
    kind: str
    delta: str = ""
    response: AgentProviderResponse | None = None
    data: dict[str, object] = field(default_factory=dict)


class LLMProvider(Protocol):
    provider_id: str

    def run_turn(self, request: AgentProviderRequest, config: AgentRuntimeConfig) -> AgentProviderResponse:
        ...


class FakeLLMProvider:
    """Deterministic test provider kept as a compatible fake provider alias."""

    provider_id = "fake"
    metadata = AgentProviderMetadata(
        provider_id="fake",
        provider_kind="test",
        offline=True,
        online=False,
        requires_credentials=False,
        test_only=True,
        supports_tools=True,
        supports_streaming=False,
        supports_tool_calls=True,
        supports_usage=False,
        default_model="fake",
        auth_status="configured",
        credential_source="none",
        login_supported=False,
    )

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


class ReplayLLMProvider:
    """Scripted offline provider for deterministic multi-turn runtime contracts."""

    def __init__(
        self,
        responses: list[AgentProviderResponse | dict],
        *,
        provider_id: str = "replay",
        streaming: bool = False,
    ) -> None:
        self.provider_id = provider_id
        self._streaming = bool(streaming)
        self.metadata = AgentProviderMetadata(
            provider_id=provider_id,
            provider_kind="test",
            offline=True,
            online=False,
            requires_credentials=False,
            test_only=True,
            supports_tools=True,
            supports_streaming=self._streaming,
            supports_tool_calls=True,
            supports_usage=False,
            default_model="replay",
            auth_status="configured",
            credential_source="none",
            login_supported=False,
        )
        self._responses = list(responses)
        self._index = 0

    def run_turn(self, request: AgentProviderRequest, config: AgentRuntimeConfig) -> AgentProviderResponse:
        if self._index >= len(self._responses):
            return AgentProviderResponse.from_text(
                "Replay provider exhausted.",
                provider_id=self.provider_id,
            )
        raw = self._responses[self._index]
        self._index += 1
        response = self._coerce_response(raw)
        if response.provider_id == self.provider_id:
            return response
        return AgentProviderResponse(
            content_blocks=response.content_blocks,
            stop_reason=response.stop_reason,
            provider_id=self.provider_id,
        )

    def stream_turn(
        self,
        request: AgentProviderRequest,
        config: AgentRuntimeConfig,
    ) -> Iterable[AgentProviderStreamEvent]:
        response = self.run_turn(request, config)
        content = response.content
        if content:
            for char in content:
                yield AgentProviderStreamEvent("text_delta", delta=char)
        for call in response.tool_calls:
            yield AgentProviderStreamEvent("tool_use_delta", data={"tool_call": call.to_dict()})
        yield AgentProviderStreamEvent("completed", response=response)

    def _coerce_response(self, raw: AgentProviderResponse | dict) -> AgentProviderResponse:
        if isinstance(raw, AgentProviderResponse):
            return raw
        blocks: list[AgentContentBlock] = []
        text = str(raw.get("text", ""))
        if text:
            blocks.append(AgentContentBlock.text_block(text))
        for tool_use in raw.get("tool_uses", raw.get("tool_calls", [])):
            payload = dict(tool_use)
            call = AgentToolCall(
                tool_call_id=str(payload.get("tool_call_id", payload.get("id", new_id("tool")))),
                tool_name=str(payload.get("tool_name", payload.get("name", ""))),
                args=dict(payload.get("args", {})),
            )
            blocks.append(AgentContentBlock.tool_use_block(call))
        return AgentProviderResponse(
            content_blocks=blocks,
            stop_reason=str(raw.get("stop_reason", "tool_use" if any(block.tool_use for block in blocks) else "end_turn")),
            provider_id=self.provider_id,
        )


class OpenAICompatibleChatProvider:
    """Adapter for OpenAI-compatible /v1/chat/completions endpoints."""

    def __init__(
        self,
        *,
        provider_id: str,
        base_url: str,
        default_model: str,
        api_key: str | None = None,
        api_key_getter: Callable[[], str] | None = None,
        base_url_getter: Callable[[], str] | None = None,
        timeout_seconds: int = 60,
        display_kind: str = "online",
    ) -> None:
        self.provider_id = provider_id
        self.base_url = base_url
        self.default_model = default_model
        self.api_key = api_key
        self.api_key_getter = api_key_getter
        self.base_url_getter = base_url_getter
        self.timeout_seconds = int(timeout_seconds)
        self.metadata = AgentProviderMetadata(
            provider_id=provider_id,
            provider_kind=display_kind,
            offline=False,
            online=True,
            requires_credentials=True,
            test_only=False,
            supports_tools=True,
            supports_streaming=True,
            supports_tool_calls=True,
            supports_usage=True,
            default_model=default_model,
            auth_status="configured" if self._api_key() else "missing",
            credential_source="user_local" if self._api_key() else "none",
            base_url=self._base_url(),
            login_supported=True,
        )

    def validate_runtime_config(self, config: AgentRuntimeConfig) -> None:
        if not self._api_key():
            raise RuntimeError(f"{self.provider_id} provider requires a configured API key. Use /login {self.provider_id}.")

    def run_turn(self, request: AgentProviderRequest, config: AgentRuntimeConfig) -> AgentProviderResponse:
        self.validate_runtime_config(config)
        payload = self._build_payload(request, config, stream=False)
        data = self._post_json(payload)
        return self._parse_response(data, config)

    def stream_turn(
        self,
        request: AgentProviderRequest,
        config: AgentRuntimeConfig,
    ) -> Iterable[AgentProviderStreamEvent]:
        self.validate_runtime_config(config)
        payload = self._build_payload(request, config, stream=True)
        request_obj = urllib.request.Request(
            self._validated_base_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        text_parts: list[str] = []
        tool_fragments: dict[int, dict[str, str]] = {}
        try:
            with urllib.request.urlopen(request_obj, timeout=self.timeout_seconds) as response:  # nosec B310
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    event_data = line[5:].strip()
                    if event_data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(event_data)
                    except json.JSONDecodeError:
                        continue
                    delta = self._first_delta(chunk)
                    content = str(delta.get("content", "") or "")
                    if content:
                        text_parts.append(content)
                        yield AgentProviderStreamEvent("text_delta", delta=content)
                    for raw_call in delta.get("tool_calls", []) if isinstance(delta.get("tool_calls"), list) else []:
                        if not isinstance(raw_call, dict):
                            continue
                        index = int(raw_call.get("index", 0) or 0)
                        fragment = tool_fragments.setdefault(index, {"id": "", "name": "", "arguments": ""})
                        if raw_call.get("id"):
                            fragment["id"] = str(raw_call.get("id"))
                        function = raw_call.get("function", {})
                        if isinstance(function, dict):
                            if function.get("name"):
                                fragment["name"] += str(function.get("name"))
                            if function.get("arguments"):
                                fragment["arguments"] += str(function.get("arguments"))
            calls = [self._tool_call_from_chat_fragment(fragment) for _, fragment in sorted(tool_fragments.items())]
            blocks: list[AgentContentBlock] = []
            text = "".join(text_parts)
            if text:
                blocks.append(AgentContentBlock.text_block(text))
            for call in calls:
                blocks.append(AgentContentBlock.tool_use_block(call))
                yield AgentProviderStreamEvent("tool_use_delta", data={"tool_call": call.to_dict()})
            yield AgentProviderStreamEvent(
                "completed",
                response=AgentProviderResponse(
                    blocks,
                    stop_reason="tool_use" if calls else "end_turn",
                    provider_id=self.provider_id,
                    model=config.model or self.default_model,
                ),
            )
        except Exception as exc:
            yield AgentProviderStreamEvent("failed", data={"warning": f"Streaming unavailable; retrying without streaming: {exc}"})
            yield AgentProviderStreamEvent("completed", response=self.run_turn(request, config))

    def _api_key(self) -> str:
        if self.api_key:
            return str(self.api_key).strip()
        if self.api_key_getter is not None:
            return str(self.api_key_getter() or "").strip()
        return ""

    def _base_url(self) -> str:
        if self.base_url_getter is not None:
            value = str(self.base_url_getter() or "").strip()
            if value:
                return value
        return self.base_url

    def _validated_base_url(self) -> str:
        return _validated_https_url(self._base_url(), self.provider_id)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key()}", "Content-Type": "application/json"}

    def _post_json(self, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            self._validated_base_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(self._http_error_message(exc)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{self.provider_id} request failed: {exc}") from exc

    def _build_payload(self, request: AgentProviderRequest, config: AgentRuntimeConfig, *, stream: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": config.model or self.default_model,
            "messages": self._messages_to_chat(request.messages),
            "tools": self._tools_to_chat(request.available_tools),
            "tool_choice": "auto",
        }
        if stream:
            payload["stream"] = True
        if config.temperature is not None:
            payload["temperature"] = config.temperature
        if config.max_tokens is not None:
            payload["max_tokens"] = int(config.max_tokens)
        return payload

    def _messages_to_chat(self, messages: list[AgentMessage]) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for message in messages:
            if message.role == AgentMessageRole.TOOL and message.tool_result is not None:
                result = message.tool_result
                items.append(
                    {
                        "role": "tool",
                        "tool_call_id": result.tool_call_id,
                        "content": result.output if result.success else result.error,
                    }
                )
                continue
            if message.role == AgentMessageRole.ASSISTANT and message.tool_calls:
                payload: dict[str, object] = {"role": "assistant", "content": message.content or ""}
                payload["tool_calls"] = [
                    {
                        "id": call.tool_call_id,
                        "type": "function",
                        "function": {"name": call.tool_name, "arguments": json.dumps(call.args, ensure_ascii=True)},
                    }
                    for call in message.tool_calls
                ]
                items.append(payload)
                continue
            if message.content:
                role = "assistant" if message.role == AgentMessageRole.ASSISTANT else "user"
                if message.role == AgentMessageRole.SYSTEM:
                    role = "system"
                items.append({"role": role, "content": message.content})
        return items

    def _tools_to_chat(self, tools: list[dict]) -> list[dict[str, object]]:
        specs: list[dict[str, object]] = []
        for tool in tools:
            name = str(tool.get("name", "")).strip()
            if not name:
                continue
            parameters = tool.get("parameters_schema")
            if not isinstance(parameters, dict):
                parameters = {"type": "object", "properties": {}, "additionalProperties": False}
            specs.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": str(tool.get("description", "")),
                        "parameters": parameters,
                    },
                }
            )
        return specs

    def _parse_response(self, data: dict[str, object], config: AgentRuntimeConfig) -> AgentProviderResponse:
        message = self._first_message(data)
        blocks: list[AgentContentBlock] = []
        content = str(message.get("content", "") or "")
        if content:
            blocks.append(AgentContentBlock.text_block(content))
        for raw_call in message.get("tool_calls", []) if isinstance(message.get("tool_calls"), list) else []:
            if isinstance(raw_call, dict):
                blocks.append(AgentContentBlock.tool_use_block(self._tool_call_from_chat(raw_call)))
        usage = dict(data.get("usage", {})) if isinstance(data.get("usage"), dict) else {}
        tool_calls = [block.tool_use.tool_call for block in blocks if block.tool_use is not None]
        return AgentProviderResponse(
            blocks,
            stop_reason="tool_use" if tool_calls else "end_turn",
            provider_id=self.provider_id,
            model=str(data.get("model", config.model or self.default_model)),
            usage=usage,
        )

    def _first_message(self, data: dict[str, object]) -> dict[str, object]:
        choices = data.get("choices", [])
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message", {})
            if isinstance(message, dict):
                return message
        return {}

    def _first_delta(self, data: dict[str, object]) -> dict[str, object]:
        choices = data.get("choices", [])
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            delta = choices[0].get("delta", {})
            if isinstance(delta, dict):
                return delta
        return {}

    def _tool_call_from_chat(self, item: dict[str, object]) -> AgentToolCall:
        function = item.get("function", {})
        payload = function if isinstance(function, dict) else {}
        arguments = str(payload.get("arguments", "{}") or "{}")
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError:
            args = {}
        return AgentToolCall(
            str(item.get("id", new_id("tool"))),
            str(payload.get("name", "")),
            args if isinstance(args, dict) else {},
        )

    def _tool_call_from_chat_fragment(self, fragment: dict[str, str]) -> AgentToolCall:
        try:
            args = json.loads(fragment.get("arguments", "{}") or "{}")
        except json.JSONDecodeError:
            args = {}
        return AgentToolCall(
            fragment.get("id") or new_id("tool"),
            fragment.get("name", ""),
            args if isinstance(args, dict) else {},
        )

    def _http_error_message(self, exc: urllib.error.HTTPError) -> str:
        body = exc.read().decode("utf-8", errors="replace")
        return f"{self.provider_id} request failed with HTTP {exc.code}: {body[:1200]}"


def create_opencode_go_provider(
    api_key_getter: Callable[[], str] | None = None,
    base_url_getter: Callable[[], str] | None = None,
) -> OpenAICompatibleChatProvider:
    return OpenAICompatibleChatProvider(
        provider_id="opencode-go",
        base_url=DEFAULT_OPENCODE_GO_BASE_URL,
        default_model=DEFAULT_OPENCODE_GO_MODEL,
        api_key_getter=api_key_getter,
        base_url_getter=base_url_getter,
    )


class OpenAIProvider:
    """OpenAI Responses API adapter with no mandatory SDK dependency."""

    provider_id = "openai"
    api_url = "https://api.openai.com/v1/responses"
    api_key_env = "OPENAI_API_KEY"
    metadata = AgentProviderMetadata(
        provider_id="openai",
        provider_kind="online",
        offline=False,
        online=True,
        requires_credentials=True,
        test_only=False,
        supports_tools=True,
        supports_streaming=True,
        supports_tool_calls=True,
        supports_usage=True,
        default_model="gpt-5",
        auth_status="missing",
        credential_source="none",
        base_url=api_url,
        login_supported=True,
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_key_getter: Callable[[], str] | None = None,
        default_model: str | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key
        self.api_key_getter = api_key_getter
        self.default_model = default_model or os.environ.get("MOTOR_AGENT_OPENAI_MODEL", "").strip() or "gpt-5"
        self.timeout_seconds = int(timeout_seconds)
        self.metadata = AgentProviderMetadata(
            provider_id=self.provider_id,
            provider_kind="online",
            offline=False,
            online=True,
            requires_credentials=True,
            test_only=False,
            supports_tools=True,
            supports_streaming=True,
            supports_tool_calls=True,
            supports_usage=True,
            default_model=self.default_model,
            auth_status="configured" if self._api_key() else "missing",
            credential_source="env" if os.environ.get(self.api_key_env, "").strip() else ("user_local" if self._api_key() else "none"),
            base_url=self.api_url,
            login_supported=True,
        )

    def validate_runtime_config(self, config: AgentRuntimeConfig) -> None:
        if not self._api_key():
            raise RuntimeError("OpenAI provider requires a configured credential. Use /login openai, motor agent providers login openai --codex-chatgpt, or OPENAI_API_KEY.")

    def run_turn(self, request: AgentProviderRequest, config: AgentRuntimeConfig) -> AgentProviderResponse:
        self.validate_runtime_config(config)
        payload = self._build_payload(request, config, stream=False)
        data = self._post_json(payload)
        return self._parse_response(data, config)

    def stream_turn(
        self,
        request: AgentProviderRequest,
        config: AgentRuntimeConfig,
    ) -> Iterable[AgentProviderStreamEvent]:
        self.validate_runtime_config(config)
        payload = self._build_payload(request, config, stream=True)
        request_obj = urllib.request.Request(
            self._validated_api_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        text_parts: list[str] = []
        tool_calls: list[AgentToolCall] = []
        usage: dict[str, object] = {}
        model = str(payload.get("model", ""))
        try:
            with urllib.request.urlopen(request_obj, timeout=self.timeout_seconds) as response:  # nosec B310
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    event_data = line[5:].strip()
                    if event_data == "[DONE]":
                        break
                    try:
                        event = json.loads(event_data)
                    except json.JSONDecodeError:
                        continue
                    event_type = str(event.get("type", ""))
                    if event_type == "response.output_text.delta":
                        delta = str(event.get("delta", ""))
                        text_parts.append(delta)
                        yield AgentProviderStreamEvent("text_delta", delta=delta)
                    elif event_type == "response.function_call_arguments.done":
                        call = self._tool_call_from_stream_event(event)
                        if call is not None:
                            tool_calls.append(call)
                            yield AgentProviderStreamEvent("tool_use_delta", data={"tool_call": call.to_dict()})
                    elif event_type == "response.completed":
                        response_payload = event.get("response", {})
                        if isinstance(response_payload, dict):
                            parsed = self._parse_response(response_payload, config)
                            yield AgentProviderStreamEvent("completed", response=parsed)
                            return
                    elif event_type in {"response.failed", "error"}:
                        yield AgentProviderStreamEvent("failed", data={"error": str(event.get("error", event))})
                        return
        except urllib.error.HTTPError as exc:
            raise RuntimeError(self._http_error_message(exc)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        blocks: list[AgentContentBlock] = []
        text = "".join(text_parts)
        if text:
            blocks.append(AgentContentBlock.text_block(text))
        blocks.extend(AgentContentBlock.tool_use_block(call) for call in tool_calls)
        yield AgentProviderStreamEvent(
            "completed",
            response=AgentProviderResponse(
                blocks,
                stop_reason="tool_use" if tool_calls else "end_turn",
                provider_id=self.provider_id,
                model=model,
                usage=usage,
            ),
        )

    def _api_key(self) -> str:
        if self.api_key:
            return str(self.api_key).strip()
        if self.api_key_getter is not None:
            value = str(self.api_key_getter() or "").strip()
            if value:
                return value
        return str(os.environ.get(self.api_key_env, "")).strip()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key()}",
            "Content-Type": "application/json",
        }

    def _validated_api_url(self) -> str:
        return _validated_https_url(self.api_url, self.provider_id)

    def _post_json(self, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            self._validated_api_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:  # nosec B310
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(self._http_error_message(exc)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

    def _build_payload(self, request: AgentProviderRequest, config: AgentRuntimeConfig, *, stream: bool) -> dict[str, object]:
        model = config.model or self.default_model
        payload: dict[str, object] = {
            "model": model,
            "input": self._messages_to_input(request.messages),
            "tools": self._tools_to_openai(request.available_tools),
            "tool_choice": "auto",
        }
        if stream:
            payload["stream"] = True
        if config.temperature is not None:
            payload["temperature"] = config.temperature
        if config.max_tokens is not None:
            payload["max_output_tokens"] = int(config.max_tokens)
        return payload

    def _messages_to_input(self, messages: list[AgentMessage]) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for message in messages:
            if message.role == AgentMessageRole.TOOL and message.tool_result is not None:
                result = message.tool_result
                output = result.output if result.success else result.error
                items.append({"type": "function_call_output", "call_id": result.tool_call_id, "output": output})
                continue
            if message.role == AgentMessageRole.ASSISTANT and message.tool_calls:
                if message.content:
                    items.append({"role": "assistant", "content": message.content})
                for call in message.tool_calls:
                    items.append(
                        {
                            "type": "function_call",
                            "call_id": call.tool_call_id,
                            "name": call.tool_name,
                            "arguments": json.dumps(call.args, ensure_ascii=True),
                        }
                    )
                continue
            if message.content:
                role = "assistant" if message.role == AgentMessageRole.ASSISTANT else "user"
                if message.role == AgentMessageRole.SYSTEM:
                    role = "system"
                items.append({"role": role, "content": message.content})
        return items

    def _tools_to_openai(self, tools: list[dict]) -> list[dict[str, object]]:
        specs: list[dict[str, object]] = []
        for tool in tools:
            name = str(tool.get("name", "")).strip()
            if not name:
                continue
            parameters = tool.get("parameters_schema")
            if not isinstance(parameters, dict):
                parameters = {"type": "object", "properties": {}, "additionalProperties": False}
            specs.append(
                {
                    "type": "function",
                    "name": name,
                    "description": str(tool.get("description", "")),
                    "parameters": parameters,
                }
            )
        return specs

    def _parse_response(self, data: dict[str, object], config: AgentRuntimeConfig) -> AgentProviderResponse:
        blocks: list[AgentContentBlock] = []
        output = data.get("output", [])
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict):
                    continue
                item_type = str(item.get("type", ""))
                if item_type == "message":
                    for part in item.get("content", []):
                        if isinstance(part, dict) and str(part.get("type", "")) in {"output_text", "text"}:
                            text = str(part.get("text", ""))
                            if text:
                                blocks.append(AgentContentBlock.text_block(text))
                elif item_type == "function_call":
                    call = self._tool_call_from_item(item)
                    blocks.append(AgentContentBlock.tool_use_block(call))
        if not blocks and isinstance(data.get("output_text"), str):
            blocks.append(AgentContentBlock.text_block(str(data["output_text"])))
        usage = dict(data.get("usage", {})) if isinstance(data.get("usage"), dict) else {}
        tool_calls = [block.tool_use.tool_call for block in blocks if block.tool_use is not None]
        return AgentProviderResponse(
            blocks,
            stop_reason="tool_use" if tool_calls else str(data.get("status", "end_turn")),
            provider_id=self.provider_id,
            model=str(data.get("model", config.model or self.default_model)),
            usage=usage,
        )

    def _tool_call_from_item(self, item: dict[str, object]) -> AgentToolCall:
        arguments = item.get("arguments", "{}")
        try:
            args = json.loads(str(arguments or "{}"))
        except json.JSONDecodeError:
            args = {}
        return AgentToolCall(
            tool_call_id=str(item.get("call_id", item.get("id", new_id("tool")))),
            tool_name=str(item.get("name", "")),
            args=args if isinstance(args, dict) else {},
        )

    def _tool_call_from_stream_event(self, event: dict[str, object]) -> AgentToolCall | None:
        name = str(event.get("name", ""))
        call_id = str(event.get("call_id", event.get("item_id", "")))
        arguments = event.get("arguments", "{}")
        if not name or not call_id:
            return None
        try:
            args = json.loads(str(arguments or "{}"))
        except json.JSONDecodeError:
            args = {}
        return AgentToolCall(call_id, name, args if isinstance(args, dict) else {})

    def _http_error_message(self, exc: urllib.error.HTTPError) -> str:
        body = exc.read().decode("utf-8", errors="replace")
        return f"OpenAI request failed with HTTP {exc.code}: {body[:1200]}"

class AgentProviderResolver:
    def __init__(self, providers: list[LLMProvider] | None = None) -> None:
        configured = providers or [FakeLLMProvider(), OpenAIProvider(), create_opencode_go_provider()]
        self._providers: dict[str, LLMProvider] = {}
        for provider in configured:
            self._providers[provider.provider_id] = provider

    def resolve(self, provider_id: str) -> LLMProvider:
        selected = str(provider_id or "fake")
        provider = self._providers.get(selected)
        if provider is None:
            available = ", ".join(sorted(self._providers)) or "<none>"
            raise ValueError(f"Agent provider is not available: {selected}. Available providers: {available}")
        return provider

    def metadata_for(self, provider_id: str) -> AgentProviderMetadata:
        return provider_metadata(self.resolve(provider_id))

    def list_provider_metadata(self) -> list[dict[str, object]]:
        return [provider_metadata(provider).to_dict() for provider in self._providers.values()]

    def list_provider_ids(self) -> list[str]:
        return sorted(self._providers)


def provider_metadata(provider: LLMProvider) -> AgentProviderMetadata:
    metadata = getattr(provider, "metadata", None)
    if isinstance(metadata, AgentProviderMetadata):
        return metadata
    provider_id = str(getattr(provider, "provider_id", "unknown"))
    return AgentProviderMetadata(
        provider_id=provider_id,
        provider_kind="custom",
        offline=True,
        online=False,
        requires_credentials=False,
        test_only=False,
        supports_tools=True,
        supports_streaming=False,
        supports_tool_calls=True,
        supports_usage=False,
        default_model="",
    )
