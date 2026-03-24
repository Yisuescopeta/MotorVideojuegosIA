from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any, Dict

from engine.integrations.opencode.client import OpenCodeClient, OpenCodeClientError, OpenCodeHTTPError
from engine.integrations.opencode.server import (
    OpenCodeServerError,
    OpenCodeServerProcess,
    OpenCodeUnavailableError,
)


@dataclass
class OpenCodeConnectionStatus:
    state: str = "disconnected"
    healthy: bool = False
    summary: str = "No conectado"
    technical_detail: str = ""
    action_hint: str = "Pulsa Connect o Start."
    base_url: str = ""
    version: str = ""
    pid: int = 0
    owned_by_editor: bool = False
    command: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "healthy": self.healthy,
            "summary": self.summary,
            "technical_detail": self.technical_detail,
            "action_hint": self.action_hint,
            "base_url": self.base_url,
            "version": self.version,
            "pid": self.pid,
            "owned_by_editor": self.owned_by_editor,
            "command": self.command,
        }


class OpenCodeBackendManager:
    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self._server = OpenCodeServerProcess(project_root=self.project_root)
        self._owned_by_editor: bool = False
        self._last_error: str = ""
        self._last_status: OpenCodeConnectionStatus = OpenCodeConnectionStatus(
            base_url=self._server.base_url,
        )

    @property
    def base_url(self) -> str:
        return self._server.base_url

    def create_client(self) -> OpenCodeClient:
        return OpenCodeClient(project_root=self.project_root, base_url=self.base_url)

    def get_last_error(self) -> str:
        return self._last_error

    def get_health(self) -> Dict[str, Any]:
        return self._server.health()

    def get_connection_status(self) -> Dict[str, Any]:
        return self._last_status.to_dict()

    def connect(self) -> Dict[str, Any]:
        self._server.reload_config()
        try:
            health = self._server.health()
            status = OpenCodeConnectionStatus(
                state="connected" if bool(health.get("healthy")) else "unreachable",
                healthy=bool(health.get("healthy", False)),
                summary="Conectado a OpenCode" if bool(health.get("healthy", False)) else "Servidor OpenCode no disponible",
                technical_detail="" if bool(health.get("healthy", False)) else "OpenCode health check returned unhealthy status.",
                action_hint="" if bool(health.get("healthy", False)) else "Revisa si OpenCode ya esta abierto y vuelve a intentar.",
                base_url=str(health.get("base_url", self.base_url) or self.base_url),
                version=str(health.get("version", "") or ""),
                pid=int(self._server._load_state().get("pid", 0) or 0),
                owned_by_editor=self._owned_by_editor,
                command=self._last_status.command,
            )
            self._last_error = ""
            self._last_status = status
            return status.to_dict()
        except OpenCodeHTTPError as exc:
            return self._set_error_status("auth_error", "Error de autenticacion con OpenCode", str(exc), "Revisa la password configurada y vuelve a intentar.")
        except OpenCodeClientError as exc:
            return self._set_error_status("unreachable", f"No se pudo conectar con OpenCode en {self.base_url}", str(exc), "Comprueba si OpenCode ya esta abierto o pulsa Start.")
        except OpenCodeUnavailableError as exc:
            return self._set_error_status("unavailable", "OpenCode no esta instalado", str(exc), "Instala OpenCode o verifica que el comando 'opencode' este en PATH.")
        except OpenCodeServerError as exc:
            detail = str(exc)
            if "HTTP 401" in detail or "HTTP 403" in detail:
                return self._set_error_status("auth_error", "Error de autenticacion con OpenCode", detail, "Revisa la password configurada y vuelve a intentar.")
            return self._set_error_status("unreachable", f"No se pudo conectar con OpenCode en {self.base_url}", detail, "Comprueba si OpenCode ya esta abierto o pulsa Start.")
        except Exception as exc:
            return self._set_error_status("error", "La conexion con OpenCode fallo", str(exc), "Revisa el detalle tecnico y vuelve a intentar.")

    def start_server(self) -> Dict[str, Any]:
        self._last_status = OpenCodeConnectionStatus(
            state="starting",
            healthy=False,
            summary="Iniciando backend OpenCode",
            technical_detail="Ejecutando 'opencode serve'.",
            action_hint="Espera a que el backend responda al health-check.",
            base_url=self.base_url,
            owned_by_editor=True,
        )
        try:
            result = self._server.start()
            self._owned_by_editor = not bool(result.get("already_running", False))
            status = self.connect()
            status["pid"] = int(result.get("pid", 0) or status.get("pid", 0) or 0)
            status["owned_by_editor"] = self._owned_by_editor
            self._last_status = OpenCodeConnectionStatus(**status)
            return self._last_status.to_dict()
        except OpenCodeUnavailableError as exc:
            return self._set_error_status("unavailable", "OpenCode no esta instalado", str(exc), "Instala OpenCode o verifica que el comando 'opencode' este en PATH.")
        except OpenCodeServerError as exc:
            detail = str(exc)
            summary = "No se pudo iniciar OpenCode"
            hint = "Revisa si el puerto esta libre y que 'opencode serve' funcione en terminal."
            if "timed out" in detail.lower():
                summary = "OpenCode no respondio a tiempo"
                hint = "Pulsa Reconnect o revisa el backend en terminal."
            return self._set_error_status("crashed", summary, detail, hint)
        except OSError as exc:
            return self._set_error_status("crashed", "No se pudo iniciar OpenCode", str(exc), "Revisa PATH, quoting del comando y permisos del proceso.")

    def start_visible(self) -> Dict[str, Any]:
        initial = self.connect()
        attach_url = self.base_url if initial.get("healthy") else None
        try:
            launch = self._server.launch_visible_client(attach_url=attach_url)
        except OpenCodeUnavailableError as exc:
            return self._set_error_status("unavailable", "OpenCode no esta instalado", str(exc), "Instala OpenCode o verifica que el comando 'opencode' este en PATH.")
        except OpenCodeServerError as exc:
            return self._set_error_status("crashed", "No se pudo abrir OpenCode", str(exc), "Revisa el comando, PATH y permisos del proceso.")
        self._last_status = OpenCodeConnectionStatus(
            state="starting",
            healthy=False,
            summary="Abriendo OpenCode",
            technical_detail=str(launch.get("target_command", "") or ""),
            action_hint="Espera a que OpenCode exponga el backend y luego el panel se conectara.",
            base_url=self.base_url,
            owned_by_editor=False,
            command=str(launch.get("launch_command", "") or ""),
        )
        return self._wait_for_connection_after_launch(launch, attach_url=attach_url)

    def ensure_server(self) -> Dict[str, Any]:
        status = self.connect()
        if status.get("healthy"):
            return status
        return self.start_server()

    def stop_server(self) -> Dict[str, Any]:
        result = self._server.stop()
        self._owned_by_editor = False
        self._last_status = OpenCodeConnectionStatus(
            state="disconnected",
            healthy=False,
            summary="Backend detenido",
            technical_detail="",
            action_hint="Pulsa Start o Connect.",
            base_url=self.base_url,
        )
        return {
            "stopped": bool(result.get("stopped", False)),
            "was_running": bool(result.get("was_running", False)),
            "returncode": result.get("returncode"),
            "connection_status": self._last_status.to_dict(),
        }

    def _wait_for_connection_after_launch(self, launch: Dict[str, Any], attach_url: str | None = None) -> Dict[str, Any]:
        timeout_seconds = max(self._server.config.startup_timeout_seconds, 20.0)
        deadline = time.time() + timeout_seconds
        last_status = self.get_connection_status()
        while time.time() < deadline:
            status = self.connect()
            status["command"] = str(launch.get("launch_command", "") or "")
            if status.get("healthy"):
                status["summary"] = "OpenCode abierto y conectado" if not attach_url else "OpenCode abierto y adjuntado"
                status["technical_detail"] = str(launch.get("target_command", "") or "")
                status["action_hint"] = "Ya puedes crear o reanudar una sesion desde el panel."
                self._last_error = ""
                self._last_status = OpenCodeConnectionStatus(**status)
                return self._last_status.to_dict()
            last_status = status
            time.sleep(0.25)
        detail = (
            f"No se pudo detectar el backend en {self.base_url} tras abrir OpenCode. "
            f"Comando intentado: {launch.get('launch_command', '')}"
        )
        return self._set_error_status(
            "unreachable",
            f"No se pudo conectar con OpenCode en {self.base_url}",
            detail,
            "Comprueba si OpenCode se abrio correctamente o pulsa Connect si ya habia un backend activo.",
            command=str(launch.get("launch_command", "") or last_status.get("command", "") or ""),
        )

    def _set_error_status(self, state: str, summary: str, technical_detail: str, action_hint: str, *, command: str = "") -> Dict[str, Any]:
        self._last_error = str(technical_detail or "")
        self._last_status = OpenCodeConnectionStatus(
            state=state,
            healthy=False,
            summary=summary,
            technical_detail=self._last_error,
            action_hint=action_hint,
            base_url=self.base_url,
            pid=int(self._server._load_state().get("pid", 0) or 0),
            owned_by_editor=self._owned_by_editor,
            command=command or self._last_status.command,
        )
        return self._last_status.to_dict()
