from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.agent.ids import resolve_agent_session_path, validate_agent_session_id
from engine.agent.types import AgentMessage, AgentMessageRole, AgentSession, AgentUsageRecord, new_id, utc_now_iso


PROTECTED_MEMORY_PATTERN = re.compile(r"(Claude Code|\.git|\.motor)", re.IGNORECASE)
SECRET_MEMORY_PATTERN = re.compile(
    r"(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}|BEGIN [A-Z ]*PRIVATE KEY",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AgentMemorySnapshot:
    schema_version: int = 1
    session_id: str = ""
    session_summary: str = ""
    project_memory_enabled: bool = False
    project_memory: str = ""
    errors: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "session_summary": self.session_summary,
            "project_memory_enabled": self.project_memory_enabled,
            "project_memory": self.project_memory,
            "errors": list(self.errors),
            "updated_at": self.updated_at,
        }


class AgentMemoryStore:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.memory_dir = self.project_root / ".motor" / "agent_state" / "memory"
        self.usage_dir = self.project_root / ".motor" / "agent_state" / "usage"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.usage_dir.mkdir(parents=True, exist_ok=True)

    def save_session_summary(self, session_id: str, summary: str) -> AgentMemorySnapshot:
        valid_id = validate_agent_session_id(session_id)
        snapshot = AgentMemorySnapshot(session_id=valid_id, session_summary=self._sanitize(summary))
        path = resolve_agent_session_path(self.memory_dir, valid_id, ".json")
        path.write_text(json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8")
        return snapshot

    def load_session_summary(self, session_id: str) -> AgentMemorySnapshot:
        valid_id = validate_agent_session_id(session_id)
        path = resolve_agent_session_path(self.memory_dir, valid_id, ".json")
        if not path.exists():
            return AgentMemorySnapshot(session_id=valid_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return AgentMemorySnapshot(session_id=valid_id, errors=[f"Memory file is corrupt and was ignored: {exc}"])
        if not isinstance(data, dict):
            return AgentMemorySnapshot(session_id=valid_id, errors=["Memory file is invalid and was ignored."])
        return AgentMemorySnapshot(
            schema_version=int(data.get("schema_version", 1)),
            session_id=valid_id,
            session_summary=self._sanitize(str(data.get("session_summary", ""))),
            project_memory_enabled=bool(data.get("project_memory_enabled", False)),
            project_memory=self._sanitize(str(data.get("project_memory", ""))),
            errors=[str(error) for error in data.get("errors", []) if str(error).strip()],
            updated_at=str(data.get("updated_at", "")) or utc_now_iso(),
        )

    def append_usage(self, session_id: str, record: AgentUsageRecord) -> None:
        path = resolve_agent_session_path(self.usage_dir, session_id, ".jsonl")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=True) + "\n")

    def _sanitize(self, text: str) -> str:
        lines = []
        for line in str(text).splitlines():
            if PROTECTED_MEMORY_PATTERN.search(line) or SECRET_MEMORY_PATTERN.search(line):
                continue
            lines.append(line)
        return "\n".join(lines).strip()


class AgentCompactionService:
    def __init__(self, memory_store: AgentMemoryStore) -> None:
        self.memory_store = memory_store

    def compact(self, session: AgentSession, *, keep_last: int | None = None) -> dict[str, Any]:
        pending = [action for action in session.pending_actions if str(action.status) == "pending" or action.status.value == "pending"]
        if pending:
            return {"compacted": False, "reason": "Cannot compact while agent actions are pending."}
        budget = max(4, int(keep_last or session.runtime_config.compaction_message_budget or 24))
        if len(session.messages) <= budget:
            snapshot = self.memory_store.save_session_summary(session.session_id, session.memory_summary)
            return {"compacted": False, "reason": "Session is already within compaction budget.", "memory": snapshot.to_dict()}

        compacted = session.messages[:-budget]
        retained = session.messages[-budget:]
        previous = session.memory_summary.strip()
        summary = self._summarize(previous, compacted)
        session.memory_summary = summary
        session.messages = retained
        snapshot = self.memory_store.save_session_summary(session.session_id, summary)
        return {
            "compacted": True,
            "removed_messages": len(compacted),
            "retained_messages": len(retained),
            "memory": snapshot.to_dict(),
        }

    def _summarize(self, previous: str, messages: list[AgentMessage]) -> str:
        lines: list[str] = []
        if previous:
            lines.append(previous)
        lines.append(f"Compaction {new_id('compact')} at {utc_now_iso()}:")
        for message in messages:
            if message.role == AgentMessageRole.TOOL and message.tool_result is not None:
                status = "ok" if message.tool_result.success else "failed"
                text = f"tool {message.tool_result.tool_name} {status}: {message.tool_result.output or message.tool_result.error}"
            else:
                text = f"{message.role.value}: {message.content}"
            text = text.replace("\n", " ").strip()
            if PROTECTED_MEMORY_PATTERN.search(text) or SECRET_MEMORY_PATTERN.search(text):
                continue
            if text:
                lines.append(text[:260])
        return "\n".join(lines)[-8000:].strip()
