from __future__ import annotations

import base64
import ctypes
import json
import os
import shutil
import subprocess
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
    auth_method: str = ""
    runtime_ready: bool = False
    supports_device_auth: bool = False
    plan_type: str = ""
    codex_cli_available: bool = False
    codex_home: str = ""

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
            "auth_method": self.auth_method,
            "runtime_ready": self.runtime_ready,
            "supports_device_auth": self.supports_device_auth,
            "plan_type": self.plan_type,
            "codex_cli_available": self.codex_cli_available,
            "codex_home": self.codex_home,
        }


@dataclass(frozen=True)
class _CodexAuthSnapshot:
    auth_mode: str = ""
    api_key: str = ""
    plan_type: str = ""
    credential_source: str = "none"
    runtime_ready: bool = False
    cli_available: bool = False
    home: str = ""


class AgentCodexAuthStore:
    AUTH_FILE_NAME = "auth.json"
    CONFIG_FILE_NAME = "config.toml"
    FILE_STORAGE_LINE = 'cli_auth_credentials_store = "file"'

    def __init__(self, global_state_dir: str | Path | None = None) -> None:
        self._custom_global_state_dir = global_state_dir is not None or bool(os.environ.get("MOTORVIDEOJUEGOSIA_HOME", "").strip())
        self.global_state_dir = self._resolve_global_state_dir(global_state_dir)
        self.managed_home = self.global_state_dir / "codex"

    def cli_available(self) -> bool:
        return bool(shutil.which("codex") or shutil.which("codex.cmd") or shutil.which("codex.exe"))

    def ensure_managed_file_storage(self) -> Path:
        self.managed_home.mkdir(parents=True, exist_ok=True)
        config_path = self.managed_home / self.CONFIG_FILE_NAME
        if not config_path.exists():
            config_path.write_text(self.FILE_STORAGE_LINE + "\n", encoding="utf-8")
            return config_path
        content = config_path.read_text(encoding="utf-8")
        if self.FILE_STORAGE_LINE not in content:
            suffix = "" if not content or content.endswith("\n") else "\n"
            config_path.write_text(content + suffix + self.FILE_STORAGE_LINE + "\n", encoding="utf-8")
        return config_path

    def build_login_command(self, *, device_auth: bool = False, with_api_key: bool = False) -> dict[str, Any]:
        self.ensure_managed_file_storage()
        command = [self._resolve_cli_command(), "login"]
        if device_auth:
            command.append("--device-auth")
        if with_api_key:
            command.append("--with-api-key")
        return {
            "command": command,
            "codex_home": self.managed_home.as_posix(),
        }

    def run_login(self, *, device_auth: bool = False, with_api_key: bool = False, api_key: str = "") -> _CodexAuthSnapshot:
        self.ensure_managed_file_storage()
        command_info = self.build_login_command(device_auth=device_auth, with_api_key=with_api_key)
        kwargs: dict[str, Any] = {"env": self._env_for(self.managed_home)}
        if with_api_key:
            secret = str(api_key or "").strip()
            if not secret:
                raise ValueError("API key is required for Codex API key login.")
            kwargs["input"] = secret + "\n"
            kwargs["text"] = True
        completed = subprocess.run(command_info["command"], **kwargs)
        if completed.returncode != 0:
            raise RuntimeError(f"Codex login failed with exit code {completed.returncode}.")
        return self.load_snapshot()

    def run_logout(self, *, home: str | Path | None = None) -> None:
        target_home = self._resolve_home(home)
        completed = subprocess.run([self._resolve_cli_command(), "logout"], env=self._env_for(target_home))
        if completed.returncode != 0:
            raise RuntimeError(f"Codex logout failed with exit code {completed.returncode}.")

    def load_snapshot(self) -> _CodexAuthSnapshot:
        cli_available = self.cli_available()
        for home in self._candidate_homes():
            snapshot = self._load_snapshot_from_home(home, cli_available=cli_available)
            if snapshot.credential_source != "none":
                return snapshot
        return _CodexAuthSnapshot(cli_available=cli_available, home=self.managed_home.as_posix())

    def _candidate_homes(self) -> list[Path]:
        homes: list[Path] = []
        seen: set[str] = set()
        raw_items = [
            self.managed_home.as_posix(),
            os.environ.get("CODEX_HOME", "").strip(),
        ]
        if not self._custom_global_state_dir:
            raw_items.append((Path.home() / ".codex").as_posix())
        for raw in raw_items:
            if not raw:
                continue
            resolved = self._resolve_home(raw)
            key = resolved.as_posix().lower()
            if key in seen:
                continue
            seen.add(key)
            homes.append(resolved)
        return homes

    def _load_snapshot_from_home(self, home: Path, *, cli_available: bool) -> _CodexAuthSnapshot:
        auth_path = home / self.AUTH_FILE_NAME
        if auth_path.exists():
            try:
                payload = json.loads(auth_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
            if isinstance(payload, dict):
                auth_mode = str(payload.get("auth_mode", payload.get("authMode", "")) or "").strip().lower()
                api_key = str(payload.get("OPENAI_API_KEY", payload.get("openai_api_key", "")) or "").strip()
                plan_type = str(payload.get("plan_type", payload.get("planType", "")) or "").strip().lower()
                credential_source = "none"
                if auth_mode == "chatgpt":
                    credential_source = "codex_chatgpt"
                elif auth_mode == "apikey" or api_key:
                    credential_source = "codex_api_key"
                if credential_source != "none":
                    return _CodexAuthSnapshot(
                        auth_mode=auth_mode,
                        api_key=api_key,
                        plan_type=plan_type,
                        credential_source=credential_source,
                        runtime_ready=bool(api_key),
                        cli_available=cli_available,
                        home=home.as_posix(),
                    )
        if cli_available and self._has_keyring_auth(home):
            return _CodexAuthSnapshot(
                credential_source="codex_keyring",
                cli_available=True,
                home=home.as_posix(),
            )
        return _CodexAuthSnapshot(cli_available=cli_available, home=home.as_posix())

    def _has_keyring_auth(self, home: Path) -> bool:
        try:
            completed = subprocess.run(
                [self._resolve_cli_command(), "login", "status"],
                env=self._env_for(home),
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception:
            return False
        return completed.returncode == 0

    def _resolve_cli_command(self) -> str:
        command = shutil.which("codex") or shutil.which("codex.cmd") or shutil.which("codex.exe")
        if not command:
            raise RuntimeError("Codex CLI is not available. Install the official Codex CLI and ensure `codex` is on PATH.")
        return command

    def _env_for(self, home: Path) -> dict[str, str]:
        env = os.environ.copy()
        env["CODEX_HOME"] = home.as_posix()
        return env

    def _resolve_home(self, home: str | Path | None) -> Path:
        if home is None:
            return self.managed_home.expanduser().resolve()
        return Path(home).expanduser().resolve()

    def _resolve_global_state_dir(self, global_state_dir: str | Path | None) -> Path:
        if global_state_dir is not None:
            return Path(global_state_dir).expanduser().resolve()
        env_override = os.environ.get("MOTORVIDEOJUEGOSIA_HOME", "").strip()
        if env_override:
            return Path(env_override).expanduser().resolve()
        return (Path.home() / ".motorvideojuegosia").resolve()


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
        self.codex_auth_store = AgentCodexAuthStore(self.credential_store.global_state_dir)

    def login(
        self,
        provider_id: str,
        *,
        api_key: str,
        base_url: str = "",
        model: str = "",
        credential_source: str = "user_local",
        device_auth: bool = False,
    ) -> dict[str, Any]:
        provider_id = self._normalize_provider(provider_id)
        defaults = self.provider_defaults(provider_id)
        if credential_source == "user_local":
            self.credential_store.save_api_key(provider_id, api_key)
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
        if provider_id != "openai":
            raise ValueError(f"Managed Codex login is not supported for provider {provider_id}.")
        if credential_source not in {"codex_chatgpt", "codex_api_key"}:
            raise ValueError(f"Unsupported provider credential source: {credential_source}")
        self.codex_auth_store.run_login(
            device_auth=device_auth,
            with_api_key=credential_source == "codex_api_key",
            api_key=api_key,
        )
        status = self.status(provider_id)
        if status.runtime_ready:
            settings = self.settings_store.set_default_provider(
                provider_id,
                model=model or defaults["model"],
                base_url=base_url or defaults["base_url"],
                stream=True,
            )
            message = "Provider openai configured via Codex login."
        else:
            settings = self.settings_store.load()
            message = "Codex login completed, but no reusable OpenAI API key was detected for the current runtime bridge."
        return {
            "provider": status.to_dict(),
            "settings": settings,
            "message": message,
        }

    def logout(self, provider_id: str) -> dict[str, Any]:
        provider_id = self._normalize_provider(provider_id)
        current_status = self.status(provider_id)
        if str(current_status.credential_source).startswith("codex_"):
            self.codex_auth_store.run_logout(home=current_status.codex_home or None)
        else:
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

    def prepare_managed_login(self, provider_id: str, *, device_auth: bool = False) -> dict[str, Any]:
        provider_id = self._normalize_provider(provider_id)
        if provider_id != "openai":
            raise ValueError(f"Managed Codex login is not supported for provider {provider_id}.")
        command_info = self.codex_auth_store.build_login_command(device_auth=device_auth)
        return {
            "provider_id": provider_id,
            "command": command_info["command"],
            "codex_home": command_info["codex_home"],
            "device_auth": bool(device_auth),
        }

    def status(self, provider_id: str) -> AgentProviderLoginStatus:
        provider_id = self._normalize_provider(provider_id)
        defaults = self.provider_defaults(provider_id)
        env_key = self.env_key(provider_id)
        source = self.credential_store.credential_source(provider_id, env_key)
        auth_method = "api_key" if source in {"env", "user_local"} else ""
        runtime_ready = source in {"env", "user_local"}
        plan_type = ""
        codex_snapshot = _CodexAuthSnapshot()
        if provider_id == "openai":
            codex_snapshot = self.codex_auth_store.load_snapshot()
            if source == "none" and codex_snapshot.credential_source != "none":
                source = codex_snapshot.credential_source
                if codex_snapshot.credential_source == "codex_chatgpt":
                    auth_method = "chatgpt"
                elif codex_snapshot.credential_source == "codex_api_key":
                    auth_method = "api_key"
                else:
                    auth_method = ""
                runtime_ready = codex_snapshot.runtime_ready
                plan_type = codex_snapshot.plan_type
        auth_status = "configured" if source in {"env", "user_local", "codex_chatgpt", "codex_api_key", "codex_keyring"} else "missing"
        return AgentProviderLoginStatus(
            provider_id=provider_id,
            auth_status=auth_status,
            credential_source=source,
            login_supported=provider_id in {"opencode-go", "openai"},
            base_url=defaults["base_url"],
            model=defaults["model"],
            updated_at=utc_now_iso() if auth_status == "configured" else "",
            auth_method=auth_method,
            runtime_ready=runtime_ready,
            supports_device_auth=provider_id == "openai",
            plan_type=plan_type,
            codex_cli_available=codex_snapshot.cli_available if provider_id == "openai" else False,
            codex_home=codex_snapshot.home if provider_id == "openai" else "",
        )

    def api_key(self, provider_id: str) -> str:
        provider_id = self._normalize_provider(provider_id)
        env_key = self.env_key(provider_id)
        if env_key and os.environ.get(env_key, "").strip():
            return os.environ[env_key].strip()
        local_api_key = self.credential_store.load_api_key(provider_id)
        if local_api_key:
            return local_api_key
        if provider_id == "openai":
            return self.codex_auth_store.load_snapshot().api_key
        return ""

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
