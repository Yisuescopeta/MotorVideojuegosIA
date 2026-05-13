"""
engine/editor/console_panel.py - Panel de Consola estilo Unity
"""

from datetime import datetime
from typing import List, Tuple

import pyray as rl
from engine.editor.render_safety import gui_toggle_bool

# Sistema de Logs Global
GLOBAL_LOGS: List[Tuple[str, str]] = []


def log_info(msg: str):
    GLOBAL_LOGS.append(("INFO", msg))


def log_warn(msg: str):
    GLOBAL_LOGS.append(("WARN", msg))


def log_err(msg: str):
    GLOBAL_LOGS.append(("ERR", msg))


def log_debug(msg: str):
    GLOBAL_LOGS.append(("DEBUG", msg))


class ConsolePanel:
    UNITY_BG = rl.Color(32, 32, 32, 255)
    UNITY_BODY = rl.Color(36, 36, 36, 255)
    UNITY_HEADER = rl.Color(56, 56, 56, 255)
    UNITY_TEXT = rl.Color(200, 200, 200, 255)
    UNITY_TEXT_DIM = rl.Color(128, 128, 128, 255)
    UNITY_BORDER = rl.Color(25, 25, 25, 255)
    TOOLBAR_HEIGHT = 24
    PANEL_PADDING = 4

    INFO = "INFO"
    WARNING = "WARN"
    ERROR = "ERR"
    DEBUG = "DEBUG"

    def __init__(self) -> None:
        self.scroll_offset: float = 0.0
        self.show_info = True
        self.show_warn = True
        self.show_err = True
        self.show_debug = True
        self.search_text = ""
        self.search_focused = False
        self.command_text = ""
        self.command_focused = False
        self.command_output = ""
        self.panel_rect = rl.Rectangle(0, 0, 0, 0)
        self.toolbar_rect = rl.Rectangle(0, 0, 0, 0)
        self.body_rect = rl.Rectangle(0, 0, 0, 0)
        self.search_rect = rl.Rectangle(0, 0, 0, 0)
        self.command_rect = rl.Rectangle(0, 0, 0, 0)
        log_info("Console initialized.")

    def clear(self) -> None:
        GLOBAL_LOGS.clear()

    def _count_by_level(self) -> dict[str, int]:
        counts = {self.INFO: 0, self.WARNING: 0, self.ERROR: 0, self.DEBUG: 0}
        for level, _message in GLOBAL_LOGS:
            if level in counts:
                counts[level] += 1
        return counts

    def _get_filtered_logs(self) -> list[tuple[str, str]]:
        query = self.search_text.strip().lower()
        filtered: list[tuple[str, str]] = []
        for level, message in GLOBAL_LOGS:
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

    def _execute_command(self, text: str) -> str:
        command = text.strip()
        if not command:
            return ""
        lower = command.lower()
        if lower == "help":
            return "Commands: help, clear, echo <text>, toggle_debug, version, time"
        if lower == "clear":
            self.clear()
            return "Console cleared."
        if lower.startswith("echo "):
            return command[5:]
        if lower == "toggle_debug":
            self.show_debug = not self.show_debug
            return f"Debug logs {'shown' if self.show_debug else 'hidden'}."
        if lower == "version":
            return "Motor editor console v1"
        if lower == "time":
            return datetime.now().isoformat(timespec="seconds")
        return f"Unknown command: {command}"

    def render(self, x: int, y: int, width: int, height: int) -> None:
        """Renderiza la consola dentro del rectángulo de contenido inferior."""
        self.panel_rect = rl.Rectangle(float(x), float(y), float(max(0, width)), float(max(0, height)))
        toolbar_h = min(self.TOOLBAR_HEIGHT, max(0, height))
        self.toolbar_rect = rl.Rectangle(float(x), float(y), float(max(0, width)), float(toolbar_h))
        body_y = y + toolbar_h
        body_h = max(0, height - toolbar_h)
        command_h = 24 if body_h >= 48 else 0
        self.body_rect = rl.Rectangle(float(x), float(body_y), float(max(0, width)), float(max(0, body_h - command_h)))
        self.command_rect = rl.Rectangle(float(x + 4), float(y + height - command_h + 2), float(max(0, width - 8)), float(max(0, command_h - 4)))

        rl.draw_rectangle_rec(self.panel_rect, self.UNITY_BG)
        rl.draw_rectangle_rec(self.toolbar_rect, self.UNITY_HEADER)
        rl.draw_line(x, y + toolbar_h - 1, x + width, y + toolbar_h - 1, self.UNITY_BORDER)
        if self.body_rect.width > 0 and self.body_rect.height > 0:
            rl.draw_rectangle_rec(self.body_rect, self.UNITY_BODY)
            rl.draw_rectangle_lines_ex(self.body_rect, 1, self.UNITY_BORDER)

        if rl.gui_button(rl.Rectangle(float(x + 5), float(y + 2), 50.0, 20.0), "Clear"):
            self.clear()

        fx = x + 60
        self.show_info = gui_toggle_bool(rl.Rectangle(float(fx), float(y + 2), 60.0, 20.0), "Info", self.show_info)
        fx += 65
        self.show_warn = gui_toggle_bool(rl.Rectangle(float(fx), float(y + 2), 60.0, 20.0), "Warn", self.show_warn)
        fx += 65
        self.show_err = gui_toggle_bool(rl.Rectangle(float(fx), float(y + 2), 60.0, 20.0), "Error", self.show_err)
        fx += 65
        self.show_debug = gui_toggle_bool(rl.Rectangle(float(fx), float(y + 2), 66.0, 20.0), "Debug", self.show_debug)

        counts = self._count_by_level()
        badge_text = f"I:{counts[self.INFO]} W:{counts[self.WARNING]} E:{counts[self.ERROR]} D:{counts[self.DEBUG]}"
        rl.draw_text(badge_text, fx + 72, y + 7, 10, self.UNITY_TEXT_DIM)
        self.search_rect = rl.Rectangle(float(max(x + width - 190, fx + 185)), float(y + 3), 180.0, 18.0)
        self._draw_text_input(self.search_rect, self.search_text, "Search", self.search_focused)

        self._handle_text_input()

        if self.body_rect.width <= 0 or self.body_rect.height <= 0:
            return

        filtered_logs = self._get_filtered_logs()

        line_height = 18
        visible_lines = max(1, int(self.body_rect.height) // line_height)
        max_scroll = max(0.0, float(max(0, len(filtered_logs) - visible_lines) * line_height))
        self.scroll_offset = min(max_scroll, max(0.0, self.scroll_offset))

        mouse_pos = rl.get_mouse_position()
        if rl.check_collision_point_rec(mouse_pos, self.body_rect):
            self.scroll_offset -= rl.get_mouse_wheel_move() * 20
            self.scroll_offset = min(max_scroll, max(0.0, self.scroll_offset))

        curr_y = int(self.body_rect.y) + self.PANEL_PADDING - int(self.scroll_offset)
        if not filtered_logs:
            rl.draw_text(
                "No console messages yet",
                int(self.body_rect.x) + 10,
                int(self.body_rect.y) + 12,
                11,
                self.UNITY_TEXT_DIM,
            )
        else:
            visible_bottom = int(self.body_rect.y + self.body_rect.height)
            for index, (ltype, msg) in enumerate(filtered_logs):
                if curr_y + line_height < int(self.body_rect.y):
                    curr_y += line_height
                    continue
                if curr_y > visible_bottom:
                    break

                color = self.UNITY_TEXT
                if ltype == self.WARNING:
                    color = rl.YELLOW
                elif ltype == self.ERROR:
                    color = rl.RED
                elif ltype == self.DEBUG:
                    color = rl.SKYBLUE

                if index % 2 == 0:
                    rl.draw_rectangle(int(self.body_rect.x), curr_y, int(self.body_rect.width), line_height, rl.Color(0, 0, 0, 20))

                icon = "(!)" if ltype == self.ERROR else ("/!\\") if ltype == self.WARNING else "(#)" if ltype == self.DEBUG else "(i)"
                rl.draw_text(icon, int(self.body_rect.x) + 10, curr_y + 4, 10, color)
                rl.draw_text(msg, int(self.body_rect.x) + 40, curr_y + 4, 10, self.UNITY_TEXT)
                rl.draw_line(
                    int(self.body_rect.x),
                    curr_y + line_height - 1,
                    int(self.body_rect.x + self.body_rect.width),
                    curr_y + line_height - 1,
                    rl.Color(45, 45, 45, 255),
                )
                curr_y += line_height

        if self.command_rect.height > 0:
            self._draw_text_input(self.command_rect, self.command_text, "Command: help", self.command_focused)
            if self.command_output:
                rl.draw_text(self.command_output[:80], int(self.command_rect.x + 8), int(self.command_rect.y - 14), 9, self.UNITY_TEXT_DIM)

    def _draw_text_input(self, rect: rl.Rectangle, value: str, placeholder: str, focused: bool) -> None:
        border = rl.SKYBLUE if focused else self.UNITY_BORDER
        rl.draw_rectangle_rec(rect, self.UNITY_BODY)
        rl.draw_rectangle_lines_ex(rect, 1, border)
        text = value if value else placeholder
        color = self.UNITY_TEXT if value else self.UNITY_TEXT_DIM
        rl.draw_text(text[:64], int(rect.x + 6), int(rect.y + 5), 10, color)
        if focused:
            cursor_x = int(rect.x + 6 + min(len(value), 64) * 6)
            rl.draw_text("_", cursor_x, int(rect.y + 5), 10, self.UNITY_TEXT)

    def _handle_text_input(self) -> None:
        mouse_pos = rl.get_mouse_position()
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            self.search_focused = rl.check_collision_point_rec(mouse_pos, self.search_rect)
            self.command_focused = rl.check_collision_point_rec(mouse_pos, self.command_rect)

        if self.search_focused:
            self.search_text = self._capture_text(self.search_text, 64)
        if self.command_focused:
            self.command_text = self._capture_text(self.command_text, 128)
            if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
                result = self._execute_command(self.command_text)
                self.command_output = result
                self.command_text = ""
                if result:
                    log_info(result)

    def _capture_text(self, value: str, max_length: int) -> str:
        if rl.is_key_pressed(rl.KEY_BACKSPACE) and value:
            value = value[:-1]
        while True:
            codepoint = rl.get_char_pressed()
            if codepoint == 0:
                break
            if codepoint in (10, 13):
                continue
            try:
                char = chr(codepoint)
            except ValueError:
                continue
            if char.isprintable() and len(value) < max_length:
                value += char
        return value
