from __future__ import annotations

import difflib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from engine.agent.command_policy import AgentCommandPolicy, AgentCommandRequest
from engine.agent.command_runner import AgentCommandRunner
from engine.agent.engine_port import AgentEnginePort
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
COMMAND_POLICY = AgentCommandPolicy()


@dataclass(frozen=True)
class AgentToolSpec:
    name: str
    description: str
    mutating: bool = False
    permission_scope: str = "read"
    destructive: bool = False
    requires_approval: bool = False
    allowed_in_full_access: bool = True
    supports_preview: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "mutating": self.mutating,
            "permission_scope": self.permission_scope,
            "read_only": not self.mutating,
            "destructive": self.destructive,
            "requires_approval": self.requires_approval or self.mutating,
            "allowed_in_full_access": self.allowed_in_full_access,
            "supports_preview": self.supports_preview,
        }


@dataclass(frozen=True)
class AgentToolContext:
    project_root: Path
    api: "EngineAPI | None" = None
    engine_port: AgentEnginePort | None = None


@dataclass(frozen=True)
class AgentToolPreparedCall:
    call: AgentToolCall
    preview: str = ""
    requires_approval: bool = False
    reason: str = ""
    blocked_result: AgentToolResult | None = None


class AgentTool(Protocol):
    spec: AgentToolSpec

    def validate(self, args: dict[str, Any], context: AgentToolContext) -> str:
        ...

    def preview(self, args: dict[str, Any], context: AgentToolContext) -> str:
        ...

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        ...


class BaseAgentTool:
    spec = AgentToolSpec(name="base", description="")

    def validate(self, args: dict[str, Any], context: AgentToolContext) -> str:
        return ""

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


def _default_capabilities() -> dict[str, Any]:
    from engine.ai import get_default_registry

    return get_default_registry().to_dict()


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
    spec = AgentToolSpec(
        "write_file",
        "Write a file inside the project.",
        mutating=True,
        permission_scope="write",
        requires_approval=True,
        supports_preview=True,
    )

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
    spec = AgentToolSpec(
        "edit_file",
        "Replace text in a file inside the project.",
        mutating=True,
        permission_scope="write",
        requires_approval=True,
        supports_preview=True,
    )

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
    spec = AgentToolSpec(
        "run_command",
        "Run an allowlisted command from the project root.",
        mutating=True,
        permission_scope="shell",
        requires_approval=True,
        supports_preview=True,
    )

    def validate(self, args: dict[str, Any], context: AgentToolContext) -> str:
        command = str(args.get("command", "")).strip()
        timeout_seconds = int(args.get("timeout_seconds", 30))
        decision = COMMAND_POLICY.decide(
            AgentCommandRequest(command=command, project_root=context.project_root, timeout_seconds=timeout_seconds)
        )
        return "" if decision.allowed else decision.reason

    def preview(self, args: dict[str, Any], context: AgentToolContext) -> str:
        command = str(args.get("command", "")).strip()
        timeout_seconds = int(args.get("timeout_seconds", 30))
        decision = COMMAND_POLICY.decide(
            AgentCommandRequest(command=command, project_root=context.project_root, timeout_seconds=timeout_seconds)
        )
        return json.dumps(decision.to_dict(), indent=2, ensure_ascii=True)

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        command = str(call.args.get("command", "")).strip()
        timeout_seconds = int(call.args.get("timeout_seconds", 30))
        decision = COMMAND_POLICY.decide(
            AgentCommandRequest(command=command, project_root=context.project_root, timeout_seconds=timeout_seconds)
        )
        if not decision.allowed:
            return self.fail(call, decision.reason, {"command_policy": decision.to_dict()})
        result = AgentCommandRunner(context.project_root).run(decision)
        return AgentToolResult(
            call.tool_call_id,
            call.tool_name,
            result.success,
            output=result.output,
            data={
                "returncode": result.returncode,
                "duration_ms": result.duration_ms,
                "command_policy": decision.to_dict(),
                "command_runner": result.audit,
            },
            error=result.error,
        )


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
    spec = AgentToolSpec(
        "git_stage",
        "Stage paths in git.",
        mutating=True,
        permission_scope="git_write",
        requires_approval=True,
        supports_preview=True,
    )

    def preview(self, args: dict[str, Any], context: AgentToolContext) -> str:
        paths = args.get("paths", [])
        if isinstance(paths, str):
            paths = [paths]
        return "Stage paths: " + ", ".join(str(path) for path in paths)

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        paths = call.args.get("paths", [])
        if isinstance(paths, str):
            paths = [paths]
        safe_paths = [_relative(_resolve_project_path(context.project_root, path, allow_missing=True), context.project_root) for path in paths]
        if not safe_paths:
            return self.fail(call, "paths is required")
        return _run_git(call, context, ["add", "--", *safe_paths])


