from __future__ import annotations

import difflib
import json
import re
import subprocess
from dataclasses import dataclass, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from engine.agent.types import AgentToolCall, AgentToolResult

if TYPE_CHECKING:
    from engine.api import EngineAPI


REFERENCE_DIR_NAME = "Claude Code"
SENSITIVE_DIRS = {".git", ".motor", REFERENCE_DIR_NAME}
IGNORED_DIRS = {*SENSITIVE_DIRS, "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
SECRET_PATTERN = re.compile(
    r"(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}|BEGIN [A-Z ]*PRIVATE KEY",
    re.IGNORECASE,
)
BLOCKED_COMMAND_PATTERNS = (
    "git reset --hard",
    "git clean -fd",
    "rm -rf",
    "rmdir /s",
    "del /s",
    "format ",
    "remove-item -recurse",
)


@dataclass(frozen=True)
class AgentToolSpec:
    name: str
    description: str
    mutating: bool = False
    permission_scope: str = "read"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "mutating": self.mutating,
            "permission_scope": self.permission_scope,
        }


@dataclass(frozen=True)
class AgentToolContext:
    project_root: Path
    api: "EngineAPI | None" = None


class AgentTool(Protocol):
    spec: AgentToolSpec

    def preview(self, args: dict[str, Any], context: AgentToolContext) -> str:
        ...

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        ...


class BaseAgentTool:
    spec = AgentToolSpec(name="base", description="")

    def preview(self, args: dict[str, Any], context: AgentToolContext) -> str:
        return f"{self.spec.name}: {json.dumps(args, ensure_ascii=True, sort_keys=True)}"

    def ok(self, call: AgentToolCall, output: str, data: dict[str, Any] | None = None) -> AgentToolResult:
        return AgentToolResult(call.tool_call_id, call.tool_name, True, output=output, data=data or {})

    def fail(self, call: AgentToolCall, message: str, data: dict[str, Any] | None = None) -> AgentToolResult:
        return AgentToolResult(call.tool_call_id, call.tool_name, False, output="", data=data or {}, error=message)


def _resolve_project_path(project_root: Path, path_value: Any, *, allow_missing: bool = True) -> Path:
    raw = str(path_value or ".").strip()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = candidate.expanduser().resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise PermissionError(f"Path outside project root: {resolved.as_posix()}") from exc
    sensitive_part = next((part for part in resolved.parts if part in SENSITIVE_DIRS), "")
    if sensitive_part:
        raise PermissionError(f"Agent tools cannot use protected project path: {sensitive_part}")
    if not allow_missing and not resolved.exists():
        raise FileNotFoundError(resolved.as_posix())
    return resolved


