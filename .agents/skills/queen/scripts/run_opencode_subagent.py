#!/usr/bin/env python3
"""Run a Queen subagent through the OpenCode fallback dispatcher.

The fallback is for Codex/root runtimes only when a native child tool is absent
or the requested agent type is unknown to that native tool. It must not hide a
native child that already started and then timed out, failed permissions,
returned invalid output, or exited with an error.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
QUEEN_DIR = SCRIPT_DIR.parent
MAPPING_PATH = QUEEN_DIR / "references" / "agent_mapping.json"

sys.path.insert(0, str(SCRIPT_DIR))
from validate_result import ContractError, parse_result_text, validate_result  # noqa: E402

EXIT_CONFIG = 2
EXIT_TIMEOUT = 3
EXIT_PROCESS = 4
EXIT_RESULT = 5
EXIT_CONTRACT = 6

NATIVE_MASKING_FAILURES = {
    "native_timeout",
    "native_permission_denied",
    "native_invalid_output",
    "native_process_failed",
}


class DispatchError(RuntimeError):
    """Raised when OpenCode output does not satisfy the dispatcher contract."""


class ProcessOutputError(DispatchError):
    """Raised when OpenCode did not produce a usable child task event."""


def compact_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_agent_mapping(path: Path = MAPPING_PATH) -> dict[str, dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    agents = data.get("agents")
    if not isinstance(agents, dict) or not agents:
        raise DispatchError("agent_mapping.json has no agents")
    return agents


def normalize_role(role: str) -> str:
    return role.strip().replace("-", "_")


def opencode_role_for(role: str, mapping: dict[str, dict[str, str]]) -> str:
    normalized = normalize_role(role)
    entry = mapping.get(normalized)
    if not entry or not isinstance(entry.get("opencode"), str):
        known = ", ".join(sorted(mapping))
        raise DispatchError(f"unknown role {role!r}; expected one of: {known}")
    return entry["opencode"]


def should_use_fallback(native_state: str, agent_type_known: bool = True) -> bool:
    """Return whether Codex/OpenCode fallback may be selected.

    Native execution is always preferred. Fallback is allowed only before a
    native child exists: the native tool is absent or the native router does not
    know the requested agent type. Failures after a native child exists are not
    masked by fallback.
    """
    if native_state in NATIVE_MASKING_FAILURES:
        return False
    if native_state == "unknown_agent_type" or not agent_type_known:
        return True
    return native_state == "missing_native_tool"


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file is not None:
        return args.prompt_file.read_text(encoding="utf-8")
    return args.prompt or ""


def build_dispatch_prompt(role: str, opencode_role: str, prompt: str) -> str:
    return (
        "Queen Codex/OpenCode fallback dispatch.\n"
        f"Requested Codex role: {normalize_role(role)}\n"
        f"Mapped OpenCode subagent_type: {opencode_role}\n"
        "Invoke exactly one task with that subagent_type and return the child "
        "task_result verbatim. No retries.\n\n"
        "Child prompt:\n"
        f"{prompt}"
    )


def resolve_opencode_executable() -> str:
    executable = shutil.which("opencode")
    if executable is None:
        raise DispatchError("opencode executable not found on PATH")
    return executable


def build_command(repo_root: Path, executable: str | None = None) -> list[str]:
    return [
        executable or resolve_opencode_executable(),
        "run",
        "--agent",
        "queen-codex-dispatch",
        "--format",
        "json",
        "--dir",
        str(repo_root),
    ]


def iter_json_events(stdout: str) -> list[Any]:
    text = stdout.strip()
    if not text:
        raise ProcessOutputError("missing OpenCode JSON output")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        events = []
        for line in stdout.splitlines():
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ProcessOutputError(f"invalid OpenCode JSON event: {exc.msg}") from exc
        return events
    if isinstance(parsed, list):
        return parsed
    return [parsed]


def nested_get(data: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        current: Any = data
        for key in path:
            if not isinstance(current, dict) or key not in current:
                current = None
                break
            current = current[key]
        if current is not None:
            return current
    return None


def event_tool_name(event: dict[str, Any]) -> str | None:
    value = nested_get(event, ("part", "tool"), ("tool",), ("name",), ("tool_name",), ("call", "tool"), ("message", "tool"))
    return value if isinstance(value, str) else None


def event_status(event: dict[str, Any]) -> str | None:
    value = nested_get(event, ("part", "state", "status"), ("status",), ("state",), ("tool", "status"), ("call", "status"), ("output", "status"))
    return value if isinstance(value, str) else None


def event_subagent_type(event: dict[str, Any]) -> str | None:
    value = nested_get(
        event,
        ("subagent_type",),
        ("part", "state", "input", "subagent_type"),
        ("input", "subagent_type"),
        ("args", "subagent_type"),
        ("tool", "input", "subagent_type"),
        ("output", "subagent_type"),
        ("result", "subagent_type"),
    )
    return value if isinstance(value, str) else None


def event_task_result(event: dict[str, Any]) -> str | None:
    part_output = nested_get(event, ("part", "state", "output"))
    if isinstance(part_output, str):
        match = re.search(r"<task_result\b[^>]*>(?P<result>[\s\S]*?)</task_result>", part_output)
        if match:
            return match.group("result").strip()
    elif isinstance(part_output, dict):
        value = part_output.get("task_result")
        if isinstance(value, str):
            return value
    value = nested_get(
        event,
        ("task_result",),
        ("output", "task_result"),
        ("result", "task_result"),
        ("tool", "output", "task_result"),
    )
    return value if isinstance(value, str) else None


def event_metadata(event: dict[str, Any]) -> dict[str, Any]:
    state_metadata = nested_get(event, ("part", "state", "metadata"))
    state_metadata = state_metadata if isinstance(state_metadata, dict) else {}
    model = state_metadata.get("model") or nested_get(
        event,
        ("model",),
        ("metadata", "model"),
        ("response", "model"),
    )
    if isinstance(model, dict):
        provider = model.get("providerID")
        model_id = model.get("modelID")
        if isinstance(provider, str) and isinstance(model_id, str):
            model = f"{provider}/{model_id}"
    return {
        "backend": nested_get(event, ("backend",), ("metadata", "backend"), ("session", "backend")) or "opencode",
        "parent_session": state_metadata.get("parentSessionId") or nested_get(event, ("sessionID",), ("metadata", "parent_session")),
        "child_session": state_metadata.get("sessionId") or nested_get(event, ("session",), ("session_id",), ("metadata", "session"), ("metadata", "session_id")),
        "model": model,
    }


def extract_task_result(stdout: str, expected_subagent_type: str) -> tuple[str, dict[str, Any]]:
    events = iter_json_events(stdout)
    task_events = [
        event for event in events
        if isinstance(event, dict)
        and event.get("type") == "tool_use"
        and event_tool_name(event) == "task"
    ]
    if len(task_events) != 1:
        raise ProcessOutputError("expected exactly one task tool_use event")
    task_event = task_events[0]
    if event_status(task_event) != "completed":
        raise ProcessOutputError("task tool_use event did not complete")
    subagent_type = event_subagent_type(task_event)
    if subagent_type != expected_subagent_type:
        raise ProcessOutputError(
            f"subagent_type mismatch: got {subagent_type!r}, expected {expected_subagent_type!r}"
        )
    task_result = event_task_result(task_event)
    if task_result is None or not task_result.strip():
        raise ProcessOutputError("missing task_result")
    return task_result, event_metadata(task_event)


def run_opencode(
    repo_root: Path,
    prompt: str,
    timeout: float,
    executable: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        build_command(repo_root, executable),
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout,
        shell=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, help="Codex Queen role, e.g. builder_deep")
    parser.add_argument("--repo-root", required=True, type=Path, help="Repository root passed to opencode --dir")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", help="Prompt text to send to the child")
    prompt_group.add_argument("--prompt-file", type=Path, help="UTF-8 file containing the child prompt")
    parser.add_argument("--timeout", type=float, default=120.0, help="OpenCode timeout in seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        mapping = load_agent_mapping()
        opencode_role = opencode_role_for(args.role, mapping)
        repo_root = args.repo_root.resolve()
        if not repo_root.is_dir():
            raise DispatchError(f"repo root does not exist: {repo_root}")
        prompt = build_dispatch_prompt(args.role, opencode_role, read_prompt(args))
        executable = resolve_opencode_executable()
    except (OSError, DispatchError, json.JSONDecodeError) as exc:
        print(compact_json({"backend": "opencode", "error": str(exc)}), file=sys.stderr)
        return EXIT_CONFIG

    try:
        completed = run_opencode(repo_root, prompt, args.timeout, executable)
    except subprocess.TimeoutExpired:
        print(compact_json({"backend": "opencode", "error": "timeout"}), file=sys.stderr)
        return EXIT_TIMEOUT
    except OSError as exc:
        print(compact_json({"backend": "opencode", "error": str(exc)}), file=sys.stderr)
        return EXIT_PROCESS

    if completed.returncode != 0:
        print(compact_json({"backend": "opencode", "returncode": completed.returncode}), file=sys.stderr)
        return EXIT_PROCESS

    try:
        task_result_text, metadata = extract_task_result(completed.stdout, opencode_role)
        metadata["role"] = normalize_role(args.role)
        result = parse_result_text(task_result_text)
        validate_result(args.role, result)
    except ProcessOutputError as exc:
        print(compact_json({"backend": "opencode", "role": normalize_role(args.role), "error": str(exc)}), file=sys.stderr)
        return EXIT_RESULT
    except (ContractError, DispatchError, json.JSONDecodeError) as exc:
        print(compact_json({"backend": "opencode", "role": normalize_role(args.role), "error": str(exc)}), file=sys.stderr)
        return EXIT_CONTRACT

    print(compact_json(result))
    print(compact_json(metadata), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
