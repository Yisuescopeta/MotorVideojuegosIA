from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class AgentPermissionMode(StrEnum):
    CONFIRM_ACTIONS = "confirm_actions"
    FULL_ACCESS = "full_access"


class AgentMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class AgentActionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class AgentEventKind(StrEnum):
    SESSION_CREATED = "session_created"
    SESSION_MIGRATED = "session_migrated"
    TURN_STARTED = "turn_started"
    TURN_SUSPENDED = "turn_suspended"
    TURN_COMPLETED = "turn_completed"
    TURN_LIMIT_REACHED = "turn_limit_reached"
    MESSAGE_ADDED = "message_added"
    PROVIDER_STARTED = "provider_started"
    PROVIDER_COMPLETED = "provider_completed"
    PROVIDER_FAILED = "provider_failed"
    PROVIDER_STREAM_STARTED = "provider_stream_started"
    ASSISTANT_DELTA = "assistant_delta"
    TOOL_USE_DELTA = "tool_use_delta"
    PROVIDER_STREAM_COMPLETED = "provider_stream_completed"
    PROVIDER_STREAM_FAILED = "provider_stream_failed"
    TOOL_CALLED = "tool_called"
    TOOL_RESULT_ADDED = "tool_result_added"
    ACTION_REQUESTED = "action_requested"
    ACTION_APPROVED = "action_approved"
    ACTION_REJECTED = "action_rejected"
    SESSION_CANCELLED = "session_cancelled"


class AgentTurnStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    LIMIT_REACHED = "limit_reached"


class AgentContentBlockKind(StrEnum):
    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"


