from __future__ import annotations

import json
from pathlib import Path

from engine.agent.types import AgentEvent, AgentSession


class AgentSessionStore:
    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.state_dir = self.project_root / ".motor" / "agent_state"
        self.sessions_dir = self.state_dir / "sessions"
        self.audit_path = self.state_dir / "audit.jsonl"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, session: AgentSession) -> None:
        session_path = self.sessions_dir / f"{session.session_id}.json"
        session_path.write_text(json.dumps(session.to_dict(), indent=2, ensure_ascii=True), encoding="utf-8")

    def load_session(self, session_id: str) -> AgentSession:
        session_path = self.sessions_dir / f"{session_id}.json"
        if not session_path.exists():
            raise KeyError(f"Agent session not found: {session_id}")
        return AgentSession.from_dict(json.loads(session_path.read_text(encoding="utf-8")))

    def append_event(self, session_id: str, event: AgentEvent) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {"session_id": session_id, **event.to_dict()}
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
