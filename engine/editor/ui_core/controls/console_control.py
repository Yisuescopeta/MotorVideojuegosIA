"""Pure console control model for gradual editor control migration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

LogEntry = tuple[str, str]


@dataclass(slots=True)
class ConsoleCommandResult:
    output: str = ""
    clear_logs: bool = False
    show_debug: bool | None = None


@dataclass(slots=True)
class ConsoleControlModel:
    show_info: bool = True
    show_warn: bool = True
    show_err: bool = True
    show_debug: bool = True
    search_text: str = ""
    command_text: str = ""
    command_output: str = ""
    scroll_offset: float = 0.0

    INFO = "INFO"
    WARNING = "WARN"
    ERROR = "ERR"
    DEBUG = "DEBUG"

    def count_by_level(self, logs: Iterable[LogEntry]) -> dict[str, int]:
        counts = {self.INFO: 0, self.WARNING: 0, self.ERROR: 0, self.DEBUG: 0}
        for level, _message in logs:
            if level in counts:
                counts[level] += 1
        return counts

    def filtered_logs(self, logs: Iterable[LogEntry]) -> list[LogEntry]:
        query = self.search_text.strip().lower()
        filtered: list[LogEntry] = []
        for level, message in logs:
            if level == self.INFO and not self.show_info:
                continue
            if level == self.WARNING and not self.show_warn:
                continue
            if level == self.ERROR and not self.show_err:
                continue
            if level == self.DEBUG and not self.show_debug:
                continue
            if query and query not in message.lower() and query not in level.lower():
                continue
            filtered.append((level, message))
        return filtered

    def execute_command(self, text: str, now: Callable[[], datetime] | None = None) -> ConsoleCommandResult:
        command = text.strip()
        if not command:
            return ConsoleCommandResult()
        lower = command.lower()
        if lower == "help":
            return ConsoleCommandResult("Commands: help, clear, echo <text>, toggle_debug, version, time")
        if lower == "clear":
            return ConsoleCommandResult("Console cleared.", clear_logs=True)
        if lower.startswith("echo "):
            return ConsoleCommandResult(command[5:])
        if lower == "toggle_debug":
            show_debug = not self.show_debug
            return ConsoleCommandResult(
                f"Debug logs {'shown' if show_debug else 'hidden'}.",
                show_debug=show_debug,
            )
        if lower == "version":
            return ConsoleCommandResult("Motor editor console v1")
        if lower == "time":
            clock = now or datetime.now
            return ConsoleCommandResult(clock().isoformat(timespec="seconds"))
        return ConsoleCommandResult(f"Unknown command: {command}")
