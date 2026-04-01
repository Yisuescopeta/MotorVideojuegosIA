"""
engine/editor/console_panel.py - Panel de Consola estilo Unity
"""

from typing import List, Tuple

import pyray as rl

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

    def __init__(self) -> None:
        self.scroll_offset: float = 0.0
        self.show_info = True
        self.show_warn = True
        self.show_err = True
        self.panel_rect = rl.Rectangle(0, 0, 0, 0)
        self.toolbar_rect = rl.Rectangle(0, 0, 0, 0)
        self.body_rect = rl.Rectangle(0, 0, 0, 0)
        log_info("Console initialized.")

    def clear(self) -> None:
        GLOBAL_LOGS.clear()

    def render(self, x: int, y: int, width: int, height: int) -> None:
        """Renderiza la consola dentro del rectángulo de contenido inferior."""
        self.panel_rect = rl.Rectangle(float(x), float(y), float(max(0, width)), float(max(0, height)))
        toolbar_h = min(self.TOOLBAR_HEIGHT, max(0, height))
        self.toolbar_rect = rl.Rectangle(float(x), float(y), float(max(0, width)), float(toolbar_h))
        body_y = y + toolbar_h
        body_h = max(0, height - toolbar_h)
        self.body_rect = rl.Rectangle(float(x), float(body_y), float(max(0, width)), float(body_h))

        rl.draw_rectangle_rec(self.panel_rect, self.UNITY_BG)
        rl.draw_rectangle_rec(self.toolbar_rect, self.UNITY_HEADER)
        rl.draw_line(x, y + toolbar_h - 1, x + width, y + toolbar_h - 1, self.UNITY_BORDER)
        if self.body_rect.width > 0 and self.body_rect.height > 0:
            rl.draw_rectangle_rec(self.body_rect, self.UNITY_BODY)
            rl.draw_rectangle_lines_ex(self.body_rect, 1, self.UNITY_BORDER)

        if rl.gui_button(rl.Rectangle(float(x + 5), float(y + 2), 50.0, 20.0), "Clear"):
            self.clear()

        fx = x + 60
        self.show_info = rl.gui_toggle(rl.Rectangle(float(fx), float(y + 2), 60.0, 20.0), "Info", self.show_info)
        fx += 65
        self.show_warn = rl.gui_toggle(rl.Rectangle(float(fx), float(y + 2), 60.0, 20.0), "Warn", self.show_warn)
        fx += 65
        self.show_err = rl.gui_toggle(rl.Rectangle(float(fx), float(y + 2), 60.0, 20.0), "Error", self.show_err)

        if self.body_rect.width <= 0 or self.body_rect.height <= 0:
            return

        filtered_logs = [
            item
            for item in GLOBAL_LOGS
            if (item[0] == self.INFO and self.show_info)
            or (item[0] == self.WARNING and self.show_warn)
            or (item[0] == self.ERROR and self.show_err)
        ]

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

                if index % 2 == 0:
                    rl.draw_rectangle(int(self.body_rect.x), curr_y, int(self.body_rect.width), line_height, rl.Color(0, 0, 0, 20))

                icon = "(!)" if ltype == self.ERROR else ("/!\\") if ltype == self.WARNING else "(i)"
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
