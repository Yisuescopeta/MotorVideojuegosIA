"""
engine/components/rich_text_label.py - RichTextLabel con BBCode-like formatting (adaptado Godot).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


def _color_tuple(value: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    r, g, b, a = value
    return (int(r), int(g), int(b), int(a))


class RichTextLabel(Component):
    """Godot RichTextLabel — text with BBCode-like formatting."""

    def __init__(
        self,
        enabled: bool = True,
        text: str = "",
        font_size: int = 14,
        default_color: tuple[int, int, int, int] = (255, 255, 255, 255),
        visible_characters: int = -1,
        percent_visible: float = 1.0,
        autowrap: bool = True,
        scroll_active: bool = True,
        selection_enabled: bool = False,
    ) -> None:
        self.enabled = enabled
        self.text = str(text)
        self.font_size = max(8, int(font_size))
        self.default_color = _color_tuple(default_color)
        self.visible_characters = int(visible_characters)
        self.percent_visible = max(0.0, min(1.0, float(percent_visible)))
        self.autowrap = bool(autowrap)
        self.scroll_active = bool(scroll_active)
        self.selection_enabled = bool(selection_enabled)
        # Runtime
        self._scroll_offset: float = 0.0
        self._max_scroll: float = 0.0

    def scroll_up(self, amount: float = 20.0) -> None:
        self._scroll_offset = max(0.0, self._scroll_offset - amount)

    def scroll_down(self, amount: float = 20.0) -> None:
        self._scroll_offset = min(max(0.0, self._max_scroll), self._scroll_offset + amount)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "text": self.text,
            "font_size": self.font_size,
            "default_color": list(self.default_color),
            "visible_characters": self.visible_characters,
            "percent_visible": self.percent_visible,
            "autowrap": self.autowrap,
            "scroll_active": self.scroll_active,
            "selection_enabled": self.selection_enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RichTextLabel":
        return cls(
            enabled=data.get("enabled", True),
            text=data.get("text", ""),
            font_size=data.get("font_size", 14),
            default_color=tuple(data.get("default_color", [255, 255, 255, 255])),  # type: ignore[arg-type]
            visible_characters=data.get("visible_characters", -1),
            percent_visible=data.get("percent_visible", 1.0),
            autowrap=data.get("autowrap", True),
            scroll_active=data.get("scroll_active", True),
            selection_enabled=data.get("selection_enabled", False),
        )
