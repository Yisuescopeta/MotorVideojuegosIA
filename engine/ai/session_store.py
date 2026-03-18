from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from engine.ai.types import AISession


class AISessionStore:
    DIR_NAME = "ai_sessions"

    def __init__(self, project_service) -> None:
        self._project_service = project_service

    @property
    def sessions_dir(self) -> Path:
        if not self._project_service.has_project:
            return self._project_service.global_state_dir / self.DIR_NAME
        return self._project_service.get_project_path("meta") / self.DIR_NAME

    def save(self, session: AISession) -> AISession:
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        path = self.sessions_dir / f"{session.id}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(session.to_dict(), handle, indent=4)
        return session

    def load(self, session_id: str) -> Optional[AISession]:
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return AISession.from_dict(payload)

    def list_sessions(self) -> List[AISession]:
        if not self.sessions_dir.exists():
            return []
        result: List[AISession] = []
        for path in sorted(self.sessions_dir.glob("*.json")):
            session = self.load(path.stem)
            if session is not None:
                result.append(session)
        return result

    def delete(self, session_id: str) -> bool:
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return False
        path.unlink()
        return True

    def get_active_session_id(self) -> str:
        state = self._project_service.load_editor_state()
        return str(state.get("active_ai_session_id", "") or "")

    def set_active_session_id(self, session_id: str) -> None:
        state = self._project_service.load_editor_state()
        state["active_ai_session_id"] = session_id
        self._project_service.save_editor_state(state)

    def load_active(self) -> Optional[AISession]:
        active_id = self.get_active_session_id()
        if not active_id:
            return None
        return self.load(active_id)
