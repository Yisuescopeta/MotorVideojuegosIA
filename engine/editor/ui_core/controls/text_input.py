"""Pure serializable text input model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from engine.editor.ui_core.controls.control import Control
from engine.editor.ui_core.controls.events import Anchor, Margin, Size


@dataclass
class TextInput(Control):
    """Serializable editor text input state with pure editing commands."""

    text: str = ""
    placeholder: str = ""
    cursor: int = 0
    selection_anchor: int | None = None
    max_length: int | None = None
    multiline: bool = False
    password: bool = False
    readonly: bool = False
    font_size: int = 12
    padding_x: float = 6.0
    padding_y: float = 4.0
    undo_stack: list[tuple[str, int, int | None]] = field(default_factory=list)
    redo_stack: list[tuple[str, int, int | None]] = field(default_factory=list)
    schema_version: int = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        self.text = str(self.text)
        self.cursor = max(0, min(int(self.cursor), len(self.text)))
        if self.selection_anchor is not None:
            self.selection_anchor = max(0, min(int(self.selection_anchor), len(self.text)))

    @property
    def has_selection(self) -> bool:
        return self.selection_anchor is not None and self.selection_anchor != self.cursor

    @property
    def selection_range(self) -> tuple[int, int]:
        if self.selection_anchor is None:
            return (self.cursor, self.cursor)
        return (min(self.selection_anchor, self.cursor), max(self.selection_anchor, self.cursor))

    @property
    def display_text(self) -> str:
        return "*" * len(self.text) if self.password else self.text

    def measure(self, available: Size) -> Size:
        """Return desired size from text content, padding, and min size."""

        del available
        lines = self.text.splitlines() or [self.placeholder or ""]
        width = max((len(line) for line in lines), default=0) * self.font_size * 0.55 + self.padding_x * 2
        height = max(1, len(lines) if self.multiline else 1) * self.font_size * 1.35 + self.padding_y * 2
        if self.custom_min_size is not None:
            width = max(width, self.custom_min_size.width)
            height = max(height, self.custom_min_size.height)
        return Size(width + self.margin.horizontal, height + self.margin.vertical)

    def set_text(self, value: str) -> None:
        """Replace text while honoring max length and undo history."""

        value = str(value)
        if self.max_length is not None:
            value = value[: max(0, self.max_length)]
        if value == self.text:
            return
        self._push_undo()
        self.text = value
        self.cursor = min(self.cursor, len(self.text))
        self.clear_selection()

    def select_all(self) -> None:
        self.selection_anchor = 0
        self.cursor = len(self.text)

    def clear_selection(self) -> None:
        self.selection_anchor = None

    def move_cursor(self, delta: int, selecting: bool = False) -> None:
        if selecting and self.selection_anchor is None:
            self.selection_anchor = self.cursor
        if not selecting:
            self.clear_selection()
        self.cursor = max(0, min(len(self.text), self.cursor + int(delta)))

    def set_cursor(self, index: int, selecting: bool = False) -> None:
        if selecting and self.selection_anchor is None:
            self.selection_anchor = self.cursor
        if not selecting:
            self.clear_selection()
        self.cursor = max(0, min(len(self.text), int(index)))

    def insert_text(self, value: str) -> bool:
        """Insert text at cursor or replace selection."""

        if self.readonly:
            return False
        value = str(value)
        if not self.multiline:
            value = value.replace("\r", "").replace("\n", "")
        if not value:
            return False
        start, end = self.selection_range
        available = None if self.max_length is None else max(0, self.max_length - (len(self.text) - (end - start)))
        if available is not None:
            value = value[:available]
        if not value:
            return False
        self._push_undo()
        self.text = self.text[:start] + value + self.text[end:]
        self.cursor = start + len(value)
        self.clear_selection()
        return True

    def backspace(self) -> bool:
        if self.readonly:
            return False
        if self.has_selection:
            return self.delete_selection()
        if self.cursor <= 0:
            return False
        self._push_undo()
        self.text = self.text[: self.cursor - 1] + self.text[self.cursor :]
        self.cursor -= 1
        return True

    def delete_forward(self) -> bool:
        if self.readonly:
            return False
        if self.has_selection:
            return self.delete_selection()
        if self.cursor >= len(self.text):
            return False
        self._push_undo()
        self.text = self.text[: self.cursor] + self.text[self.cursor + 1 :]
        return True

    def delete_selection(self) -> bool:
        if self.readonly:
            return False
        start, end = self.selection_range
        if start == end:
            return False
        self._push_undo()
        self.text = self.text[:start] + self.text[end:]
        self.cursor = start
        self.clear_selection()
        return True

    def copy_selection(self) -> str:
        start, end = self.selection_range
        return self.text[start:end]

    def cut_selection(self) -> str:
        value = self.copy_selection()
        if value:
            self.delete_selection()
        return value

    def paste_text(self, value: str) -> bool:
        return self.insert_text(value)

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        self.redo_stack.append(self._snapshot())
        self._restore(self.undo_stack.pop())
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        self.undo_stack.append(self._snapshot())
        self._restore(self.redo_stack.pop())
        return True

    def handle_command(self, command: str, text: str = "", selecting: bool = False) -> bool:
        """Apply a named text/navigation command."""

        if command == "insert":
            return self.insert_text(text)
        if command == "backspace":
            return self.backspace()
        if command == "delete":
            return self.delete_forward()
        if command == "undo":
            return self.undo()
        if command == "redo":
            return self.redo()
        if command == "paste":
            return self.paste_text(text)
        if command == "cut":
            return bool(self.cut_selection())
        if command == "copy":
            return bool(self.copy_selection())
        if command == "left":
            self.move_cursor(-1, selecting=selecting)
            return True
        if command == "right":
            self.move_cursor(1, selecting=selecting)
            return True
        if command == "home":
            self.set_cursor(0, selecting=selecting)
            return True
        if command == "end":
            self.set_cursor(len(self.text), selecting=selecting)
            return True
        if command == "select_all":
            self.select_all()
            return True
        return False

    def to_dict(self) -> dict[str, object]:
        """Serialize state to JSON-compatible primitives."""

        data = asdict(self)
        data.pop("parent", None)
        data.pop("children", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "TextInput":
        """Build text input state from a `to_dict()` payload."""

        payload: dict[str, Any] = dict(data)
        payload.pop("parent", None)
        payload.pop("children", None)
        payload["anchor"] = _anchor_from_payload(payload.get("anchor"))
        payload["margin"] = _margin_from_payload(payload.get("margin"))
        payload["custom_min_size"] = _size_from_payload(payload.get("custom_min_size"))
        payload["undo_stack"] = [_snapshot_from_payload(item) for item in payload.get("undo_stack", [])]
        payload["redo_stack"] = [_snapshot_from_payload(item) for item in payload.get("redo_stack", [])]
        return cls(**payload)

    def _snapshot(self) -> tuple[str, int, int | None]:
        return (self.text, self.cursor, self.selection_anchor)

    def _push_undo(self) -> None:
        self.undo_stack.append(self._snapshot())
        self.redo_stack.clear()

    def _restore(self, snapshot: tuple[str, int, int | None]) -> None:
        text, cursor, anchor = snapshot
        self.text = text
        self.cursor = max(0, min(cursor, len(self.text)))
        self.selection_anchor = None if anchor is None else max(0, min(anchor, len(self.text)))


def _anchor_from_payload(value: object) -> Anchor:
    if isinstance(value, dict):
        return Anchor(
            left=float(value.get("left", 0.0)),
            top=float(value.get("top", 0.0)),
            right=float(value.get("right", 0.0)),
            bottom=float(value.get("bottom", 0.0)),
        )
    if isinstance(value, Anchor):
        return value
    return Anchor()


def _margin_from_payload(value: object) -> Margin:
    if isinstance(value, dict):
        return Margin(
            left=float(value.get("left", 0.0)),
            top=float(value.get("top", 0.0)),
            right=float(value.get("right", 0.0)),
            bottom=float(value.get("bottom", 0.0)),
        )
    if isinstance(value, Margin):
        return value
    return Margin()


def _size_from_payload(value: object) -> Size | None:
    if value is None or isinstance(value, Size):
        return value
    if isinstance(value, dict):
        return Size(width=float(value.get("width", 0.0)), height=float(value.get("height", 0.0)))
    return None


def _snapshot_from_payload(value: object) -> tuple[str, int, int | None]:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        anchor = value[2]
        return (str(value[0]), int(value[1]), None if anchor is None else int(anchor))
    return ("", 0, None)
