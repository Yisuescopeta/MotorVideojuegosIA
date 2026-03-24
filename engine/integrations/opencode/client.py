from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from urllib import error, parse, request

from engine.integrations.opencode.server import OpenCodeServerConfig


class OpenCodeClientError(RuntimeError):
    """Base error for OpenCode HTTP client failures."""


class OpenCodeHTTPError(OpenCodeClientError):
    """Raised when the OpenCode server returns an HTTP error."""


class OpenCodeClient:
    """Minimal OpenCode HTTP client for session-oriented automation."""

    def __init__(
        self,
        project_root: str | os.PathLike[str] = ".",
        base_url: str | None = None,
        config_path: str | os.PathLike[str] | None = None,
        username: str = "opencode",
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self._config = OpenCodeServerConfig.load(self.project_root, config_path)
        self._username = str(username or "opencode").strip() or "opencode"
        self.base_url = (base_url or f"http://{self._config.hostname}:{self._config.port}").rstrip("/")
        self._artifacts_root = self.project_root / "artifacts" / "opencode" / "sessions"

    @property
    def artifacts_root(self) -> Path:
        return self._artifacts_root

    def create_session(self, title: str) -> Dict[str, Any]:
        payload = {"title": str(title or "").strip() or "OpenCode Session"}
        response = self._request_json("POST", "/session", body=payload)
        if not isinstance(response, dict):
            raise OpenCodeClientError("OpenCode returned an invalid session payload")
        return response

    def list_sessions(self) -> List[Dict[str, Any]]:
        payload = self._request_json("GET", "/session")
        if not isinstance(payload, list):
            raise OpenCodeClientError("OpenCode returned an invalid session list payload")
        return [item for item in payload if isinstance(item, dict)]

    def get_session(self, session_id: str) -> Dict[str, Any]:
        payload = self._request_json("GET", f"/session/{parse.quote(session_id, safe='')}")
        if not isinstance(payload, dict):
            raise OpenCodeClientError("OpenCode returned an invalid session detail payload")
        return payload

    def send_message(
        self,
        session_id: str,
        text: str,
        agent: str = "plan",
        model: Any = None,
        wait: bool = True,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "agent": "build" if str(agent or "").strip() == "build" else "plan",
            "parts": [{"type": "text", "text": str(text or "")}],
        }
        model_payload = self._normalize_model(model)
        if model_payload is not None:
            payload["model"] = model_payload
        path = f"/session/{parse.quote(session_id, safe='')}/message" if wait else f"/session/{parse.quote(session_id, safe='')}/prompt_async"
        response = self._request_json("POST", path, body=payload, allow_empty=not wait)
        if wait:
            self._write_session_artifacts(session_id)
        if not wait:
            return {"accepted": True}
        if not isinstance(response, dict):
            raise OpenCodeClientError("OpenCode returned an invalid message payload")
        return response

    def get_messages(self, session_id: str, limit: int | None = None) -> List[Dict[str, Any]]:
        query = {"limit": int(limit)} if limit is not None else None
        payload = self._request_json("GET", f"/session/{parse.quote(session_id, safe='')}/message", query=query)
        if not isinstance(payload, list):
            raise OpenCodeClientError("OpenCode returned an invalid messages payload")
        return [item for item in payload if isinstance(item, dict)]

    def get_diff(self, session_id: str, message_id: str | None = None) -> List[Dict[str, Any]]:
        query = {"messageID": message_id} if message_id else None
        payload = self._request_json("GET", f"/session/{parse.quote(session_id, safe='')}/diff", query=query)
        if not isinstance(payload, list):
            raise OpenCodeClientError("OpenCode returned an invalid diff payload")
        diff = [item for item in payload if isinstance(item, dict)]
        self._write_json(self._session_artifact_path(session_id, "diff.json"), diff)
        return diff

    def respond_permission(
        self,
        session_id: str,
        permission_id: str,
        response: str,
        remember: bool | None = None,
    ) -> bool:
        payload: Dict[str, Any] = {"response": str(response or "").strip()}
        if remember is not None:
            payload["remember"] = bool(remember)
        result = self._request_json(
            "POST",
            f"/session/{parse.quote(session_id, safe='')}/permissions/{parse.quote(permission_id, safe='')}",
            body=payload,
        )
        return bool(result)

    def stream_events(self) -> Iterator[Dict[str, Any]]:
        req = self._build_request("GET", "/event")
        try:
            response = request.urlopen(req, timeout=self._config.health_timeout_seconds)
        except error.HTTPError as exc:
            raise self._http_error(exc) from exc
        except error.URLError as exc:
            raise OpenCodeClientError(f"OpenCode event stream failed: {exc.reason}") from exc

        def _generator() -> Iterator[Dict[str, Any]]:
            event_type = "message"
            event_id = ""
            data_lines: List[str] = []
            try:
                for raw_line in response:
                    line = raw_line.decode("utf-8").rstrip("\r\n")
                    if not line:
                        emitted = self._build_sse_event(event_type, event_id, data_lines)
                        if emitted is not None:
                            yield emitted
                        event_type = "message"
                        event_id = ""
                        data_lines = []
                        continue
                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip() or "message"
                        continue
                    if line.startswith("id:"):
                        event_id = line.split(":", 1)[1].strip()
                        continue
                    if line.startswith("data:"):
                        data_lines.append(line.split(":", 1)[1].lstrip())
                emitted = self._build_sse_event(event_type, event_id, data_lines)
                if emitted is not None:
                    yield emitted
            finally:
                try:
                    response.close()
                except Exception:
                    pass

        return _generator()

    def export_transcript(self, session_id: str, out_path: str | os.PathLike[str]) -> Path:
        messages = self.get_messages(session_id)
        path = Path(out_path)
        if not path.is_absolute():
            path = (self.project_root / path).resolve()
        self._write_json(path, messages)
        self._write_json(self._session_artifact_path(session_id, "transcript.json"), messages)
        return path

    def list_pending_permissions(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        messages = self.get_messages(session_id, limit=limit)
        pending: List[Dict[str, Any]] = []
        for message in messages:
            info = message.get("info", {}) if isinstance(message, dict) else {}
            parts = message.get("parts", []) if isinstance(message, dict) else []
            for part in parts:
                candidate = self._extract_permission_part(part, info)
                if candidate is not None:
                    pending.append(candidate)
        return pending

    def _write_session_artifacts(self, session_id: str) -> None:
        self.export_transcript(session_id, self._session_artifact_path(session_id, "transcript.json"))
        try:
            self.get_diff(session_id)
        except OpenCodeClientError:
            pass

    def _session_artifact_path(self, session_id: str, filename: str) -> Path:
        return self._artifacts_root / session_id / filename

    def _normalize_model(self, model: Any) -> Optional[Dict[str, Any]]:
        if model is None:
            return None
        if isinstance(model, dict):
            normalized = {str(key): value for key, value in model.items() if value is not None}
            return normalized or None
        text = str(model).strip()
        if not text:
            return None
        return {"modelID": text}

    def _build_request(
        self,
        method: str,
        path: str,
        body: Dict[str, Any] | None = None,
        query: Dict[str, Any] | None = None,
    ) -> request.Request:
        url = f"{self.base_url}{path}"
        if query:
            encoded = parse.urlencode({key: value for key, value in query.items() if value is not None})
            if encoded:
                url = f"{url}?{encoded}"
        req = request.Request(url=url, method=method.upper())
        if self._config.password:
            token = base64.b64encode(f"{self._username}:{self._config.password}".encode("utf-8")).decode("ascii")
            req.add_header("Authorization", f"Basic {token}")
        if body is not None:
            req.data = json.dumps(body).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        return req

    def _request_json(
        self,
        method: str,
        path: str,
        body: Dict[str, Any] | None = None,
        query: Dict[str, Any] | None = None,
        allow_empty: bool = False,
    ) -> Any:
        req = self._build_request(method, path, body=body, query=query)
        timeout = max(self._config.startup_timeout_seconds, self._config.health_timeout_seconds)
        try:
            with request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
        except error.HTTPError as exc:
            raise self._http_error(exc) from exc
        except error.URLError as exc:
            raise OpenCodeClientError(f"OpenCode request failed: {exc.reason}") from exc
        if not raw:
            return {} if allow_empty else {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise OpenCodeClientError("OpenCode returned invalid JSON") from exc

    def _http_error(self, exc: error.HTTPError) -> OpenCodeHTTPError:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""
        suffix = f": {body}" if body else ""
        return OpenCodeHTTPError(f"OpenCode request failed with HTTP {exc.code}{suffix}")

    def _build_sse_event(self, event_type: str, event_id: str, data_lines: List[str]) -> Optional[Dict[str, Any]]:
        if not data_lines and not event_id:
            return None
        data_text = "\n".join(data_lines).strip()
        properties: Any = data_text
        if data_text:
            try:
                properties = json.loads(data_text)
            except json.JSONDecodeError:
                properties = data_text
        return {
            "type": event_type or "message",
            "id": event_id,
            "properties": properties,
        }

    def _extract_permission_part(self, part: Any, message_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(part, dict):
            return None
        part_type = str(part.get("type", "") or "").lower()
        permission_id = part.get("permissionID", part.get("permissionId", part.get("id", "")))
        if not permission_id:
            return None
        if "permission" not in part_type and "permission" not in json.dumps(part, ensure_ascii=True).lower():
            return None
        status = str(part.get("status", part.get("state", "pending")) or "pending").lower()
        if status not in {"pending", "ask", "requested", ""}:
            return None
        return {
            "permission_id": str(permission_id),
            "message_id": str(message_info.get("id", "") or part.get("messageID", "")),
            "type": part.get("type", ""),
            "tool": part.get("tool", part.get("name", "")),
            "pattern": part.get("pattern", ""),
            "description": part.get("description", part.get("title", "")),
            "raw": part,
        }

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4)
