from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


class ExitCode(IntEnum):
    OK = 0
    FAILED = 1
    INVALID = 2


@dataclass(frozen=True)
class ToolCommandResult:
    command: tuple[str, ...]
    cwd: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": list(self.command),
            "command_text": format_command(self.command),
            "cwd": self.cwd,
            "returncode": self.returncode,
            "passed": self.passed,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def normalize_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def quote_token(token: str) -> str:
    if not token:
        return '""'
    if any(character.isspace() for character in token) or any(character in token for character in '"&|<>'):
        escaped = token.replace('"', '\\"')
        return f'"{escaped}"'
    return token


def format_command(command: Sequence[str]) -> str:
    return " ".join(quote_token(part) for part in command)


def make_response(success: bool, message: str, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "success": success,
        "message": message,
        "data": dict(data or {}),
    }


def print_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=True))


def run_command(
    command: Sequence[str],
    *,
    cwd: str | Path,
    env: Mapping[str, str] | None = None,
) -> ToolCommandResult:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        list(command),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=merged_env,
    )
    return ToolCommandResult(
        command=tuple(str(part) for part in command),
        cwd=normalize_path(cwd).as_posix(),
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def run_git(args: Sequence[str], *, cwd: str | Path) -> ToolCommandResult:
    return run_command(["git", *args], cwd=cwd)


def resolve_git_root(start: str | Path) -> Path | None:
    candidate = normalize_path(start)
    result = run_git(["rev-parse", "--show-toplevel"], cwd=candidate)
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    if not output:
        return None
    return normalize_path(output)


def current_branch(repo_root: str | Path) -> str | None:
    result = run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=repo_root)
    branch = result.stdout.strip()
    if result.returncode != 0 or not branch:
        return None
    return branch


def head_sha(repo_root: str | Path) -> str | None:
    result = run_git(["rev-parse", "--short", "HEAD"], cwd=repo_root)
    sha = result.stdout.strip()
    if result.returncode != 0 or not sha:
        return None
    return sha


def is_dirty(repo_root: str | Path) -> bool:
    result = run_git(["status", "--short"], cwd=repo_root)
    return result.returncode == 0 and bool(result.stdout.strip())


def branch_exists(repo_root: str | Path, branch_name: str) -> bool:
    result = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"], cwd=repo_root)
    return result.returncode == 0


def slugify_branch_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return normalized or "worktree"


def parse_worktree_porcelain(output: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] = {}

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                entries.append(_finalize_worktree_entry(current))
                current = {}
            continue

        key, _, value = raw_line.partition(" ")
        if key == "worktree":
            current["path"] = normalize_path(value).as_posix()
        elif key == "branch":
            branch_name = value.removeprefix("refs/heads/")
            current["branch"] = branch_name
        elif key == "HEAD":
            current["head"] = value
        elif key in {"detached", "bare"}:
            current[key] = True
        elif key in {"locked", "prunable"}:
            current[key] = value or True
        else:
            current[key] = value or True

    if current:
        entries.append(_finalize_worktree_entry(current))

    return entries


def _finalize_worktree_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(entry)
    normalized["detached"] = bool(normalized.get("detached", False))
    normalized["bare"] = bool(normalized.get("bare", False))
    normalized.setdefault("branch", None)
    normalized.setdefault("head", None)
    return normalized
