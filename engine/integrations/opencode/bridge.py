from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from engine.integrations.opencode.artifacts import ensure_opencode_artifact_dir, write_json_artifact
from engine.integrations.opencode.backend_manager import OpenCodeBackendManager
from engine.integrations.opencode.session_controller import OpenCodeSessionController


class OpenCodeBridge:
    """Project-local OpenCode facade shared by CLI and editor."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.backend = OpenCodeBackendManager(self.project_root)
        self.sessions = OpenCodeSessionController(self.project_root, backend_manager=self.backend)

    def get_health(self) -> Dict[str, Any]:
        return self.backend.get_health()

    def get_connection_status(self) -> Dict[str, Any]:
        return self.backend.get_connection_status()

    def get_last_error(self) -> str:
        return self.backend.get_last_error() or self.sessions.last_error

    def connect(self) -> Dict[str, Any]:
        self.sessions.refresh_connection()
        return self.sessions.get_snapshot()

    def reconnect(self) -> Dict[str, Any]:
        return self.connect()

    def ensure_server(self) -> Dict[str, Any]:
        return self.sessions.ensure_backend()

    def start_visible(self) -> Dict[str, Any]:
        return self.sessions.start_visible()

    def start_server(self) -> Dict[str, Any]:
        status = self.backend.start_server()
        snapshot = self.sessions.get_snapshot()
        snapshot["connection_status"] = status
        return snapshot

    def server_status(self) -> Dict[str, Any]:
        return self.backend.connect()

    def stop_server(self) -> Dict[str, Any]:
        return self.sessions.stop_backend()

    def load_initial_state(self) -> Dict[str, Any]:
        return self.sessions.load_initial_state()

    def refresh_sessions(self) -> Dict[str, Any]:
        return self.sessions.refresh_sessions()

    def list_sessions(self) -> List[Dict[str, Any]]:
        return self.sessions.refresh_sessions()["sessions"]

    def create_session(self, title: str) -> Dict[str, Any]:
        snapshot = self.sessions.create_and_select_session(title)
        return {
            "id": snapshot.get("active_session_id", ""),
            "title": title,
        }

    def create_and_select_session(self, title: str) -> Dict[str, Any]:
        return self.sessions.create_and_select_session(title)

    def select_session(self, session_id: str, limit: int = 100) -> Dict[str, Any]:
        return self.sessions.select_session(session_id, limit=limit)

    def refresh_active_session(self, limit: int = 100, message_id: str | None = None) -> Dict[str, Any]:
        return self.sessions.refresh_active_session(limit=limit, message_id=message_id)

    def get_session_view(self, session_id: str, limit: int = 100, message_id: str | None = None) -> Dict[str, Any]:
        snapshot = self.sessions.select_session(session_id, limit=limit)
        if message_id:
            snapshot = self.sessions.refresh_active_session(limit=limit, message_id=message_id)
        return snapshot

    def get_messages(self, session_id: str, limit: int | None = None) -> List[Dict[str, Any]]:
        snapshot = self.sessions.select_session(session_id, limit=limit or 100)
        return [item for item in snapshot.get("messages", []) if isinstance(item, dict)]

    def get_diff(self, session_id: str, message_id: str | None = None) -> List[Dict[str, Any]]:
        snapshot = self.sessions.select_session(session_id, limit=100)
        if message_id:
            snapshot = self.sessions.refresh_active_session(limit=100, message_id=message_id)
        return [item for item in snapshot.get("diff", []) if isinstance(item, dict)]

    def list_pending_permissions(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        snapshot = self.sessions.select_session(session_id, limit=limit)
        return [item for item in snapshot.get("approvals", []) if isinstance(item, dict)]

    def respond_permission(self, session_id: str, permission_id: str, response: str, remember: bool = False) -> Dict[str, Any]:
        self.sessions.select_session(session_id)
        snapshot = self.sessions.respond_permission(permission_id, response=response, remember=remember)
        return {
            "session_id": session_id,
            "permission_id": permission_id,
            "response": response,
            "remember": remember,
            "accepted": True,
            "snapshot": snapshot,
        }

    def send_prompt(
        self,
        session_id: str,
        text: str,
        *,
        agent: str = "plan",
        model: str | None = None,
        wait: bool = True,
        out_dir: str | Path = "",
    ) -> Dict[str, Any]:
        self.sessions.select_session(session_id)
        snapshot = self.sessions.send_prompt(text=text, agent=agent, model=model, out_dir=out_dir)
        return {
            "session_id": session_id,
            "agent": agent,
            "wait": wait,
            **snapshot.get("last_artifacts", {}),
            "snapshot": snapshot,
        }

    def send_message(
        self,
        session_id: str,
        text: str,
        *,
        agent: str = "plan",
        model: str | None = None,
        out_dir: str | Path = "",
    ) -> Dict[str, Any]:
        return self.send_prompt(session_id, text, agent=agent, model=model, out_dir=out_dir)

    def export_diff_artifact(self, session_id: str, *, message_id: str | None = None, out_dir: str | Path = "") -> Dict[str, Any]:
        self.sessions.select_session(session_id)
        return self.sessions.export_diff_artifact(out_dir=out_dir, message_id=message_id)

    def export_messages_artifact(self, session_id: str, *, limit: int | None = None, out_dir: str | Path = "") -> Dict[str, Any]:
        self.sessions.select_session(session_id, limit=limit or 100)
        return self.sessions.export_messages_artifact(out_dir=out_dir, limit=limit)

    def refresh_session_view(self, session_id: str, *, limit: int = 100, message_id: str | None = None) -> Dict[str, Any]:
        return self.get_session_view(session_id, limit=limit, message_id=message_id)
