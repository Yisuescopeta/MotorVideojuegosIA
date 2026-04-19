from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.agent.command_policy import AgentCommandDecision


@dataclass(frozen=True)
class AgentCommandRunResult:
    success: bool
    output: str = ""
    error: str = ""
    returncode: int | None = None
    duration_ms: int = 0
    audit: dict[str, Any] = field(default_factory=dict)


class AgentCommandRunner:
    """Process runner for allowlisted agent commands.

    It is a constrained process boundary, not a full OS/container sandbox.
    """

    OUTPUT_LIMIT = 20000
    ERROR_LIMIT = 2000
    ALLOWED_ENV_KEYS = (
        "PATH",
        "PATHEXT",
        "SystemRoot",
        "WINDIR",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
        "PROGRAMDATA",
    )

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.audit_path = self.project_root / ".motor" / "agent_state" / "command_audit.jsonl"

    def run(self, decision: AgentCommandDecision) -> AgentCommandRunResult:
        if not decision.allowed:
            audit = self._audit_payload(decision, returncode=None, duration_ms=0, blocked=True)
            self._append_audit(audit)
            return AgentCommandRunResult(False, error=decision.reason, audit=audit)
        cwd = Path(decision.cwd or self.project_root.as_posix()).expanduser().resolve()
        try:
            cwd.relative_to(self.project_root)
        except ValueError:
            audit = self._audit_payload(decision, returncode=None, duration_ms=0, blocked=True)
            self._append_audit(audit)
            return AgentCommandRunResult(False, error="Command cwd is outside project root.", audit=audit)

        start = time.monotonic()
        try:
            completed = subprocess.run(
                list(decision.argv),
                cwd=cwd,
                shell=False,
                env=self._safe_env(),
                capture_output=True,
                text=True,
                timeout=decision.timeout_seconds,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            output = ((completed.stdout or "") + (completed.stderr or ""))[-self.OUTPUT_LIMIT :]
            audit = self._audit_payload(decision, returncode=completed.returncode, duration_ms=duration_ms, blocked=False)
            self._append_audit(audit)
            return AgentCommandRunResult(
                completed.returncode == 0,
                output=output,
                error="" if completed.returncode == 0 else output[-self.ERROR_LIMIT :],
                returncode=completed.returncode,
                duration_ms=duration_ms,
                audit=audit,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            audit = self._audit_payload(decision, returncode=None, duration_ms=duration_ms, blocked=False)
            self._append_audit(audit)
            return AgentCommandRunResult(False, error=str(exc), duration_ms=duration_ms, audit=audit)

    def _safe_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        for key in self.ALLOWED_ENV_KEYS:
            value = os.environ.get(key)
            if value:
                env[key] = value
        return env

    def _audit_payload(
        self,
        decision: AgentCommandDecision,
        *,
        returncode: int | None,
        duration_ms: int,
        blocked: bool,
    ) -> dict[str, Any]:
        return {
            "argv": list(decision.argv),
            "cwd": decision.cwd,
            "profile": decision.profile.value if decision.profile is not None else "",
            "timeout_seconds": decision.timeout_seconds,
            "returncode": returncode,
            "duration_ms": duration_ms,
            "blocked": blocked,
            "env_keys": [key for key in self.ALLOWED_ENV_KEYS if os.environ.get(key)],
            "reason": decision.reason,
        }

    def _append_audit(self, payload: dict[str, Any]) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
