from __future__ import annotations

import math
from contextlib import contextmanager
from typing import Iterator

import pyray as rl


def _safe_dimension(reader_name: str) -> int:
    reader = getattr(rl, reader_name, None)
    if reader is None:
        return 0
    try:
        return max(0, int(reader()))
    except Exception:
        return 0


def logical_rect_to_scissor_rect(rect: rl.Rectangle) -> tuple[int, int, int, int] | None:
    width = float(rect.width)
    height = float(rect.height)
    if width <= 0 or height <= 0:
        return None

    screen_width = _safe_dimension("get_screen_width")
    screen_height = _safe_dimension("get_screen_height")
    render_width = _safe_dimension("get_render_width") or screen_width
    render_height = _safe_dimension("get_render_height") or screen_height

    scale_x = float(render_width) / float(screen_width) if screen_width > 0 else 1.0
    scale_y = float(render_height) / float(screen_height) if screen_height > 0 else 1.0

    left = int(math.floor(float(rect.x) * scale_x))
    top = int(math.floor(float(rect.y) * scale_y))
    right = int(math.ceil((float(rect.x) + width) * scale_x))
    bottom = int(math.ceil((float(rect.y) + height) * scale_y))

    if render_width > 0:
        left = max(0, min(left, render_width))
        right = max(left, min(right, render_width))
    if render_height > 0:
        top = max(0, min(top, render_height))
        bottom = max(top, min(bottom, render_height))

    scissor_width = max(0, right - left)
    scissor_height = max(0, bottom - top)
    if scissor_width <= 0 or scissor_height <= 0:
        return None
    return left, top, scissor_width, scissor_height


@contextmanager
def editor_scissor(rect: rl.Rectangle) -> Iterator[bool]:
    scissor = logical_rect_to_scissor_rect(rect)
    if scissor is None:
        yield False
        return
    rl.begin_scissor_mode(*scissor)
    try:
        yield True
    finally:
        rl.end_scissor_mode()


def safe_reset_clip_state() -> None:
    is_window_ready = getattr(rl, "is_window_ready", None)
    if callable(is_window_ready):
        try:
            if not bool(is_window_ready()):
                return
        except Exception:
            return
    try:
        rl.end_scissor_mode()
    except Exception:
        pass


def gui_toggle_bool(rect: rl.Rectangle, label: str, current: bool) -> bool:
    """RayGUI toggle helper for pyray builds that expect a mutable bool*."""
    state = rl.ffi.new("bool *", bool(current))
    rl.gui_toggle(rect, label, state)
    return bool(state[0])
