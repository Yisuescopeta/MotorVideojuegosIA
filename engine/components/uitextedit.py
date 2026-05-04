"""
engine/components/uitextedit.py — TextEdit multilínea (adaptado Godot TextEdit).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class TextEdit(Component):
    """Editor de texto multilinea (adaptado Godot TextEdit)."""

    def __init__(
        self,
        enabled: bool = True,
        text: str = "",
        font_size: int = 14,
        editable: bool = True,
        line_numbers: bool = False,
        word_wrap: bool = True,
        max_lines: int = 0,
    ) -> None:
        self.enabled = enabled
        self.text = str(text)
        self.font_size = max(10, int(font_size))
        self.editable = bool(editable)
        self.line_numbers = bool(line_numbers)
        self.word_wrap = bool(word_wrap)
        self.max_lines = int(max_lines)
        # Runtime state (not serialized)
        self._focused: bool = False
        self._cursor_line: int = 0
        self._cursor_column: int = 0
        self._scroll_y: float = 0.0

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = bool(value)

    @property
    def cursor_line(self) -> int:
        return self._cursor_line

    @cursor_line.setter
    def cursor_line(self, value: int) -> None:
        self._cursor_line = max(0, int(value))

    @property
    def cursor_column(self) -> int:
        return self._cursor_column

    @cursor_column.setter
    def cursor_column(self, value: int) -> None:
        self._cursor_column = max(0, int(value))

    @property
    def scroll_y(self) -> float:
        return self._scroll_y

    @scroll_y.setter
    def scroll_y(self, value: float) -> None:
        self._scroll_y = max(0.0, float(value))

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "text": self.text,
            "font_size": self.font_size,
            "editable": self.editable,
            "line_numbers": self.line_numbers,
            "word_wrap": self.word_wrap,
            "max_lines": self.max_lines,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TextEdit":
        return cls(
            enabled=data.get("enabled", True),
            text=data.get("text", ""),
            font_size=data.get("font_size", 14),
            editable=data.get("editable", True),
            line_numbers=data.get("line_numbers", False),
            word_wrap=data.get("word_wrap", True),
            max_lines=data.get("max_lines", 0),
        )
