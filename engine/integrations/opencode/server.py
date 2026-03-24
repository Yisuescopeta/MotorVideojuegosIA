from __future__ import annotations

import base64
import json
import os
import platform
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
from urllib import error, request


class OpenCodeServerError(RuntimeError):
    """Base error for OpenCode server lifecycle failures."""


class OpenCodeUnavailableError(OpenCodeServerError):
    """Raised when the opencode executable is not available."""


class OpenCodeConfigError(OpenCodeServerError):
    """Raised when the local OpenCode config is invalid."""


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass(frozen=True)
class OpenCodeServerConfig:
    port: int = 4096
    hostname: str = "127.0.0.1"
    password: str = ""
    startup_timeout_seconds: float = 10.0
    health_timeout_seconds: float = 2.0
    shutdown_timeout_seconds: float = 5.0

    @classmethod
    def default_path(cls, project_root: str | os.PathLike[str]) -> Path:
        return Path(project_root).resolve() / ".motor" / "opencode" / "config.json"

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "OpenCodeServerConfig":
        if not isinstance(payload, dict):
            raise OpenCodeConfigError("OpenCode config must be a JSON object")
        try:
            port = int(payload.get("port", cls.port))
        except (TypeError, ValueError) as exc:
            raise OpenCodeConfigError("OpenCode config field 'port' must be an integer") from exc
        hostname = str(payload.get("hostname", cls.hostname)).strip() or cls.hostname
        password = str(payload.get("password", cls.password))
        try:
            startup_timeout = float(payload.get("startup_timeout_seconds", cls.startup_timeout_seconds))
            health_timeout = float(payload.get("health_timeout_seconds", cls.health_timeout_seconds))
            shutdown_timeout = float(payload.get("shutdown_timeout_seconds", cls.shutdown_timeout_seconds))
        except (TypeError, ValueError) as exc:
            raise OpenCodeConfigError("OpenCode timeout fields must be numeric") from exc
        if port <= 0 or port > 65535:
            raise OpenCodeConfigError("OpenCode config field 'port' must be between 1 and 65535")
        return cls(
            port=port,
            hostname=hostname,
            password=password,
            startup_timeout_seconds=max(startup_timeout, 0.1),
            health_timeout_seconds=max(health_timeout, 0.1),
            shutdown_timeout_seconds=max(shutdown_timeout, 0.1),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "port": self.port,
            "hostname": self.hostname,
            "password": self.password,
            "startup_timeout_seconds": self.startup_timeout_seconds,
            "health_timeout_seconds": self.health_timeout_seconds,
            "shutdown_timeout_seconds": self.shutdown_timeout_seconds,
        }

    @classmethod
    def load(cls, project_root: str | os.PathLike[str], path: str | os.PathLike[str] | None = None) -> "OpenCodeServerConfig":
        config_path = Path(path).resolve() if path is not None else cls.default_path(project_root)
        if not config_path.exists():
            config = cls()
            config.save(project_root, config_path)
            return config
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            raise OpenCodeConfigError(f"Invalid JSON in OpenCode config: {config_path.as_posix()}") from exc
        except OSError as exc:
            raise OpenCodeConfigError(f"Unable to read OpenCode config: {config_path.as_posix()}") from exc
        return cls.from_dict(payload)

    def save(self, project_root: str | os.PathLike[str], path: str | os.PathLike[str] | None = None) -> Path:
        config_path = Path(path).resolve() if path is not None else self.default_path(project_root)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=4)
        return config_path


