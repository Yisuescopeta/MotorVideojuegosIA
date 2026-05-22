"""Build report generation."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.export.build_context import BuildContext

try:
    from engine.config import ENGINE_VERSION
except ImportError:
    ENGINE_VERSION = "0.0.0"

_SECRET_PATTERNS: list[tuple[str, str]] = [
    (r'(?:keystore|key)\s+at\s+\S+', r'keystore at [REDACTED]'),
    (r'keystore_path\s*["\':=]+\s*\S+', r'keystore_path="[REDACTED]"'),
    (r'keystore_password\s*["\':=]+\s*\S+', r'keystore_password="[REDACTED]"'),
    (r'key_alias\s*["\':=]+\s*\S+', r'key_alias="[REDACTED]"'),
    (r'key_password\s*["\':=]+\s*\S+', r'key_password="[REDACTED]"'),
    (r'(?:password|token|secret|api_key)\s*["\':=]+\s*\S+',
     r'[REDACTED]'),
    (r'(?:--password|--token|--api-key)\s+\S+', r'[REDACTED]'),
    (r'storeFile\s+\S+', r'storeFile [REDACTED]'),
    (r'ANDROID_KEYSTORE_NOT_FOUND.*', r'ANDROID_KEYSTORE_NOT_FOUND: [REDACTED]'),
]


def _sanitize(value: str) -> str:
    for pattern, replacement in _SECRET_PATTERNS:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    return value


def _sanitize_list(items: list[str]) -> list[str]:
    return [_sanitize(item) for item in items]


def _sanitize_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for art in artifacts:
        clean: dict[str, Any] = {}
        for k, v in art.items():
            if isinstance(v, str):
                clean[k] = _sanitize(v)
            else:
                clean[k] = v
        result.append(clean)
    return result


def _sanitize_env(env: dict[str, str]) -> dict[str, str]:
    return {k: _sanitize(v) for k, v in env.items()}


def generate_build_report(
    ctx: BuildContext,
    success: bool,
    duration_seconds: float,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": 1,
        "success": success,
        "preset": ctx.preset.name,
        "platform": ctx.preset.platform,
        "mode": ctx.preset.mode,
        "engine_version": ENGINE_VERSION,
        "project_name": ctx.preset.display_name or ctx.preset.name,
        "entry_scene": ctx.preset.entry_scene,
        "started_at_utc": ctx.started_at_utc.isoformat(),
        "finished_at_utc": now,
        "duration_seconds": round(duration_seconds, 2),
        "artifacts": _sanitize_artifacts(ctx.artifacts),
        "warnings": _sanitize_list(ctx.warnings),
        "errors": _sanitize_list(ctx.errors),
        "environment": _sanitize_env(_env_info()),
    }


def write_build_report(
    report: dict[str, Any],
    project_root: str | Path,
    preset_name: str,
) -> Path:
    root = Path(project_root)
    reports_dir = root / ".motor" / "build" / "export_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in preset_name)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{safe}_{ts}.json"
    path = reports_dir / filename
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return path


def _env_info() -> dict[str, str]:
    pyinstaller = shutil.which("pyinstaller") or ""
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "os": os.name,
        "pyinstaller": pyinstaller,
    }
