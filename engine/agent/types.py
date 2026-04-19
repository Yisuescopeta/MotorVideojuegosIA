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
    MESSAGE_ADDED = "message_added"
    TOOL_CALLED = "tool_called"
    ACTION_REQUESTED = "action_requested"
    ACTION_APPROVED = "action_approved"
    ACTION_REJECTED = "action_rejected"
    SESSION_CANCELLED = "session_cancelled"


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


@dataclass
class AgentMessage:
    message_id: str
    role: AgentMessageRole
    content: str
    created_at: str = field(default_factory=utc_now_iso)
    tool_calls: list[AgentToolCall] = field(default_factory=list)
    tool_result: AgentToolResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "role": self.role.value,
            "content": self.content,
            "created_at": self.created_at,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "tool_result": self.tool_result.to_dict() if self.tool_result is not None else None,
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
            tool_result=AgentToolResult(**tool_result_data) if isinstance(tool_result_data, dict) else None,
        )


@dataclass
class AgentActionRequest:
    action_id: str
    tool_call: AgentToolCall
    reason: str
    preview: str = ""
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
            status=AgentActionStatus(str(data.get("status", AgentActionStatus.PENDING.value))),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            resolved_at=str(data.get("resolved_at", "")),
            result=AgentToolResult(**result_data) if isinstance(result_data, dict) else None,
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
    cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "permission_mode": self.permission_mode.value,
            "provider_id": self.provider_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [message.to_dict() for message in self.messages],
            "pending_actions": [action.to_dict() for action in self.pending_actions],
            "events": [event.to_dict() for event in self.events],
            "cancelled": self.cancelled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentSession":
        return cls(
            session_id=str(data.get("session_id", "")),
            permission_mode=AgentPermissionMode(str(data.get("permission_mode", AgentPermissionMode.CONFIRM_ACTIONS.value))),
            provider_id=str(data.get("provider_id", "fake")),
            title=str(data.get("title", "")),
            created_at=str(data.get("created_at", "")) or utc_now_iso(),
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
            messages=[AgentMessage.from_dict(item) for item in data.get("messages", [])],
            pending_actions=[AgentActionRequest.from_dict(item) for item in data.get("pending_actions", [])],
            events=[AgentEvent.from_dict(item) for item in data.get("events", [])],
            cancelled=bool(data.get("cancelled", False)),
        )