def _relative(path: Path, project_root: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _safe_text(path: Path, *, limit: int = 20000) -> str:
    data = path.read_text(encoding="utf-8", errors="replace")
    if len(data) > limit:
        return data[:limit] + "\n...[truncated]..."
    return data


def _diff(old: str, new: str, path: str) -> str:
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def _reject_secrets(content: str) -> None:
    if SECRET_PATTERN.search(content):
        raise PermissionError("Hard guard blocked writing content that looks like a secret.")


class ReadFileTool(BaseAgentTool):
    spec = AgentToolSpec("read_file", "Read a UTF-8 text file inside the project.")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        try:
            path = _resolve_project_path(context.project_root, call.args.get("path"), allow_missing=False)
            if not path.is_file():
                return self.fail(call, f"Not a file: {_relative(path, context.project_root)}")
            content = _safe_text(path)
            return self.ok(call, content, {"path": _relative(path, context.project_root)})
        except Exception as exc:
            return self.fail(call, str(exc))


class ListFilesTool(BaseAgentTool):
    spec = AgentToolSpec("list_files", "List files and folders inside the project.")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        try:
            root = _resolve_project_path(context.project_root, call.args.get("path", "."), allow_missing=False)
            if not root.is_dir():
                return self.fail(call, f"Not a directory: {_relative(root, context.project_root)}")
            entries: list[dict[str, Any]] = []
            for item in sorted(root.iterdir(), key=lambda value: value.name.lower()):
                if item.name in IGNORED_DIRS:
                    continue
                entries.append({"path": _relative(item, context.project_root), "type": "dir" if item.is_dir() else "file"})
                if len(entries) >= int(call.args.get("limit", 200)):
                    break
            return self.ok(call, json.dumps(entries, indent=2, ensure_ascii=True), {"entries": entries})
        except Exception as exc:
            return self.fail(call, str(exc))


class SearchTextTool(BaseAgentTool):
    spec = AgentToolSpec("search_text", "Search text files inside the project.")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        try:
            root = _resolve_project_path(context.project_root, call.args.get("path", "."), allow_missing=False)
            pattern = str(call.args.get("pattern", "")).strip()
            if not pattern:
                return self.fail(call, "pattern is required")
            regex = re.compile(pattern, re.IGNORECASE)
            files = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
            matches: list[dict[str, Any]] = []
            for path in files:
                if any(part in IGNORED_DIRS for part in path.parts):
                    continue
                if path.stat().st_size > 1_000_000:
                    continue
                for index, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                    if regex.search(line):
                        matches.append({"path": _relative(path, context.project_root), "line": index, "text": line[:240]})
                        if len(matches) >= int(call.args.get("limit", 100)):
                            return self.ok(call, json.dumps(matches, indent=2, ensure_ascii=True), {"matches": matches})
            return self.ok(call, json.dumps(matches, indent=2, ensure_ascii=True), {"matches": matches})
        except Exception as exc:
            return self.fail(call, str(exc))


class WriteFileTool(BaseAgentTool):
    spec = AgentToolSpec("write_file", "Write a file inside the project.", mutating=True, permission_scope="write")

    def preview(self, args: dict[str, Any], context: AgentToolContext) -> str:
        path = _resolve_project_path(context.project_root, args.get("path"), allow_missing=True)
        rel = _relative(path, context.project_root)
        new = str(args.get("content", ""))
        old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        return _diff(old, new, rel) or f"Create or overwrite {rel}"

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        try:
            path = _resolve_project_path(context.project_root, call.args.get("path"), allow_missing=True)
            content = str(call.args.get("content", ""))
            overwrite = bool(call.args.get("overwrite", True))
            _reject_secrets(content)
            if path.exists() and not overwrite:
                return self.fail(call, f"File already exists: {_relative(path, context.project_root)}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return self.ok(call, f"Wrote {_relative(path, context.project_root)}", {"path": _relative(path, context.project_root)})
        except Exception as exc:
            return self.fail(call, str(exc))


class EditFileTool(BaseAgentTool):
    spec = AgentToolSpec("edit_file", "Replace text in a file inside the project.", mutating=True, permission_scope="write")

    def preview(self, args: dict[str, Any], context: AgentToolContext) -> str:
        path = _resolve_project_path(context.project_root, args.get("path"), allow_missing=False)
        old_content = path.read_text(encoding="utf-8", errors="replace")
        old_text = str(args.get("old_text", ""))
        new_text = str(args.get("new_text", ""))
        new_content = old_content.replace(old_text, new_text, 0 if bool(args.get("replace_all", False)) else 1)
        return _diff(old_content, new_content, _relative(path, context.project_root))

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        try:
            path = _resolve_project_path(context.project_root, call.args.get("path"), allow_missing=False)
            old_text = str(call.args.get("old_text", ""))
            new_text = str(call.args.get("new_text", ""))
            replace_all = bool(call.args.get("replace_all", False))
            _reject_secrets(new_text)
            content = path.read_text(encoding="utf-8", errors="replace")
            if old_text not in content:
                return self.fail(call, "old_text not found")
            count = -1 if replace_all else 1
            path.write_text(content.replace(old_text, new_text, count), encoding="utf-8")
            return self.ok(call, f"Edited {_relative(path, context.project_root)}", {"path": _relative(path, context.project_root)})
        except Exception as exc:
            return self.fail(call, str(exc))


class RunCommandTool(BaseAgentTool):
    spec = AgentToolSpec("run_command", "Run a shell command from the project root.", mutating=True, permission_scope="shell")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        command = str(call.args.get("command", "")).strip()
        if not command:
            return self.fail(call, "command is required")
        lowered = command.lower()
        if any(pattern in lowered for pattern in BLOCKED_COMMAND_PATTERNS):
            return self.fail(call, "Hard guard blocked a destructive command.")
        try:
            completed = subprocess.run(
                command,
                cwd=context.project_root,
                shell=True,
                capture_output=True,
                text=True,
                timeout=int(call.args.get("timeout_seconds", 30)),
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            return self.ok(call, output[-20000:], {"returncode": completed.returncode})
        except Exception as exc:
            return self.fail(call, str(exc))


class GitStatusTool(BaseAgentTool):
    spec = AgentToolSpec("git_status", "Show git status for the project.")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        return _run_git(call, context, ["status", "--short"])


class GitDiffTool(BaseAgentTool):
    spec = AgentToolSpec("git_diff", "Show git diff for the project.")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        args = ["diff"]
        path = str(call.args.get("path", "")).strip()
        if path:
            safe = _resolve_project_path(context.project_root, path, allow_missing=True)
            args.extend(["--", _relative(safe, context.project_root)])
        return _run_git(call, context, args)


class GitStageTool(BaseAgentTool):
    spec = AgentToolSpec("git_stage", "Stage paths in git.", mutating=True, permission_scope="git_write")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        paths = call.args.get("paths", [])
        if isinstance(paths, str):
            paths = [paths]
        safe_paths = [_relative(_resolve_project_path(context.project_root, path, allow_missing=True), context.project_root) for path in paths]
        if not safe_paths:
            return self.fail(call, "paths is required")
        return _run_git(call, context, ["add", "--", *safe_paths])


class GitCommitTool(BaseAgentTool):
    spec = AgentToolSpec("git_commit", "Create a git commit.", mutating=True, permission_scope="git_write")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        message = str(call.args.get("message", "")).strip()
        if not message:
            return self.fail(call, "message is required")
        return _run_git(call, context, ["commit", "-m", message])


def _run_git(call: AgentToolCall, context: AgentToolContext, args: list[str]) -> AgentToolResult:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=context.project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        return AgentToolResult(
            call.tool_call_id,
            call.tool_name,
            completed.returncode == 0,
            output=output[-20000:],
            data={"returncode": completed.returncode},
            error="" if completed.returncode == 0 else output[-2000:],
        )
    except Exception as exc:
        return AgentToolResult(call.tool_call_id, call.tool_name, False, error=str(exc))


class EngineContextTool(BaseAgentTool):
    spec = AgentToolSpec("engine_context", "Capture an AI workflow context snapshot through EngineAPI.")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        if context.api is None:
            return self.fail(call, "EngineAPI is not attached to this agent session.")
        try:
            from engine.workflows.ai_assist import build_project_context_snapshot

            snapshot = build_project_context_snapshot(context.api, snapshot_id=str(call.args.get("snapshot_id", "agent-context")))
            return self.ok(call, json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=True), snapshot.to_dict())
        except Exception as exc:
            return self.fail(call, str(exc))


class EngineCapabilitiesTool(BaseAgentTool):
    spec = AgentToolSpec("engine_capabilities", "List engine AI-facing capabilities.")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        try:
            from engine.ai import get_default_registry

            data = get_default_registry().to_dict()
            return self.ok(call, json.dumps(data, indent=2, ensure_ascii=True), data)
        except Exception as exc:
            return self.fail(call, str(exc))


class EngineAuthoringExecuteTool(BaseAgentTool):
    spec = AgentToolSpec(
        "engine_authoring_execute",
        "Execute structured authoring operations through EngineAPI.",
        mutating=True,
        permission_scope="engine_authoring",
    )

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        if context.api is None:
            return self.fail(call, "EngineAPI is not attached to this agent session.")
        try:
            from engine.workflows.ai_assist import AuthoringExecutionService
            from engine.workflows.ai_assist.types import (
                AuthoringEntityPropertyKind,
                AuthoringExecutionOperation,
                AuthoringExecutionOperationKind,
                AuthoringExecutionRequest,
            )

            allowed = {field.name for field in fields(AuthoringExecutionOperation)}
            operations = []
            for raw in call.args.get("operations", []):
                payload = {key: value for key, value in dict(raw).items() if key in allowed}
                payload["kind"] = AuthoringExecutionOperationKind(str(payload["kind"]))
                if payload.get("property_kind"):
                    payload["property_kind"] = AuthoringEntityPropertyKind(str(payload["property_kind"]))
                operations.append(AuthoringExecutionOperation(**payload))
            request = AuthoringExecutionRequest(
                request_id=str(call.args.get("request_id", "agent-authoring")),
                label=str(call.args.get("label", "agent_authoring")),
                operations=operations,
                target_scene_ref=str(call.args.get("target_scene_ref", "")),
                metadata=dict(call.args.get("metadata", {})),
            )
            result = AuthoringExecutionService(context.api).execute(request)
            return self.ok(call, json.dumps(result.to_dict(), indent=2, ensure_ascii=True), result.to_dict())
        except Exception as exc:
            return self.fail(call, str(exc))


class EngineValidateTool(BaseAgentTool):
    spec = AgentToolSpec("engine_validate", "Validate a scene payload or scene file through workflow validators.")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        try:
            from engine.workflows.ai_assist import validate_scene_payload

            payload = call.args.get("scene_payload")
            if payload is None:
                path_value = call.args.get("path", "")
                if not path_value and context.api is not None:
                    path_value = context.api.get_active_scene().get("path", "")
                path = _resolve_project_path(context.project_root, path_value, allow_missing=False)
                payload = json.loads(path.read_text(encoding="utf-8"))
            report = validate_scene_payload(payload)
            return self.ok(call, json.dumps(report.to_dict(), indent=2, ensure_ascii=True), report.to_dict())
        except Exception as exc:
            return self.fail(call, str(exc))


class EngineVerifyTool(BaseAgentTool):
    spec = AgentToolSpec("engine_verify", "Run a headless verification scenario.")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        try:
            from engine.workflows.ai_assist import HeadlessVerificationService
            from engine.workflows.ai_assist.types import (
                HeadlessVerificationAssertion,
                HeadlessVerificationAssertionKind,
                HeadlessVerificationScenario,
            )

            scenario_data = dict(call.args.get("scenario", call.args))
            assertions = []
            for raw in scenario_data.get("assertions", []):
                payload = dict(raw)
                payload["kind"] = HeadlessVerificationAssertionKind(str(payload["kind"]))
                assertions.append(HeadlessVerificationAssertion(**payload))
            scenario_root = _resolve_project_path(
                context.project_root,
                scenario_data.get("project_root", "."),
                allow_missing=False,
            )
            if not scenario_root.is_dir():
                return self.fail(call, f"Not a directory: {_relative(scenario_root, context.project_root)}")
            scenario = HeadlessVerificationScenario(
                scenario_id=str(scenario_data.get("scenario_id", "agent-verification")),
                project_root=scenario_root.as_posix(),
                scene_path=str(scenario_data.get("scene_path", "")),
                assertions=assertions,
                seed=scenario_data.get("seed"),
                play=bool(scenario_data.get("play", False)),
                step_frames=int(scenario_data.get("step_frames", 0)),
                recent_event_limit=int(scenario_data.get("recent_event_limit", 50)),
            )
            report = HeadlessVerificationService().run(scenario)
            return self.ok(call, json.dumps(report.to_dict(), indent=2, ensure_ascii=True), report.to_dict())
        except Exception as exc:
            return self.fail(call, str(exc))


class AgentToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}
        for tool in (
            ReadFileTool(),
            ListFilesTool(),
            SearchTextTool(),
            WriteFileTool(),
            EditFileTool(),
            RunCommandTool(),
            GitStatusTool(),
            GitDiffTool(),
            GitStageTool(),
            GitCommitTool(),
            EngineContextTool(),
            EngineCapabilitiesTool(),
            EngineAuthoringExecuteTool(),
            EngineValidateTool(),
            EngineVerifyTool(),
        ):
            self.register(tool)

    def register(self, tool: AgentTool) -> None:
        self._tools[tool.spec.name] = tool

    def get(self, name: str) -> AgentTool | None:
        return self._tools.get(name)

    def list_specs(self) -> list[dict[str, Any]]:
        return [tool.spec.to_dict() for tool in sorted(self._tools.values(), key=lambda value: value.spec.name)]

    def requires_confirmation(self, name: str) -> bool:
        tool = self.get(name)
        return bool(tool and tool.spec.mutating)

    def preview(self, call: AgentToolCall, context: AgentToolContext) -> str:
        tool = self.get(call.tool_name)
        if tool is None:
            return f"Unknown tool: {call.tool_name}"
        return tool.preview(call.args, context)

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        tool = self.get(call.tool_name)
        if tool is None:
            return AgentToolResult(call.tool_call_id, call.tool_name, False, error=f"Unknown tool: {call.tool_name}")
        return tool.execute(call, context)