class AgentPermissionDecisionKind(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class AgentToolCall:
    tool_call_id: str
    tool_name: str
    args: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentToolCall":
        return cls(
            tool_call_id=str(data.get("tool_call_id", "")),
            tool_name=str(data.get("tool_name", "")),
            args=dict(data.get("args", {})),
        )


@dataclass(frozen=True)
class AgentToolResult:
    tool_call_id: str
    tool_name: str
    success: bool
    output: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentToolResult":
        return cls(
            tool_call_id=str(data.get("tool_call_id", "")),
            tool_name=str(data.get("tool_name", "")),
            success=bool(data.get("success", False)),
            output=str(data.get("output", "")),
            data=dict(data.get("data", {})),
            error=str(data.get("error", "")),
        )


@dataclass(frozen=True)
class AgentToolUseBlock:
    tool_call: AgentToolCall

    def to_dict(self) -> dict[str, Any]:
        return {"tool_call": self.tool_call.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentToolUseBlock":
        return cls(tool_call=AgentToolCall.from_dict(dict(data.get("tool_call", {}))))


@dataclass(frozen=True)
class AgentToolResultBlock:
    tool_result: AgentToolResult

    def to_dict(self) -> dict[str, Any]:
        return {"tool_result": self.tool_result.to_dict()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentToolResultBlock":
        return cls(tool_result=AgentToolResult.from_dict(dict(data.get("tool_result", {}))))


@dataclass(frozen=True)
class AgentContentBlock:
    kind: AgentContentBlockKind
    text: str = ""
    tool_use: AgentToolUseBlock | None = None
    tool_result: AgentToolResultBlock | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "text": self.text,
            "tool_use": self.tool_use.to_dict() if self.tool_use is not None else None,
            "tool_result": self.tool_result.to_dict() if self.tool_result is not None else None,
        }

    @classmethod
    def text_block(cls, text: str) -> "AgentContentBlock":
        return cls(AgentContentBlockKind.TEXT, text=str(text))

    @classmethod
    def tool_use_block(cls, tool_call: AgentToolCall) -> "AgentContentBlock":
        return cls(AgentContentBlockKind.TOOL_USE, tool_use=AgentToolUseBlock(tool_call))

    @classmethod
    def tool_result_block(cls, tool_result: AgentToolResult) -> "AgentContentBlock":
        return cls(AgentContentBlockKind.TOOL_RESULT, tool_result=AgentToolResultBlock(tool_result))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentContentBlock":
        kind = AgentContentBlockKind(str(data.get("kind", AgentContentBlockKind.TEXT.value)))
        return cls(
            kind=kind,
            text=str(data.get("text", "")),
            tool_use=AgentToolUseBlock.from_dict(dict(data.get("tool_use", {})))
            if isinstance(data.get("tool_use"), dict)
            else None,
            tool_result=AgentToolResultBlock.from_dict(dict(data.get("tool_result", {})))
            if isinstance(data.get("tool_result"), dict)
            else None,
        )


@dataclass(frozen=True)
class AgentPermissionDecision:
    kind: AgentPermissionDecisionKind
    reason: str = ""
    preview: str = ""
    updated_args: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "reason": self.reason,
            "preview": self.preview,
            "updated_args": dict(self.updated_args),
        }


@dataclass
class AgentTurnState:
    turn_id: str
    status: AgentTurnStatus = AgentTurnStatus.RUNNING
    iteration: int = 0
    max_iterations: int = 8
    suspended_action_id: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "status": self.status.value,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "suspended_action_id": self.suspended_action_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentTurnState":
        return cls(
            turn_id=str(data.get("turn_id", "")),
            status=AgentTurnStatus(str(data.get("status", AgentTurnStatus.RUNNING.value))),
            iteration=int(data.get("iteration", 0)),
            max_iterations=int(data.get("max_iterations", 8)),
            suspended_action_id=str(data.get("suspended_action_id", "")),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
        )


@dataclass(frozen=True)
class AgentRuntimeConfig:
    provider_id: str = "fake"
    max_iterations_per_turn: int = 8
    model: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    compaction_message_budget: int = 24

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentUsageRecord:
    usage_id: str
    provider_id: str
    model: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: float | None = None
    currency: str = ""
    status: str = "unknown"
    created_at: str = field(default_factory=utc_now_iso)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "usage_id": self.usage_id,
            "provider_id": self.provider_id,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost,
            "currency": self.currency,
            "status": self.status,
            "created_at": self.created_at,
            "raw": dict(self.raw),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentUsageRecord":
        def _int_or_none(value: Any) -> int | None:
            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        def _float_or_none(value: Any) -> float | None:
            try:
                return float(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        return cls(
            usage_id=str(data.get("usage_id", "")) or new_id("agent-usage"),
            provider_id=str(data.get("provider_id", "")),
            model=str(data.get("model", "")),
            input_tokens=_int_or_none(data.get("input_tokens")),
            output_tokens=_int_or_none(data.get("output_tokens")),
            total_tokens=_int_or_none(data.get("total_tokens")),
            estimated_cost=_float_or_none(data.get("estimated_cost")),
            currency=str(data.get("currency", "")),
            status=str(data.get("status", "unknown")),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            raw=dict(data.get("raw", {})) if isinstance(data.get("raw"), dict) else {},
        )


@dataclass
class AgentMessage:
    message_id: str
    role: AgentMessageRole
    content: str
    created_at: str = field(default_factory=utc_now_iso)
    tool_calls: list[AgentToolCall] = field(default_factory=list)
    tool_result: AgentToolResult | None = None
    content_blocks: list[AgentContentBlock] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "role": self.role.value,
            "content": self.content,
            "created_at": self.created_at,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "tool_result": self.tool_result.to_dict() if self.tool_result is not None else None,
            "content_blocks": [block.to_dict() for block in self.content_blocks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentMessage":
        tool_result_data = data.get("tool_result")
        return cls(
            message_id=str(data.get("message_id", "")),
            role=AgentMessageRole(str(data.get("role", AgentMessageRole.SYSTEM.value))),
            content=str(data.get("content", "")),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            tool_calls=[AgentToolCall.from_dict(item) for item in data.get("tool_calls", [])],
            tool_result=AgentToolResult.from_dict(tool_result_data) if isinstance(tool_result_data, dict) else None,
            content_blocks=[AgentContentBlock.from_dict(item) for item in data.get("content_blocks", [])],
        )


@dataclass
class AgentActionRequest:
    action_id: str
    tool_call: AgentToolCall
    reason: str
    preview: str = ""
    turn_id: str = ""
    status: AgentActionStatus = AgentActionStatus.PENDING
    created_at: str = field(default_factory=utc_now_iso)
    resolved_at: str = ""
    result: AgentToolResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "tool_call": self.tool_call.to_dict(),
            "reason": self.reason,
            "preview": self.preview,
            "turn_id": self.turn_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "result": self.result.to_dict() if self.result is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentActionRequest":
        result_data = data.get("result")
        return cls(
            action_id=str(data.get("action_id", "")),
            tool_call=AgentToolCall.from_dict(dict(data.get("tool_call", {}))),
            reason=str(data.get("reason", "")),
            preview=str(data.get("preview", "")),
            turn_id=str(data.get("turn_id", "")),
            status=AgentActionStatus(str(data.get("status", AgentActionStatus.PENDING.value))),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            resolved_at=str(data.get("resolved_at", "")),
            result=AgentToolResult.from_dict(result_data) if isinstance(result_data, dict) else None,
        )


@dataclass(frozen=True)
class AgentSuspension:
    action_id: str
    turn_id: str
    tool_call: AgentToolCall
    reason: str
    preview: str = ""
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "turn_id": self.turn_id,
            "tool_call": self.tool_call.to_dict(),
            "reason": self.reason,
            "preview": self.preview,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSuspension":
        return cls(
            action_id=str(data.get("action_id", "")),
            turn_id=str(data.get("turn_id", "")),
            tool_call=AgentToolCall.from_dict(dict(data.get("tool_call", {}))),
            reason=str(data.get("reason", "")),
            preview=str(data.get("preview", "")),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
        )


@dataclass(frozen=True)
class AgentEvent:
    event_id: str
    kind: AgentEventKind
    created_at: str = field(default_factory=utc_now_iso)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind.value,
            "created_at": self.created_at,
            "data": dict(self.data),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentEvent":
        return cls(
            event_id=str(data.get("event_id", "")),
            kind=AgentEventKind(str(data.get("kind", AgentEventKind.MESSAGE_ADDED.value))),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            data=dict(data.get("data", {})),
        )


@dataclass
class AgentSession:
    session_id: str
    permission_mode: AgentPermissionMode
    provider_id: str = "fake"
    title: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    messages: list[AgentMessage] = field(default_factory=list)
    pending_actions: list[AgentActionRequest] = field(default_factory=list)
    events: list[AgentEvent] = field(default_factory=list)
    active_turn: AgentTurnState | None = None
    suspended_turn: AgentSuspension | None = None
    runtime_config: AgentRuntimeConfig = field(default_factory=AgentRuntimeConfig)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    memory_summary: str = ""
    usage_records: list[AgentUsageRecord] = field(default_factory=list)
    cancelled: bool = False
    schema_version: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "permission_mode": self.permission_mode.value,
            "provider_id": self.provider_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [message.to_dict() for message in self.messages],
            "pending_actions": [action.to_dict() for action in self.pending_actions],
            "events": [event.to_dict() for event in self.events],
            "active_turn": self.active_turn.to_dict() if self.active_turn is not None else None,
            "suspended_turn": self.suspended_turn.to_dict() if self.suspended_turn is not None else None,
            "runtime_config": self.runtime_config.to_dict(),
            "provider_metadata": dict(self.provider_metadata),
            "memory_summary": self.memory_summary,
            "usage_records": [record.to_dict() for record in self.usage_records],
            "cancelled": self.cancelled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSession":
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            session_id=str(data.get("session_id", "")),
            permission_mode=AgentPermissionMode(str(data.get("permission_mode", AgentPermissionMode.CONFIRM_ACTIONS.value))),
            provider_id=str(data.get("provider_id", "fake")),
            title=str(data.get("title", "")),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
            messages=[AgentMessage.from_dict(item) for item in data.get("messages", [])],
            pending_actions=[AgentActionRequest.from_dict(item) for item in data.get("pending_actions", [])],
            events=[AgentEvent.from_dict(item) for item in data.get("events", [])],
            active_turn=AgentTurnState.from_dict(data["active_turn"]) if isinstance(data.get("active_turn"), dict) else None,
            suspended_turn=AgentSuspension.from_dict(data["suspended_turn"])
            if isinstance(data.get("suspended_turn"), dict)
            else None,
            runtime_config=AgentRuntimeConfig(**dict(data.get("runtime_config", {})))
            if isinstance(data.get("runtime_config"), dict)
            else AgentRuntimeConfig(),
            provider_metadata=dict(data.get("provider_metadata", {})) if isinstance(data.get("provider_metadata"), dict) else {},
            memory_summary=str(data.get("memory_summary", "")),
            usage_records=[AgentUsageRecord.from_dict(item) for item in data.get("usage_records", [])]
            if isinstance(data.get("usage_records"), list)
            else [],
            cancelled=bool(data.get("cancelled", False)),
        )