class OpenCodeServerProcess:
    """Manage an opencode HTTP server process for the current project."""

    def __init__(
        self,
        project_root: str | os.PathLike[str] = ".",
        config_path: str | os.PathLike[str] | None = None,
        executable: str = "opencode",
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.config_path = Path(config_path).resolve() if config_path is not None else OpenCodeServerConfig.default_path(self.project_root)
        self.executable = executable
        self._config = OpenCodeServerConfig.load(self.project_root, self.config_path)
        self._process: subprocess.Popen[str] | None = None
        self._state_path = self.config_path.parent / "server_state.json"

    @property
    def config(self) -> OpenCodeServerConfig:
        return self._config

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def base_url(self) -> str:
        return f"http://{self._config.hostname}:{self._config.port}"

    def reload_config(self) -> OpenCodeServerConfig:
        self._config = OpenCodeServerConfig.load(self.project_root, self.config_path)
        return self._config

    def launch_visible_client(self, attach_url: str | None = None) -> Dict[str, Any]:
        executable_path = self._resolve_executable_path()
        self.reload_config()
        env = self._build_env()
        target_command = self._build_visible_client_command(executable_path, attach_url=attach_url)
        launch_command = self._build_visible_launch_command(target_command)
        try:
            subprocess.Popen(
                launch_command,
                cwd=self.project_root.as_posix(),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
            )
        except OSError as exc:
            raise OpenCodeServerError(f"Unable to open OpenCode client: {exc}") from exc
        return {
            "launched": True,
            "attach_url": str(attach_url or ""),
            "base_url": self.base_url,
            "target_command": self._format_command(target_command),
            "launch_command": self._format_command(launch_command),
            "project_root": self.project_root.as_posix(),
            "platform": platform.system(),
        }

    def start(self) -> Dict[str, Any]:
        if self.is_running:
            health = self.health()
            return {
                "started": True,
                "already_running": True,
                "pid": int(self._process.pid) if self._process is not None else 0,
                "base_url": self.base_url,
                "health": health,
            }

        try:
            health = self.health()
            persisted = self._load_state()
            return {
                "started": True,
                "already_running": True,
                "pid": int(persisted.get("pid", 0) or 0),
                "base_url": self.base_url,
                "health": health,
            }
        except OpenCodeServerError:
            pass

        executable_path = self._resolve_executable_path()

        self.reload_config()
        env = self._build_env()

        command = [
            executable_path,
            "serve",
            "--port",
            str(self._config.port),
            "--hostname",
            self._config.hostname,
        ]
        try:
            self._process = subprocess.Popen(
                command,
                cwd=self.project_root.as_posix(),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            raise OpenCodeServerError(f"Unable to start opencode server: {exc}") from exc

        deadline = time.time() + self._config.startup_timeout_seconds
        last_error = "OpenCode server did not become healthy in time."
        while time.time() < deadline:
            if self._process.poll() is not None:
                stderr = ""
                if self._process.stderr is not None:
                    try:
                        stderr = self._process.stderr.read().strip()
                    except Exception:
                        stderr = ""
                self._close_process_streams(self._process)
                self._process = None
                message = stderr or "Process exited before health check succeeded."
                raise OpenCodeServerError(f"OpenCode server failed to start. {message}")
            try:
                health = self.health()
                self._write_state(int(self._process.pid) if self._process is not None else 0)
                return {
                    "started": True,
                    "already_running": False,
                    "pid": int(self._process.pid) if self._process is not None else 0,
                    "base_url": self.base_url,
                    "health": health,
                }
            except OpenCodeServerError as exc:
                last_error = str(exc)
                time.sleep(0.2)

        self.stop()
        raise OpenCodeServerError(f"OpenCode server start timed out. {last_error}")

    def stop(self) -> Dict[str, Any]:
        persisted = self._load_state()
        if self._process is None:
            persisted_pid = int(persisted.get("pid", 0) or 0)
            if persisted_pid > 0:
                self._kill_process_tree(persisted_pid)
                self._clear_state()
                return {"stopped": True, "was_running": True, "returncode": None}
            return {"stopped": True, "was_running": False}

        process = self._process
        self._process = None
        pid = int(process.pid)
        if process.poll() is not None:
            self._kill_process_tree(pid)
            self._close_process_streams(process)
            self._clear_state()
            return {"stopped": True, "was_running": False, "returncode": process.returncode}

        process.terminate()
        try:
            process.wait(timeout=self._config.shutdown_timeout_seconds)
        except subprocess.TimeoutExpired:
            self._kill_process_tree(pid)
            try:
                process.wait(timeout=max(self._config.shutdown_timeout_seconds, 1.0))
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=max(self._config.shutdown_timeout_seconds, 1.0))
        finally:
            self._kill_process_tree(pid)
            self._close_process_streams(process)
            self._clear_state()

        return {
            "stopped": True,
            "was_running": True,
            "returncode": process.returncode,
        }

    def health(self) -> Dict[str, Any]:
        response = self._request_json("/global/health", timeout=self._config.health_timeout_seconds)
        healthy = bool(response.get("healthy", False))
        version = str(response.get("version", "") or "")
        return {
            "healthy": healthy,
            "version": version,
            "base_url": self.base_url,
        }

    def _resolve_executable_path(self) -> str:
        executable_path = shutil.which(self.executable)
        if not executable_path:
            raise OpenCodeUnavailableError(self._build_missing_executable_message())
        return executable_path

    def _build_env(self) -> Dict[str, str]:
        env = dict(os.environ)
        if self._config.password:
            env["OPENCODE_SERVER_PASSWORD"] = self._config.password
        return env

    def _build_visible_client_command(self, executable_path: str, attach_url: str | None = None) -> list[str]:
        if attach_url:
            return [
                executable_path,
                "attach",
                str(attach_url),
            ]
        return [
            executable_path,
            str(self.project_root),
            "--hostname",
            self._config.hostname,
            "--port",
            str(self._config.port),
        ]

    def _build_visible_launch_command(self, target_command: list[str]) -> list[str]:
        if os.name == "nt":
            return [
                "cmd.exe",
                "/c",
                "start",
                "",
                "/D",
                str(self.project_root),
                "cmd.exe",
                "/k",
                self._format_command(target_command),
            ]
        return list(target_command)

    def _format_command(self, command: list[str]) -> str:
        return subprocess.list2cmdline(command)

    def _request_json(self, path: str, timeout: float) -> Dict[str, Any]:
        req = request.Request(f"{self.base_url}{path}")
        if self._config.password:
            token = base64.b64encode(f"opencode:{self._config.password}".encode("utf-8")).decode("ascii")
            req.add_header("Authorization", f"Basic {token}")
        try:
            with request.urlopen(req, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise OpenCodeServerError(f"OpenCode health request failed with HTTP {exc.code}") from exc
        except error.URLError as exc:
            raise OpenCodeServerError(f"OpenCode health request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise OpenCodeServerError("OpenCode health request returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise OpenCodeServerError("OpenCode health request returned a non-object payload")
        return payload

    def _build_missing_executable_message(self) -> str:
        return (
            "OpenCode is not installed or is not on PATH. "
            "Install OpenCode and ensure the 'opencode' command is available, "
            "then retry. Example: run the OpenCode installer or verify with "
            "'opencode --help'. The motor itself can continue running without this integration."
        )

    def _close_process_streams(self, process: subprocess.Popen[str]) -> None:
        for stream_name in ("stdin", "stdout", "stderr"):
            stream = getattr(process, stream_name, None)
            if stream is None:
                continue
            try:
                stream.close()
            except Exception:
                pass

    def _load_state(self) -> Dict[str, Any]:
        if not self._state_path.exists():
            return {}
        try:
            with self._state_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_state(self, pid: int) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with self._state_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "pid": pid,
                    "hostname": self._config.hostname,
                    "port": self._config.port,
                    "base_url": self.base_url,
                },
                handle,
                indent=4,
            )

    def _clear_state(self) -> None:
        try:
            if self._state_path.exists():
                self._state_path.unlink()
        except Exception:
            pass

    def _kill_process_tree(self, pid: int) -> None:
        if pid <= 0:
            return
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass

    @classmethod
    def default_config(cls, project_root: str | os.PathLike[str]) -> Path:
        config = OpenCodeServerConfig(
            port=_find_free_port(),
            startup_timeout_seconds=10.0,
            health_timeout_seconds=2.0,
            shutdown_timeout_seconds=5.0,
        )
        return config.save(project_root)