class GitCommitTool(BaseAgentTool):
    spec = AgentToolSpec(
        "git_commit",
        "Create a git commit.",
        mutating=True,
        permission_scope="git_write",
        requires_approval=True,
        supports_preview=True,
    )

    def preview(self, args: dict[str, Any], context: AgentToolContext) -> str:
        return f"Create git commit: {str(args.get('message', '')).strip()}"

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
        if context.engine_port is None:
            return self.fail(call, "Engine port is not attached to this agent session.")
        try:
            data = context.engine_port.context_snapshot(call.args)
            return self.ok(call, json.dumps(data, indent=2, ensure_ascii=True), data)
        except Exception as exc:
            return self.fail(call, str(exc))


class EngineCapabilitiesTool(BaseAgentTool):
    spec = AgentToolSpec("engine_capabilities", "List engine AI-facing capabilities.")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        try:
            data = context.engine_port.capabilities() if context.engine_port is not None else _default_capabilities()
            return self.ok(call, json.dumps(data, indent=2, ensure_ascii=True), data)
        except Exception as exc:
            return self.fail(call, str(exc))


class EngineAuthoringExecuteTool(BaseAgentTool):
    spec = AgentToolSpec(
        "engine_authoring_execute",
        "Execute structured authoring operations through EngineAPI.",
        mutating=True,
        permission_scope="engine_authoring",
        requires_approval=True,
        supports_preview=True,
    )

    def preview(self, args: dict[str, Any], context: AgentToolContext) -> str:
        operations = args.get("operations", [])
        return json.dumps({"operations": operations, "target_scene_ref": args.get("target_scene_ref", "")}, indent=2, ensure_ascii=True)

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        if context.engine_port is None:
            return self.fail(call, "Engine port is not attached to this agent session.")
        try:
            data = context.engine_port.authoring_execute(call.args)
            return self.ok(call, json.dumps(data, indent=2, ensure_ascii=True), data)
        except Exception as exc:
            return self.fail(call, str(exc))


class EngineValidateTool(BaseAgentTool):
    spec = AgentToolSpec("engine_validate", "Validate a scene payload or scene file through workflow validators.")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        try:
            if context.engine_port is not None:
                data = context.engine_port.validate(call.args, context.project_root)
            else:
                from engine.workflows.ai_assist import validate_scene_payload

                payload = call.args.get("scene_payload")
                if payload is None:
                    path = _resolve_project_path(context.project_root, call.args.get("path", ""), allow_missing=False)
                    payload = json.loads(path.read_text(encoding="utf-8"))
                data = validate_scene_payload(payload).to_dict()
            return self.ok(call, json.dumps(data, indent=2, ensure_ascii=True), data)
        except Exception as exc:
            return self.fail(call, str(exc))


class EngineVerifyTool(BaseAgentTool):
    spec = AgentToolSpec("engine_verify", "Run a headless verification scenario.")

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        try:
            if context.engine_port is None:
                return self.fail(call, "Engine port is not attached to this agent session.")
            data = context.engine_port.verify(call.args, context.project_root)
            return self.ok(call, json.dumps(data, indent=2, ensure_ascii=True), data)
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
        return bool(tool and (tool.spec.requires_approval or tool.spec.mutating))

    def prepare(
        self,
        call: AgentToolCall,
        context: AgentToolContext,
        *,
        require_confirmation: bool,
    ) -> AgentToolPreparedCall:
        tool = self.get(call.tool_name)
        if tool is None:
            return AgentToolPreparedCall(
                call,
                blocked_result=AgentToolResult(call.tool_call_id, call.tool_name, False, error=f"Unknown tool: {call.tool_name}"),
            )
        if not tool.spec.allowed_in_full_access:
            return AgentToolPreparedCall(
                call,
                blocked_result=AgentToolResult(
                    call.tool_call_id,
                    call.tool_name,
                    False,
                    error=f"Tool is not allowed in full_access mode: {call.tool_name}",
                ),
            )
        try:
            validation_error = tool.validate(call.args, context)
        except Exception as exc:
            validation_error = str(exc)
        if validation_error:
            return AgentToolPreparedCall(
                call,
                blocked_result=AgentToolResult(call.tool_call_id, call.tool_name, False, error=validation_error),
            )
        preview = ""
        if tool.spec.supports_preview or tool.spec.mutating:
            try:
                preview = tool.preview(call.args, context)
            except Exception as exc:
                preview = f"Preview failed: {exc}"
        needs_approval = require_confirmation and (tool.spec.requires_approval or tool.spec.mutating)
        return AgentToolPreparedCall(
            call,
            preview=preview,
            requires_approval=needs_approval,
            reason=f"{call.tool_name} requires confirmation in confirm_actions mode." if needs_approval else "",
        )

    def preview(self, call: AgentToolCall, context: AgentToolContext) -> str:
        tool = self.get(call.tool_name)
        if tool is None:
            return f"Unknown tool: {call.tool_name}"
        return tool.preview(call.args, context)

    def execute(self, call: AgentToolCall, context: AgentToolContext) -> AgentToolResult:
        tool = self.get(call.tool_name)
        if tool is None:
            return AgentToolResult(call.tool_call_id, call.tool_name, False, error=f"Unknown tool: {call.tool_name}")
        try:
            return tool.execute(call, context)
        except Exception as exc:
            return AgentToolResult(call.tool_call_id, call.tool_name, False, error=str(exc))
