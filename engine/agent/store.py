from __future__ import annotations

import json
from pathlib import Path

from engine.agent.ids import resolve_agent_session_path, validate_agent_session_id
from engine.agent.migration import AgentSessionMigrationError, AgentSessionMigrator
from engine.agent.types import AgentEvent, AgentSession


class AgentSessionStore:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.state_dir = self.project_root / ".motor" / "agent_state"
        self.sessions_dir = self.state_dir / "sessions"
        self.events_dir = self.state_dir / "events"
        self.audit_path = self.state_dir / "audit.jsonl"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.migrator = AgentSessionMigrator()

    def save_session(self, session: AgentSession) -> None:
        session_path = resolve_agent_session_path(self.sessions_dir, session.session_id, ".json")
        session_path.write_text(json.dumps(session.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8")

    def load_session(self, session_id: str) -> AgentSession:
        valid_id = validate_agent_session_id(session_id)
        session_path = resolve_agent_session_path(self.sessions_dir, valid_id, ".json")
        if not session_path.exists():
            raise KeyError(f"Agent session not found: {valid_id}")
        raw = session_path.read_text(encoding="utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AgentSessionMigrationError(f"Agent session file is corrupt and was not migrated: {session_path}") from exc
        result = self.migrator.migrate_payload(payload)
        if result.migrated:
            backup_path = session_path.with_name(f"{session_path.stem}.legacy-v1.bak")
            if not backup_path.exists():
                backup_path.write_text(raw, encoding="utf-8")
            temp_path = session_path.with_suffix(session_path.suffix + ".tmp")
            temp_path.write_text(json.dumps(result.payload, indent=2, ensure_ascii=True), encoding="utf-8")
            temp_path.replace(session_path)
            if result.event is not None:
                self.append_event(valid_id, AgentEvent.from_dict(result.event))
        return AgentSession.from_dict(result.payload)

    def append_event(self, session_id: str, event: AgentEvent) -> None:
        valid_id = validate_agent_session_id(session_id)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        payload = {"session_id": valid_id, **event.to_dict()}
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
        event_path = resolve_agent_session_path(self.events_dir, valid_id, ".jsonl")
        with event_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
