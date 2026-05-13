"""Editor scroll area primitive."""

from __future__ import annotations

from dataclasses import dataclass

from engine.editor.ui import input as ui_input
from engine.editor.ui.draw import draw_rounded_rect
from engine.editor.ui.geometry import Rect
from engine.editor.ui.theme import UNITY_DARK, EditorTheme
from engine.editor.ui.tokens import PANEL_RADIUS


@dataclass
class EditorScrollResult:
    """Result from one vertical editor scroll area draw."""

    rect: Rect
    content_rect: Rect
    content_height: float
    viewport_height: float
    scroll_offset_y: float
    max_scroll_y: float
    changed: bool = False
    hovered: bool = False
    wheel_delta: float = 0.0
    track_rect: Rect | None = None
    thumb_rect: Rect | None = None


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(float(value), max_value))


def editor_scroll_area(
    rect: Rect,
    content_height: float,
    scroll_offset_y: float,
    *,
    wheel_step: float = 32.0,
    scrollbar_width: float = 8.0,
    min_thumb_height: float = 24.0,
    theme: EditorTheme = UNITY_DARK,
) -> EditorScrollResult:
    """Draw vertical scroll track/thumb and return clamped offset."""

    x, y, w, h = rect
    viewport_height = max(0.0, float(h))
    content_height = max(0.0, float(content_height))
    max_scroll = max(0.0, content_height - viewport_height)
    original_offset = float(scroll_offset_y)
    offset = _clamp(original_offset, 0.0, max_scroll)
    hovered = ui_input.is_hovered(rect)
    wheel = ui_input.wheel_delta() if hovered else 0.0
    if wheel:
        offset = _clamp(offset - wheel * wheel_step, 0.0, max_scroll)

    track_rect: Rect | None = None
    thumb_rect: Rect | None = None
    if max_scroll > 0.0 and scrollbar_width > 0.0:
        track_rect = (x + max(0.0, w - scrollbar_width), y, scrollbar_width, viewport_height)
        ratio = viewport_height / max(content_height, 1.0)
        thumb_h = min(viewport_height, max(min_thumb_height, viewport_height * ratio))
        travel = max(0.0, viewport_height - thumb_h)
        thumb_y = y + (offset / max_scroll) * travel if max_scroll else y
        thumb_rect = (track_rect[0], thumb_y, scrollbar_width, thumb_h)

        if ui_input.is_pressed(track_rect):
            _mx, my = ui_input.mouse_position()
            center_y = _clamp(my - y - thumb_h / 2, 0.0, travel)
            offset = _clamp((center_y / max(travel, 1.0)) * max_scroll, 0.0, max_scroll)
            thumb_rect = (track_rect[0], y + center_y, scrollbar_width, thumb_h)

        draw_rounded_rect(track_rect, theme.raygui_dark, PANEL_RADIUS)
        draw_rounded_rect(thumb_rect, theme.button_hover if ui_input.is_hovered(thumb_rect) else theme.border_hover, PANEL_RADIUS)

    content_w = max(0.0, w - (scrollbar_width if max_scroll > 0.0 else 0.0))
    return EditorScrollResult(
        rect=rect,
        content_rect=(x, y, content_w, viewport_height),
        content_height=content_height,
        viewport_height=viewport_height,
        scroll_offset_y=offset,
        max_scroll_y=max_scroll,
        changed=abs(offset - original_offset) > 0.000001,
        hovered=hovered,
        wheel_delta=wheel,
        track_rect=track_rect,
        thumb_rect=thumb_rect,
    )
