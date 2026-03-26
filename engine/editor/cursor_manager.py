from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import pyray as rl


class CursorVisualState(IntEnum):
    DEFAULT = 0
    INTERACTIVE = 1
    TEXT = 2


@dataclass(frozen=True)
class CursorPalette:
    outline: rl.Color
    frame: rl.Color
    fill: rl.Color
    core: rl.Color
    detail: rl.Color
    shadow: rl.Color


class CustomCursorRenderer:
    """Draws a square editor cursor with a warm accent palette."""

    SIZE: int = 16
    HOTSPOT_X: int = 8
    HOTSPOT_Y: int = 8

    DEFAULT_PALETTE = CursorPalette(
        outline=rl.Color(14, 16, 18, 240),
        frame=rl.Color(124, 126, 131, 255),
        fill=rl.Color(44, 46, 49, 235),
        core=rl.Color(191, 138, 69, 255),
        detail=rl.Color(230, 194, 132, 255),
        shadow=rl.Color(0, 0, 0, 78),
    )
    INTERACTIVE_PALETTE = CursorPalette(
        outline=rl.Color(12, 14, 16, 250),
        frame=rl.Color(167, 170, 176, 255),
        fill=rl.Color(50, 52, 56, 245),
        core=rl.Color(236, 176, 78, 255),
        detail=rl.Color(255, 220, 150, 255),
        shadow=rl.Color(0, 0, 0, 92),
    )
    TEXT_PALETTE = CursorPalette(
        outline=rl.Color(14, 16, 18, 245),
        frame=rl.Color(176, 178, 183, 255),
        fill=rl.Color(48, 50, 54, 240),
        core=rl.Color(233, 221, 190, 255),
        detail=rl.Color(255, 244, 216, 255),
        shadow=rl.Color(0, 0, 0, 88),
    )

    def hide_system_cursor(self) -> None:
        if not rl.is_cursor_hidden():
            rl.hide_cursor()

    def show_system_cursor(self) -> None:
        if rl.is_cursor_hidden():
            rl.show_cursor()

    def render(self, mouse_pos: rl.Vector2, state: CursorVisualState) -> None:
        palette = self._palette_for_state(state)
        x = int(mouse_pos.x) - self.HOTSPOT_X
        y = int(mouse_pos.y) - self.HOTSPOT_Y

        self._draw_shadow(x, y, palette.shadow)
        self._draw_frame(x, y, palette)
        self._draw_core(x, y, palette)

    def _palette_for_state(self, state: CursorVisualState) -> CursorPalette:
        if state == CursorVisualState.TEXT:
            return self.TEXT_PALETTE
        if state == CursorVisualState.INTERACTIVE:
            return self.INTERACTIVE_PALETTE
        return self.DEFAULT_PALETTE

    def _draw_shadow(self, x: int, y: int, color: rl.Color) -> None:
        rl.draw_rectangle(x + 2, y + 2, 12, 12, color)
        rl.draw_rectangle(x + 4, y + 1, 8, 1, color)
        rl.draw_rectangle(x + 1, y + 4, 1, 8, color)

    def _draw_frame(self, x: int, y: int, palette: CursorPalette) -> None:
        outline = palette.outline
        frame = palette.frame
        fill = palette.fill

        rl.draw_rectangle(x + 4, y + 0, 8, 1, outline)
        rl.draw_rectangle(x + 4, y + 15, 8, 1, outline)
        rl.draw_rectangle(x + 0, y + 4, 1, 8, outline)
        rl.draw_rectangle(x + 15, y + 4, 1, 8, outline)

        rl.draw_rectangle(x + 2, y + 2, 12, 12, outline)
        rl.draw_rectangle(x + 3, y + 3, 10, 10, frame)
        rl.draw_rectangle(x + 4, y + 4, 8, 8, fill)

        rl.draw_rectangle(x + 7, y + 1, 2, 2, frame)
        rl.draw_rectangle(x + 13, y + 7, 2, 2, frame)
        rl.draw_rectangle(x + 7, y + 13, 2, 2, frame)
        rl.draw_rectangle(x + 1, y + 7, 2, 2, frame)

    def _draw_core(self, x: int, y: int, palette: CursorPalette) -> None:
        rl.draw_rectangle(x + 6, y + 6, 4, 4, palette.core)
        rl.draw_rectangle(x + 7, y + 5, 2, 1, palette.detail)
        rl.draw_rectangle(x + 7, y + 10, 2, 1, palette.detail)
        rl.draw_rectangle(x + 5, y + 7, 1, 2, palette.detail)
        rl.draw_rectangle(x + 10, y + 7, 1, 2, palette.detail)
