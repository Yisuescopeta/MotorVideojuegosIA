from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_session_slug(session_id: str) -> str:
    text = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in str(session_id or "").strip())
    return text.strip("_") or "session"


def ensure_opencode_artifact_dir(session_id: str, out_dir: str | Path = "", project_root: str | Path = ".") -> Path:
    root = Path(project_root).resolve()
    if out_dir:
        target = Path(out_dir)
        if not target.is_absolute():
            target = (root / target).resolve()
    else:
        target = root / "artifacts" / "opencode" / f"{_utc_timestamp_slug()}_{_safe_session_slug(session_id)}"
    target.mkdir(parents=True, exist_ok=True)
    return target.resolve()


def write_json_artifact(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return path
