from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class AgentCommandProfile(StrEnum):
    PYTHON_TESTS = "python_tests"
    MOTOR_CLI_READ = "motor_cli_read"
    READ_ONLY_PROBE = "read_only_probe"


@dataclass(frozen=True)
class AgentCommandRequest:
    command: str
    project_root: Path
    timeout_seconds: int = 30


@dataclass(frozen=True)
class AgentCommandDecision:
    allowed: bool
    argv: tuple[str, ...] = ()
    profile: AgentCommandProfile | None = None
    reason: str = ""
    cwd: str = ""
    timeout_seconds: int = 30

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "argv": list(self.argv),
            "profile": self.profile.value if self.profile is not None else "",
            "reason": self.reason,
            "cwd": self.cwd,
            "timeout_seconds": self.timeout_seconds,
        }


class AgentCommandPolicy:
    """Allowlist policy for the agent run_command tool.

    This is intentionally not a shell sandbox. It is a narrow argv policy that
    refuses shell syntax and executes only known profiles with shell=False.
    """

    _SHELL_METACHARS = ("&&", "||", ";", "|", ">", "<", "`", "$(", "%", "*", "?")
    _BLOCKED_EXECUTABLES = {
        "powershell",
        "powershell.exe",
        "pwsh",
        "pwsh.exe",
        "cmd",
        "cmd.exe",
        "bash",
        "bash.exe",
        "sh",
        "sh.exe",
        "del",
        "rm",
        "remove-item",
        "format",
    }
    _PYTHON_EXECUTABLES = {"py", "py.exe", "python", "python.exe"}
    _REFERENCE_DIR = "claude code"

    def decide(self, request: AgentCommandRequest) -> AgentCommandDecision:
        project_root = request.project_root.expanduser().resolve()
        command = str(request.command or "").strip()
        timeout_seconds = max(1, min(int(request.timeout_seconds or 30), 120))
        if not command:
            return self._deny("command is required", project_root, timeout_seconds)
        lowered = command.lower()
        if self._REFERENCE_DIR in lowered:
            return self._deny("Hard guard blocked access to the local Claude Code reference.", project_root, timeout_seconds)
        metachar = next((token for token in self._SHELL_METACHARS if token in command), "")
        if metachar:
            return self._deny(f"Shell metacharacters are not allowed in run_command: {metachar}", project_root, timeout_seconds)

        try:
            argv = tuple(self._split(command))
        except ValueError as exc:
            return self._deny(str(exc), project_root, timeout_seconds)
        if not argv:
            return self._deny("command is required", project_root, timeout_seconds)

        executable = self._normalize(argv[0])
        if executable in self._BLOCKED_EXECUTABLES:
            return self._deny(f"Blocked executable for run_command: {argv[0]}", project_root, timeout_seconds)
        blocked_reason = self._blocked_invocation_reason(argv)
        if blocked_reason:
            return self._deny(blocked_reason, project_root, timeout_seconds)

        profile = self._classify(argv, project_root)
        if profile is None:
            return self._deny("Command is not in an allowed run_command profile.", project_root, timeout_seconds)
        return AgentCommandDecision(
            allowed=True,
            argv=argv,
            profile=profile,
            reason=f"Allowed by profile: {profile.value}",
            cwd=project_root.as_posix(),
            timeout_seconds=timeout_seconds,
        )

    def _split(self, command: str) -> list[str]:
        parts = shlex.split(command, posix=(os.name != "nt"))
        return [self._strip_outer_quotes(part) for part in parts]

    def _classify(self, argv: tuple[str, ...], project_root: Path) -> AgentCommandProfile | None:
        executable = self._normalize(argv[0])
        if executable in self._PYTHON_EXECUTABLES and argv[1:] in {("--version",), ("-V",)}:
            return AgentCommandProfile.READ_ONLY_PROBE
        if executable in self._PYTHON_EXECUTABLES and len(argv) >= 3 and argv[1] == "-m":
            module = argv[2]
            rest = argv[3:]
            if module == "unittest" and self._valid_unittest_args(rest):
                return AgentCommandProfile.PYTHON_TESTS
            if module == "motor" and self._valid_motor_args(rest, project_root):
                return AgentCommandProfile.MOTOR_CLI_READ
        if executable == "git" and self._valid_read_only_git(argv[1:], project_root):
            return AgentCommandProfile.READ_ONLY_PROBE
        return None

    def _valid_unittest_args(self, args: tuple[str, ...]) -> bool:
        if not args:
            return False
        allowed_flags = {"-v", "--verbose", "-q", "--quiet", "-f", "--failfast", "-b", "--buffer", "-c", "--catch"}
        for arg in args:
            if arg in allowed_flags:
                continue
            if arg.startswith("-k"):
                return False
            if arg.startswith("-"):
                return False
            if "/" in arg or "\\" in arg:
                return False
            if not all(part.replace("_", "").isalnum() for part in arg.split(".")):
                return False
        return True

    def _valid_motor_args(self, args: tuple[str, ...], project_root: Path) -> bool:
        if not args:
            return False
        if args == ("--help",):
            return True
        command = args[0]
        if command == "capabilities":
            return all(arg in {"--json"} for arg in args[1:])
        if command != "doctor":
            return False
        index = 1
        while index < len(args):
            arg = args[index]
            if arg == "--json":
                index += 1
                continue
            if arg == "--project":
                if index + 1 >= len(args):
                    return False
                if not self._is_project_relative_or_inside(project_root, args[index + 1]):
                    return False
                index += 2
                continue
            return False
        return True

    def _valid_read_only_git(self, args: tuple[str, ...], project_root: Path) -> bool:
        if args in {("status", "--short"), ("status",), ("diff",)}:
            return True
        if len(args) >= 3 and args[0] == "diff" and "--" in args:
            path_arg = args[-1]
            return self._is_project_relative_or_inside(project_root, path_arg)
        return False

    def _blocked_invocation_reason(self, argv: tuple[str, ...]) -> str:
        executable = self._normalize(argv[0])
        lowered = tuple(self._normalize(arg) for arg in argv)
        if executable in self._PYTHON_EXECUTABLES and len(argv) >= 2 and argv[1] == "-c":
            return "Inline Python execution is blocked for run_command."
        if executable == "git" and len(lowered) >= 2:
            if lowered[1] in {"add", "commit", "reset", "clean", "checkout", "push", "pull", "merge", "rebase"}:
                return f"Git mutation is blocked in run_command: git {argv[1]}"
        if executable in {"rm", "del", "remove-item", "format"}:
            return f"Destructive command is blocked in run_command: {argv[0]}"
        return ""

    def _is_project_relative_or_inside(self, project_root: Path, value: str) -> bool:
        if value in {".", "./"}:
            return True
        if "claude code" in value.lower():
            return False
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = project_root / candidate
        try:
            candidate.expanduser().resolve().relative_to(project_root)
        except ValueError:
            return False
        return True

    def _deny(self, reason: str, project_root: Path, timeout_seconds: int) -> AgentCommandDecision:
        return AgentCommandDecision(
            allowed=False,
            reason=reason,
            cwd=project_root.as_posix(),
            timeout_seconds=timeout_seconds,
        )

    def _normalize(self, value: str) -> str:
        return value.strip().lower()

    def _strip_outer_quotes(self, value: str) -> str:
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            return value[1:-1]
        return value
