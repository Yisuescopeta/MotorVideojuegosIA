from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from engine.integrations.opencode.artifacts import ensure_opencode_artifact_dir, write_json_artifact
from engine.integrations.opencode.backend_manager import OpenCodeBackendManager


class OpenCodeSessionController:
    def __init__(self, project_root: str | Path = ".", backend_manager: OpenCodeBackendManager | None = None) -> None:
        self.project_root = Path(project_root).resolve()
        self.backend_manager = backend_manager or OpenCodeBackendManager(self.project_root)
        self.active_session_id: str = ""
        self.sessions: List[Dict[str, Any]] = []
        self.messages: List[Dict[str, Any]] = []
        self.diff: List[Dict[str, Any]] = []
        self.approvals: List[Dict[str, Any]] = []
        self.last_error: str = ""
        self.last_operation: str = ""
        self.last_artifacts: Dict[str, str] = {}

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "connection_status": self.backend_manager.get_connection_status(),
            "active_session_id": self.active_session_id,
            "sessions": list(self.sessions),
            "messages": list(self.messages),
            "diff": list(self.diff),
            "approvals": list(self.approvals),
            "last_error": self.last_error,
            "last_operation": self.last_operation,
            "last_artifacts": dict(self.last_artifacts),
        }

    def load_initial_state(self) -> Dict[str, Any]:
        status = self.backend_manager.connect()
        if status.get("healthy"):
            self.refresh_sessions()
        else:
            self._clear_session_view()
            self.last_error = str(status.get("technical_detail", "") or "")
            self.last_operation = "connect"
        return self.get_snapshot()

    def refresh_connection(self) -> Dict[str, Any]:
        status = self.backend_manager.connect()
        self.last_operation = "connect"
        if status.get("healthy"):
            self.refresh_sessions()
        else:
            self.last_error = str(status.get("technical_detail", "") or "")
        return self.get_snapshot()

    def start_visible(self) -> Dict[str, Any]:
        status = self.backend_manager.start_visible()
        self.last_operation = "start_visible"
        if status.get("healthy"):
            self.last_error = ""
            self.refresh_sessions()
        else:
            self.last_error = str(status.get("technical_detail", "") or "")
        return self.get_snapshot()

    def ensure_backend(self) -> Dict[str, Any]:
        status = self.backend_manager.ensure_server()
        self.last_operation = "ensure_server"
        if status.get("healthy"):
            self.last_error = ""
            self.refresh_sessions()
        else:
            self.last_error = str(status.get("technical_detail", "") or "")
        return self.get_snapshot()

    def stop_backend(self) -> Dict[str, Any]:
        self.backend_manager.stop_server()
        self._clear_session_view()
        self.last_operation = "stop_server"
        return self.get_snapshot()

    def refresh_sessions(self) -> Dict[str, Any]:
        client = self.backend_manager.create_client()
        self.sessions = client.list_sessions()
        self.last_error = ""
        self.last_operation = "refresh_sessions"
        if self.active_session_id:
            available = {str(item.get("id", "") or "") for item in self.sessions}
            if self.active_session_id not in available:
                self.active_session_id = ""
                self._clear_session_view(keep_sessions=True)
        if not self.active_session_id and self.sessions:
            self.active_session_id = self._pick_default_session_id(self.sessions)
        if self.active_session_id:
            return self.refresh_active_session()
        return self.get_snapshot()

    def select_session(self, session_id: str, limit: int = 100) -> Dict[str, Any]:
        self.active_session_id = str(session_id or "").strip()
        return self.refresh_active_session(limit=limit)

    def create_and_select_session(self, title: str, limit: int = 100) -> Dict[str, Any]:
        client = self.backend_manager.create_client()
        created = client.create_session(title=title)
        self.last_operation = "create_session"
        self.active_session_id = str(created.get("id", "") or "")
        self.refresh_sessions()
        if self.active_session_id:
            return self.refresh_active_session(limit=limit)
        return self.get_snapshot()

    def refresh_active_session(self, limit: int = 100, message_id: str | None = None) -> Dict[str, Any]:
        if not self.active_session_id:
            self._clear_session_view(keep_sessions=True)
            return self.get_snapshot()
        client = self.backend_manager.create_client()
        self.messages = client.get_messages(self.active_session_id, limit=limit)
        self.diff = client.get_diff(self.active_session_id, message_id=message_id)
        self.approvals = client.list_pending_permissions(self.active_session_id, limit=limit)
        self.last_error = ""
        self.last_operation = "refresh_session"
        return self.get_snapshot()

    def send_prompt(self, text: str, agent: str = "plan", model: str | None = None, out_dir: str | Path = "") -> Dict[str, Any]:
        if not self.active_session_id:
            default_title = f"OpenCode {self._timestamp_label()}"
            created = self.create_and_select_session(default_title)
            if not created.get("active_session_id"):
                raise RuntimeError("No active OpenCode session selected")
        client = self.backend_manager.create_client()
        output_dir = ensure_opencode_artifact_dir(self.active_session_id, out_dir=out_dir, project_root=self.project_root)
        response = client.send_message(self.active_session_id, text=text, agent=agent, model=model, wait=True)
        transcript_path = client.export_transcript(self.active_session_id, output_dir / "transcript.json")
        diff = client.get_diff(self.active_session_id)
        write_json_artifact(output_dir / "response.json", response)
        write_json_artifact(output_dir / "diff.json", diff)
        self.last_artifacts = {
            "artifact_dir": output_dir.as_posix(),
            "transcript_path": transcript_path.as_posix(),
            "diff_path": (output_dir / "diff.json").as_posix(),
        }
        write_json_artifact(output_dir / "manifest.json", {
            "session_id": self.active_session_id,
            "agent": agent,
            **self.last_artifacts,
        })
        self.last_operation = "send_prompt"
        return self.refresh_active_session()

    def respond_permission(self, permission_id: str, response: str, remember: bool = False) -> Dict[str, Any]:
        if not self.active_session_id:
            raise RuntimeError("No active OpenCode session selected")
        client = self.backend_manager.create_client()
        client.respond_permission(self.active_session_id, permission_id, response=response, remember=remember)
        self.last_operation = "respond_permission"
        return self.refresh_active_session()

    def export_diff_artifact(self, out_dir: str | Path = "", message_id: str | None = None) -> Dict[str, Any]:
        if not self.active_session_id:
            raise RuntimeError("No active OpenCode session selected")
        output_dir = ensure_opencode_artifact_dir(self.active_session_id, out_dir=out_dir, project_root=self.project_root)
        client = self.backend_manager.create_client()
        diff = client.get_diff(self.active_session_id, message_id=message_id)
        diff_path = write_json_artifact(output_dir / "diff.json", diff)
        manifest = {
            "session_id": self.active_session_id,
            "message_id": message_id or "",
            "artifact_dir": output_dir.as_posix(),
            "diff_path": diff_path.as_posix(),
        }
        write_json_artifact(output_dir / "manifest.json", manifest)
        self.last_artifacts = {
            "artifact_dir": manifest["artifact_dir"],
            "transcript_path": self.last_artifacts.get("transcript_path", ""),
            "diff_path": manifest["diff_path"],
        }
        self.last_operation = "export_diff"
        return manifest

    def export_messages_artifact(self, out_dir: str | Path = "", limit: int | None = None) -> Dict[str, Any]:
        if not self.active_session_id:
            raise RuntimeError("No active OpenCode session selected")
        output_dir = ensure_opencode_artifact_dir(self.active_session_id, out_dir=out_dir, project_root=self.project_root)
        client = self.backend_manager.create_client()
        messages = client.get_messages(self.active_session_id, limit=limit)
        transcript_path = write_json_artifact(output_dir / "transcript.json", messages)
        manifest = {
            "session_id": self.active_session_id,
            "limit": limit,
            "artifact_dir": output_dir.as_posix(),
            "transcript_path": transcript_path.as_posix(),
        }
        write_json_artifact(output_dir / "manifest.json", manifest)
        self.last_artifacts = {
            "artifact_dir": manifest["artifact_dir"],
            "transcript_path": manifest["transcript_path"],
            "diff_path": self.last_artifacts.get("diff_path", ""),
        }
        self.last_operation = "export_messages"
        return manifest

    def _clear_session_view(self, *, keep_sessions: bool = False) -> None:
        if not keep_sessions:
            self.sessions = []
        self.messages = []
        self.diff = []
        self.approvals = []
        self.last_artifacts = {}

    def _pick_default_session_id(self, sessions: List[Dict[str, Any]]) -> str:
        def _updated_key(item: Dict[str, Any]) -> str:
            return str(item.get("updatedAt", item.get("updated_at", "")) or "")

        ordered = sorted(sessions, key=_updated_key, reverse=True)
        return str((ordered[0].get("id", "") if ordered else "") or "")

    def _timestamp_label(self) -> str:
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H:%M")
