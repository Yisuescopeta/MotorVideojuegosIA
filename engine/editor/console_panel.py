"""
engine/editor/console_panel.py - Panel de Consola estilo Unity
"""

from typing import Any

import pyray as rl
from engine.core.runtime_logging import GLOBAL_LOGS, log_debug, log_err, log_info, log_warn  # noqa: F401
from engine.editor.render_safety import gui_toggle_bool
from engine.editor.theme import get_active_theme
from engine.editor.theme.fonts import get_mono_font
from engine.editor.ui.text_input_render import process_text_input, render_text_input
from engine.editor.ui_core.controls.console_control import ConsoleControlModel
from engine.editor.ui_core.controls.text_input import TextInput


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
        self.command_output = ""
        self.panel_rect = rl.Rectangle(0, 0, 0, 0)
        self.toolbar_rect = rl.Rectangle(0, 0, 0, 0)
        self.body_rect = rl.Rectangle(0, 0, 0, 0)
        self.search_rect = rl.Rectangle(0, 0, 0, 0)
        self.command_rect = rl.Rectangle(0, 0, 0, 0)
        self.control_model = ConsoleControlModel()
        self.search_input = TextInput(placeholder="Search...", max_length=64, font_size=10)
        self.command_input = TextInput(placeholder="Command: help", max_length=128, font_size=10)
        self._mono_font: Any = None
        log_info("Console initialized.")

    @property
    def search_text(self) -> str:
        return self.search_input.text

    @search_text.setter
    def search_text(self, value: str) -> None:
        self.search_input.set_text(value)

    @property
    def command_text(self) -> str:
        return self.command_input.text

    @command_text.setter
    def command_text(self, value: str) -> None:
        self.command_input.set_text(value)

    def clear(self) -> None:
        GLOBAL_LOGS.clear()

    def _count_by_level(self) -> dict[str, int]:
        self._sync_control_model_from_panel()
        return self.control_model.count_by_level(GLOBAL_LOGS)

    def _get_filtered_logs(self) -> list[tuple[str, str]]:
        self._sync_control_model_from_panel()
        return self.control_model.filtered_logs(GLOBAL_LOGS)

    def _execute_command(self, text: str) -> str:
        self._sync_control_model_from_panel()
        result = self.control_model.execute_command(text)
        if result.clear_logs:
            self.clear()
        if result.show_debug is not None:
            self.show_debug = result.show_debug
        self._sync_control_model_from_panel()
        return result.output

    def _sync_control_model_from_panel(self) -> None:
        self.control_model.show_info = self.show_info
        self.control_model.show_warn = self.show_warn
        self.control_model.show_err = self.show_err
        self.control_model.show_debug = self.show_debug
        self.control_model.search_text = self.search_text
        self.control_model.command_text = self.command_text
        self.control_model.command_output = self.command_output
        self.control_model.scroll_offset = self.scroll_offset

    def _resolve_colors(self) -> dict:
        """Resolve colors from the active editor theme."""
        try:
            theme = get_active_theme()
            return {
                "BG": rl.Color(*theme.panel),
                "BODY": rl.Color(*theme.panel_alt),
                "HEADER": rl.Color(*theme.panel_header),
                "TEXT": rl.Color(*theme.text),
                "TEXT_DIM": rl.Color(*theme.text_muted),
                "BORDER": rl.Color(*theme.border),
            }
        except Exception:
            return {
                "BG": self.UNITY_BG,
                "BODY": self.UNITY_BODY,
                "HEADER": self.UNITY_HEADER,
                "TEXT": self.UNITY_TEXT,
                "TEXT_DIM": self.UNITY_TEXT_DIM,
                "BORDER": self.UNITY_BORDER,
            }

    def render(self, x: int, y: int, width: int, height: int) -> None:
        """Renderiza la consola dentro del rectangulo de contenido inferior."""
        self.panel_rect = rl.Rectangle(float(x), float(y), float(max(0, width)), float(max(0, height)))
        toolbar_h = min(self.TOOLBAR_HEIGHT, max(0, height))
        self.toolbar_rect = rl.Rectangle(float(x), float(y), float(max(0, width)), float(toolbar_h))
        body_y = y + toolbar_h
        body_h = max(0, height - toolbar_h)
        command_h = 24 if body_h >= 48 else 0
        self.body_rect = rl.Rectangle(float(x), float(body_y), float(max(0, width)), float(max(0, body_h - command_h)))
        self.command_rect = rl.Rectangle(float(x + 4), float(y + height - command_h + 2), float(max(0, width - 8)), float(max(0, command_h - 4)))
        colors = self._resolve_colors()
        is_window_ready = getattr(rl, "is_window_ready", None)
        use_text_ex = False
        if callable(is_window_ready):
            try:
                use_text_ex = bool(is_window_ready())
            except Exception:
                use_text_ex = False

        rl.draw_rectangle_rec(self.panel_rect, colors["BG"])
        rl.draw_rectangle_rec(self.toolbar_rect, colors["HEADER"])
        rl.draw_line(x, y + toolbar_h - 1, x + width, y + toolbar_h - 1, colors["BORDER"])
        if self.body_rect.width > 0 and self.body_rect.height > 0:
            rl.draw_rectangle_rec(self.body_rect, colors["BODY"])
            rl.draw_rectangle_lines_ex(self.body_rect, 1, colors["BORDER"])

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
        rl.draw_text(badge_text, fx + 72, y + 7, 10, colors["TEXT_DIM"])
        self.search_rect = rl.Rectangle(float(max(x + width - 190, fx + 185)), float(y + 3), 180.0, 18.0)
        self.search_input.arrange((self.search_rect.x, self.search_rect.y, self.search_rect.width, self.search_rect.height))
        render_text_input(self.search_input, self.search_input.focused)

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
                colors["TEXT_DIM"],
            )
        else:
            visible_bottom = int(self.body_rect.y + self.body_rect.height)
            for index, (ltype, msg) in enumerate(filtered_logs):
                if curr_y + line_height < int(self.body_rect.y):
                    curr_y += line_height
                    continue
                if curr_y > visible_bottom:
                    break

                color = colors["TEXT"]
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
                if use_text_ex:
                    if self._mono_font is None:
                        self._mono_font = get_mono_font(10)
                    if self._mono_font is not None:
                        rl.draw_text_ex(
                            self._mono_font,
                            msg,
                            rl.Vector2(float(self.body_rect.x) + 40, float(curr_y + 4)),
                            10,
                            0,
                            colors["TEXT"],
                        )
                    else:
                        rl.draw_text(msg, int(self.body_rect.x) + 40, curr_y + 4, 10, colors["TEXT"])
                else:
                    rl.draw_text(msg, int(self.body_rect.x) + 40, curr_y + 4, 10, colors["TEXT"])
                rl.draw_line(
                    int(self.body_rect.x),
                    curr_y + line_height - 1,
                    int(self.body_rect.x + self.body_rect.width),
                    curr_y + line_height - 1,
                    rl.Color(45, 45, 45, 255),
                )
                curr_y += line_height

        if self.command_rect.height > 0:
            self.command_input.arrange((self.command_rect.x, self.command_rect.y, self.command_rect.width, self.command_rect.height))
            render_text_input(self.command_input, self.command_input.focused)
            if self.command_output:
                rl.draw_text(self.command_output[:80], int(self.command_rect.x + 8), int(self.command_rect.y - 14), 9, colors["TEXT_DIM"])

    def _handle_text_input(self) -> None:
        mouse_pos = rl.get_mouse_position()
        if rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            if rl.check_collision_point_rec(mouse_pos, self.search_rect):
                self.search_input._focused = True
                self.command_input._focused = False
            elif rl.check_collision_point_rec(mouse_pos, self.command_rect):
                self.command_input._focused = True
                self.search_input._focused = False
            else:
                self.search_input._focused = False
                self.command_input._focused = False

        if self.search_input.focused:
            process_text_input(self.search_input)

        if self.command_input.focused:
            process_text_input(self.command_input)
            if rl.is_key_pressed(rl.KEY_ENTER) or rl.is_key_pressed(rl.KEY_KP_ENTER):
                cmd = self.command_input.text
                result = self._execute_command(cmd)
                self.command_output = result
                self.command_input.set_text("")
                if result:
                    log_info(result)
