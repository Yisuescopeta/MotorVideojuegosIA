from __future__ import annotations

import re
from pathlib import Path


AGENT_SESSION_ID_PATTERN = re.compile(r"^agent-session-[a-f0-9]{12}$")


def validate_agent_session_id(session_id: str) -> str:
    value = str(session_id or "").strip()
    if not AGENT_SESSION_ID_PATTERN.fullmatch(value):
        raise ValueError(f"Invalid agent session id: {value}")
    return value


def resolve_agent_session_path(base_dir: str | Path, session_id: str, suffix: str) -> Path:
    base = Path(base_dir).expanduser().resolve()
    valid_id = validate_agent_session_id(session_id)
    path = (base / f"{valid_id}{suffix}").resolve()
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Invalid agent session id: {valid_id}") from exc
    return path
