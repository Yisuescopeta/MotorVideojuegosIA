from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.agent.types import utc_now_iso


DEFAULT_OPENCODE_GO_BASE_URL = "https://opencode.ai/zen/go/v1/chat/completions"
DEFAULT_OPENCODE_GO_MODEL = "opencode-go/kimi-k2.5"
DEFAULT_OPENAI_MODEL = "gpt-5"


@dataclass(frozen=True)
class AgentProviderLoginStatus:
    provider_id: str
    auth_status: str = "missing"
    credential_source: str = "none"
    login_supported: bool = False
    base_url: str = ""
    model: str = ""
    updated_at: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "auth_status": self.auth_status,
            "credential_source": self.credential_source,
            "login_supported": self.login_supported,
            "base_url": self.base_url,
            "model": self.model,
            "updated_at": self.updated_at,
            "error": self.error,
        }


class AgentCredentialStore:
    """User-local credential store. Secrets are never written to project state."""

    FILE_NAME = "agent_credentials.json"

    def __init__(self, global_state_dir: str | Path | None = None) -> None:
        self.global_state_dir = self._resolve_global_state_dir(global_state_dir)
        self.path = self.global_state_dir / self.FILE_NAME

    def supports_local_secrets(self) -> bool:
        return os.name == "nt" and _WindowsDPAPI.available()

    def save_api_key(self, provider_id: str, api_key: str) -> None:
        secret = str(api_key or "").strip()
        if not secret:
            raise ValueError("API key is required.")
        if not self.supports_local_secrets():
            raise RuntimeError("Local credential storage requires Windows DPAPI. Use provider environment variables instead.")
        data = self._load()
        provider = data.setdefault("providers", {}).setdefault(provider_id, {})
        provider["encrypted_api_key"] = _WindowsDPAPI.protect(secret.encode("utf-8"))
        provider["encryption"] = "dpapi"
        provider["credential_source"] = "user_local"
        provider["updated_at"] = utc_now_iso()
        self._save(data)

    def load_api_key(self, provider_id: str) -> str:
        data = self._load()
        provider = data.get("providers", {}).get(provider_id, {})
        encrypted = str(provider.get("encrypted_api_key", ""))
        if not encrypted:
            return ""
        if provider.get("encryption") != "dpapi":
            return ""
        try:
            return _WindowsDPAPI.unprotect(encrypted).decode("utf-8")
        except Exception:
            return ""

    def delete_api_key(self, provider_id: str) -> None:
        data = self._load()
        provider = data.setdefault("providers", {}).setdefault(provider_id, {})
        provider.pop("encrypted_api_key", None)
        provider["credential_source"] = "none"
        provider["updated_at"] = utc_now_iso()
        self._save(data)

    def credential_source(self, provider_id: str, env_key: str = "") -> str:
        if env_key and os.environ.get(env_key, "").strip():
            return "env"
        if self.load_api_key(provider_id):
            return "user_local"
        return "none"

    def _resolve_global_state_dir(self, global_state_dir: str | Path | None) -> Path:
        if global_state_dir is not None:
            return Path(global_state_dir).expanduser().resolve()
        env_override = os.environ.get("MOTORVIDEOJUEGOSIA_HOME", "").strip()
        if env_override:
            return Path(env_override).expanduser().resolve()
        return (Path.home() / ".motorvideojuegosia").resolve()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": 1, "providers": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"schema_version": 1, "providers": {}}
        if not isinstance(data, dict):
            return {"schema_version": 1, "providers": {}}
        data.setdefault("schema_version", 1)
        data.setdefault("providers", {})
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


