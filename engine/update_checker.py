"""
engine/update_checker.py - Comprobación mínima de actualizaciones

PROPÓSITO:
    Consulta GitHub Releases en segundo plano para detectar versiones nuevas.
    Tolerante a errores de red: si falla, el motor sigue funcionando normalmente.

USO:
    from engine.update_checker import start_update_check, get_update_info

    start_update_check()          # llamar una vez al arranque
    info = get_update_info()      # consultar desde el draw loop
    if info and info.available:
        webbrowser.open(info.download_url)
"""

import json
import threading
import urllib.request
from dataclasses import dataclass
from typing import Optional

from engine.config import ENGINE_VERSION

GITHUB_RELEASES_URL = "https://api.github.com/repos/Yisuescopeta/MotorVideojuegosIA/releases/latest"
REQUEST_TIMEOUT = 5  # segundos


@dataclass(frozen=True)
class UpdateInfo:
    available: bool
    current: str
    latest: str
    download_url: str


_result: Optional[UpdateInfo] = None
_lock = threading.Lock()


def _normalize_version(tag: str) -> str:
    """Elimina prefijo 'v' para comparar versiones."""
    return tag.lstrip("vV").strip()


def _check() -> None:
    global _result
    try:
        req = urllib.request.Request(
            GITHUB_RELEASES_URL,
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "MotorVideojuegosIA-UpdateCheck"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:  # nosec B310 — URL is always HTTPS to GitHub API
            data = json.loads(resp.read().decode("utf-8"))

        tag = _normalize_version(data.get("tag_name", ""))
        current = _normalize_version(ENGINE_VERSION)

        # Buscar el asset .exe del instalador, o fallback a la página de release
        download_url = data.get("html_url", "")
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".exe") and "Setup" in name:
                download_url = asset.get("browser_download_url", download_url)
                break

        available = tag != "" and tag != current

        with _lock:
            _result = UpdateInfo(
                available=available,
                current=current,
                latest=tag,
                download_url=download_url,
            )
    except Exception:
        # Cualquier error (sin red, DNS, timeout, JSON inválido, etc.) se silencia.
        pass


def start_update_check() -> None:
    """Lanza la comprobación en un daemon thread (no bloquea el arranque)."""
    t = threading.Thread(target=_check, daemon=True)
    t.start()


def get_update_info() -> Optional[UpdateInfo]:
    """Devuelve el resultado de la comprobación, o None si aún no terminó."""
    with _lock:
        return _result
