"""Small editor toast notification manager."""

from __future__ import annotations

import time
from dataclasses import dataclass

import pyray as rl


@dataclass(frozen=True)
class ToastMessage:
    id: int
    level: str
    message: str
    created_at: float
    duration_ms: int


class ToastManager:
    INFO = "INFO"
    WARN = "WARN"
    ERR = "ERR"
    DEBUG = "DEBUG"

    _LEVELS = {INFO, WARN, ERR, DEBUG}
    _ALIASES = {
        "INFO": INFO,
        "INFORMATION": INFO,
        "WARN": WARN,
        "WARNING": WARN,
        "ERR": ERR,
        "ERROR": ERR,
        "DEBUG": DEBUG,
    }

    def __init__(self, max_visible: int = 5) -> None:
        self.max_visible = max(1, int(max_visible))
        self._toasts: list[ToastMessage] = []
        self._next_id = 1

    def add(self, level: str, message: str, duration_ms: int = 4000) -> int:
        toast_id = self._next_id
        self._next_id += 1
        toast = ToastMessage(
            id=toast_id,
            level=self._normalize_level(level),
            message=str(message),
            created_at=time.monotonic(),
            duration_ms=max(0, int(duration_ms)),
        )
        self._toasts.append(toast)
        return toast_id

    def dismiss(self, toast_id: int) -> None:
        self._toasts = [toast for toast in self._toasts if toast.id != toast_id]

    def clear(self) -> None:
        self._toasts.clear()

    def update(self, now: float | None = None) -> None:
        now_seconds = self._now_seconds(now)
        self._toasts = [toast for toast in self._toasts if not self._expired(toast, now_seconds)]

    def visible_toasts(self, now: float | None = None) -> list[ToastMessage]:
        self.update(now)
        return list(self._toasts[-self.max_visible :])

    def render(self, screen_width: int, screen_height: int) -> None:
        toasts = self.visible_toasts()
        if not toasts:
            return

        width = min(360, max(180, int(screen_width) - 24))
        x = max(8, int(screen_width) - width - 12)
        y = max(8, int(screen_height) - 12 - len(toasts) * 54)
        for toast in toasts:
            rect = rl.Rectangle(float(x), float(y), float(width), 46.0)
            rl.draw_rectangle_rec(rect, rl.Color(24, 24, 24, 230))
            rl.draw_rectangle_lines_ex(rect, 1, self._level_color(toast.level))
            rl.draw_text(toast.level, x + 10, y + 8, 10, self._level_color(toast.level))
            rl.draw_text(toast.message[:72], x + 10, y + 24, 10, rl.Color(235, 235, 235, 255))
            y += 54

    def _normalize_level(self, level: str) -> str:
        return self._ALIASES.get(str(level).strip().upper(), self.INFO)

    def _now_seconds(self, now: float | None) -> float:
        return time.monotonic() if now is None else float(now)

    def _expired(self, toast: ToastMessage, now_seconds: float) -> bool:
        return toast.duration_ms == 0 or (now_seconds - toast.created_at) * 1000.0 >= toast.duration_ms

    def _level_color(self, level: str) -> rl.Color:
        if level == self.WARN:
            return rl.YELLOW
        if level == self.ERR:
            return rl.RED
        if level == self.DEBUG:
            return rl.SKYBLUE
        return rl.GREEN


TOAST_MANAGER = ToastManager()


def toast_info(message: str, duration_ms: int = 4000) -> int:
    return TOAST_MANAGER.add(ToastManager.INFO, message, duration_ms)


def toast_warn(message: str, duration_ms: int = 4000) -> int:
    return TOAST_MANAGER.add(ToastManager.WARN, message, duration_ms)


def toast_err(message: str, duration_ms: int = 4000) -> int:
    return TOAST_MANAGER.add(ToastManager.ERR, message, duration_ms)


def toast_debug(message: str, duration_ms: int = 4000) -> int:
    return TOAST_MANAGER.add(ToastManager.DEBUG, message, duration_ms)