class AgentProviderSettingsStore:
    """Project-local non-secret provider preferences."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / ".motor" / "agent_state" / "provider_settings.json"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return self._default()
        if not isinstance(data, dict):
            return self._default()
        default = self._default()
        default.update({key: value for key, value in data.items() if key != "api_key"})
        return default

    def set_default_provider(self, provider_id: str, *, model: str = "", base_url: str = "", stream: bool | None = None) -> dict[str, Any]:
        data = self.load()
        data["default_provider_id"] = str(provider_id or "fake")
        if model:
            data["model"] = str(model)
        if base_url:
            data["base_url"] = str(base_url)
        if stream is not None:
            data["stream"] = bool(stream)
        data["updated_at"] = utc_now_iso()
        self.save(data)
        return data

    def save(self, data: dict[str, Any]) -> None:
        safe = {key: value for key, value in data.items() if "key" not in key.lower() and "secret" not in key.lower()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(safe, indent=2, ensure_ascii=True), encoding="utf-8")

    def _default(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "default_provider_id": "fake",
            "model": "",
            "base_url": "",
            "stream": True,
            "updated_at": "",
        }


class AgentProviderLoginService:
    def __init__(self, *, credential_store: AgentCredentialStore, settings_store: AgentProviderSettingsStore) -> None:
        self.credential_store = credential_store
        self.settings_store = settings_store

    def login(self, provider_id: str, *, api_key: str, base_url: str = "", model: str = "") -> dict[str, Any]:
        provider_id = self._normalize_provider(provider_id)
        self.credential_store.save_api_key(provider_id, api_key)
        defaults = self.provider_defaults(provider_id)
        settings = self.settings_store.set_default_provider(
            provider_id,
            model=model or defaults["model"],
            base_url=base_url or defaults["base_url"],
            stream=True,
        )
        return {
            "provider": self.status(provider_id).to_dict(),
            "settings": settings,
            "message": f"Provider {provider_id} configured.",
        }

    def logout(self, provider_id: str) -> dict[str, Any]:
        provider_id = self._normalize_provider(provider_id)
        self.credential_store.delete_api_key(provider_id)
        settings = self.settings_store.load()
        if settings.get("default_provider_id") == provider_id:
            settings = self.settings_store.set_default_provider("fake", model="fake", base_url="", stream=False)
        return {
            "provider": self.status(provider_id).to_dict(),
            "settings": settings,
            "message": f"Provider {provider_id} logged out.",
        }

    def set_default_provider(self, provider_id: str, *, model: str = "", base_url: str = "") -> dict[str, Any]:
        provider_id = self._normalize_provider(provider_id)
        defaults = self.provider_defaults(provider_id)
        return self.settings_store.set_default_provider(
            provider_id,
            model=model or defaults["model"],
            base_url=base_url or defaults["base_url"],
            stream=provider_id != "fake",
        )

    def default_provider_settings(self) -> dict[str, Any]:
        return self.settings_store.load()

    def status(self, provider_id: str) -> AgentProviderLoginStatus:
        provider_id = self._normalize_provider(provider_id)
        defaults = self.provider_defaults(provider_id)
        env_key = self.env_key(provider_id)
        source = self.credential_store.credential_source(provider_id, env_key)
        auth_status = "configured" if source in {"env", "user_local"} else "missing"
        return AgentProviderLoginStatus(
            provider_id=provider_id,
            auth_status=auth_status,
            credential_source=source,
            login_supported=provider_id in {"opencode-go", "openai"},
            base_url=defaults["base_url"],
            model=defaults["model"],
            updated_at=utc_now_iso() if auth_status == "configured" else "",
        )

    def api_key(self, provider_id: str) -> str:
        provider_id = self._normalize_provider(provider_id)
        env_key = self.env_key(provider_id)
        if env_key and os.environ.get(env_key, "").strip():
            return os.environ[env_key].strip()
        return self.credential_store.load_api_key(provider_id)

    def provider_defaults(self, provider_id: str) -> dict[str, str]:
        provider_id = self._normalize_provider(provider_id)
        if provider_id == "opencode-go":
            return {"base_url": DEFAULT_OPENCODE_GO_BASE_URL, "model": DEFAULT_OPENCODE_GO_MODEL}
        if provider_id == "openai":
            return {"base_url": "https://api.openai.com/v1/responses", "model": DEFAULT_OPENAI_MODEL}
        return {"base_url": "", "model": provider_id if provider_id == "fake" else ""}

    def env_key(self, provider_id: str) -> str:
        provider_id = self._normalize_provider(provider_id)
        if provider_id == "openai":
            return "OPENAI_API_KEY"
        if provider_id == "opencode-go":
            return "OPENCODE_GO_API_KEY"
        return ""

    def _normalize_provider(self, provider_id: str) -> str:
        value = str(provider_id or "opencode-go").strip().lower()
        return "opencode-go" if value in {"opencode", "opencodego", "go"} else value


class _WindowsDPAPI:
    CRYPTPROTECT_UI_FORBIDDEN = 0x01

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    @classmethod
    def available(cls) -> bool:
        return os.name == "nt" and hasattr(ctypes, "windll")

    @classmethod
    def protect(cls, payload: bytes) -> str:
        if not cls.available():
            raise RuntimeError("Windows DPAPI is not available.")
        in_blob, in_buffer = cls._blob_from_bytes(payload)
        out_blob = cls.DATA_BLOB()
        if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            cls.CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        ):
            raise ctypes.WinError()
        try:
            encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return base64.b64encode(encrypted).decode("ascii")
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)

    @classmethod
    def unprotect(cls, payload: str) -> bytes:
        if not cls.available():
            raise RuntimeError("Windows DPAPI is not available.")
        raw = base64.b64decode(payload.encode("ascii"))
        in_blob, in_buffer = cls._blob_from_bytes(raw)
        out_blob = cls.DATA_BLOB()
        if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            cls.CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        ):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)

    @classmethod
    def _blob_from_bytes(cls, payload: bytes):
        buffer = ctypes.create_string_buffer(payload)
        return cls.DATA_BLOB(len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer
