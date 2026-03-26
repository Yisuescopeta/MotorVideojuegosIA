"""
engine/editor/console_panel.py - Panel de Consola estilo Unity
"""

import pyray as rl
from typing import List, Tuple

# Sistema de Logs Global
GLOBAL_LOGS: List[Tuple[str, str]] = []


def log_info(msg: str):
    GLOBAL_LOGS.append(("INFO", msg))


def log_warn(msg: str):
    GLOBAL_LOGS.append(("WARN", msg))


def log_err(msg: str):
    GLOBAL_LOGS.append(("ERR", msg))


class ConsolePanel:
    UNITY_BG = rl.Color(32, 32, 32, 255)
    UNITY_TEXT = rl.Color(200, 200, 200, 255)
    UNITY_BORDER = rl.Color(25, 25, 25, 255)

    INFO = "INFO"
    WARNING = "WARN"
    ERROR = "ERR"

    def __init__(self) -> None:
        self.scroll_offset: float = 0
        self.show_info = True
        self.show_warn = True
        self.show_err = True
        log_info("Console initialized.")

    def clear(self) -> None:
        GLOBAL_LOGS.clear()

    def render(self, x: int, y: int, width: int, height: int) -> None:
        """Renderiza la consola dentro del rectángulo de contenido inferior."""
        toolbar_y = y
        toolbar_h = 24
        rl.draw_rectangle(x, toolbar_y, width, toolbar_h, rl.Color(56, 56, 56, 255))
        rl.draw_line(x, toolbar_y + toolbar_h - 1, x + width, toolbar_y + toolbar_h - 1, self.UNITY_BORDER)

        if rl.gui_button(rl.Rectangle(x + 5, toolbar_y + 2, 50, 20), "Clear"):
            self.clear()

        fx = x + 60
        self.show_info = rl.gui_toggle(rl.Rectangle(fx, toolbar_y + 2, 60, 20), "Info", self.show_info)
        fx += 65
        self.show_warn = rl.gui_toggle(rl.Rectangle(fx, toolbar_y + 2, 60, 20), "Warn", self.show_warn)
        fx += 65
        self.show_err = rl.gui_toggle(rl.Rectangle(fx, toolbar_y + 2, 60, 20), "Error", self.show_err)

        content_y_start = toolbar_y + toolbar_h
        content_h = max(0, height - toolbar_h)
        rl.begin_scissor_mode(x, content_y_start, width, content_h)

        filtered_logs = [
            item
            for item in GLOBAL_LOGS
            if (item[0] == self.INFO and self.show_info)
            or (item[0] == self.WARNING and self.show_warn)
            or (item[0] == self.ERROR and self.show_err)
        ]

        curr_y = content_y_start + 5
        line_height = 18
        mouse_pos = rl.get_mouse_position()
        if rl.check_collision_point_rec(mouse_pos, rl.Rectangle(x, content_y_start, width, content_h)):
            self.scroll_offset -= rl.get_mouse_wheel_move() * 20
            self.scroll_offset = max(0, self.scroll_offset)

        curr_y -= int(self.scroll_offset)
        for index, (ltype, msg) in enumerate(filtered_logs):
            if curr_y + line_height < content_y_start:
                curr_y += line_height
                continue
            if curr_y > y + height:
                break

            color = self.UNITY_TEXT
            if ltype == self.WARNING:
                color = rl.YELLOW
            elif ltype == self.ERROR:
                color = rl.RED

            if index % 2 == 0:
                rl.draw_rectangle(x, curr_y, width, line_height, rl.Color(0, 0, 0, 20))

            icon = "(!)" if ltype == self.ERROR else ("/!\\") if ltype == self.WARNING else "(i)"
            rl.draw_text(icon, x + 10, curr_y + 4, 10, color)
            rl.draw_text(msg, x + 40, curr_y + 4, 10, self.UNITY_TEXT)
            rl.draw_line(x, curr_y + line_height - 1, x + width, curr_y + line_height - 1, rl.Color(45, 45, 45, 255))
            curr_y += line_height

        rl.end_scissor_mode()
