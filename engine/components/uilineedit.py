"""
engine/components/uilineedit.py — LineEdit UI para entrada de texto (adaptado Godot LineEdit).
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


def _color_tuple(value: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    r, g, b, a = value
    return (int(r), int(g), int(b), int(a))


class LineEdit(Component):
    """Control de entrada de texto de una sola línea (adaptado Godot LineEdit)."""

    def __init__(
        self,
        enabled: bool = True,
        text: str = "",
        placeholder: str = "",
        max_length: int = 0,
        secret: bool = False,
        editable: bool = True,
        font_size: int = 16,
        color: tuple[int, int, int, int] = (255, 255, 255, 255),
        placeholder_color: tuple[int, int, int, int] = (128, 128, 128, 255),
        alignment: str = "left",
    ) -> None:
        self.enabled = enabled
        self.text = str(text)
        self.placeholder = str(placeholder)
        self.max_length = int(max_length)
        self.secret = bool(secret)
        self.editable = bool(editable)
        self.font_size = max(10, int(font_size))
        self.color = _color_tuple(color)
        self.placeholder_color = _color_tuple(placeholder_color)
        self.alignment = str(alignment or "left")
        # Runtime state (not serialized)
        self._focused: bool = False
        self._cursor_position: int = 0
        self._selection_start: int = 0
        self._selection_end: int = 0

    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        self._focused = bool(value)

    @property
    def cursor_position(self) -> int:
        return self._cursor_position

    @cursor_position.setter
    def cursor_position(self, value: int) -> None:
        self._cursor_position = max(0, min(len(self.text), int(value)))

    @property
    def selection_start(self) -> int:
        return self._selection_start

    @selection_start.setter
    def selection_start(self, value: int) -> None:
        self._selection_start = max(0, min(len(self.text), int(value)))

    @property
    def selection_end(self) -> int:
        return self._selection_end

    @selection_end.setter
    def selection_end(self, value: int) -> None:
        self._selection_end = max(0, min(len(self.text), int(value)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "text": self.text,
            "placeholder": self.placeholder,
            "max_length": self.max_length,
            "secret": self.secret,
            "editable": self.editable,
            "font_size": self.font_size,
            "color": list(self.color),
            "placeholder_color": list(self.placeholder_color),
            "alignment": self.alignment,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LineEdit":
        return cls(
            enabled=data.get("enabled", True),
            text=data.get("text", ""),
            placeholder=data.get("placeholder", ""),
            max_length=data.get("max_length", 0),
            secret=data.get("secret", False),
            editable=data.get("editable", True),
            font_size=data.get("font_size", 16),
            color=tuple(data.get("color", [255, 255, 255, 255])),  # type: ignore[arg-type]
            placeholder_color=tuple(data.get("placeholder_color", [128, 128, 128, 255])),  # type: ignore[arg-type]
            alignment=data.get("alignment", "left"),
        )
