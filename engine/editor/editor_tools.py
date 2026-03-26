from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EditorTool(Enum):
    HAND = "Hand"
    MOVE = "Move"
    ROTATE = "Rotate"
    SCALE = "Scale"
    TRANSFORM = "Transform"
    RECT = "Rect"

    @classmethod
    def from_value(cls, value: Any) -> "EditorTool":
        if isinstance(value, cls):
            return value
        text = str(value or "").strip().lower()
        for item in cls:
            if item.value.lower() == text:
                return item
        return cls.MOVE


class TransformSpace(Enum):
    WORLD = "world"
    LOCAL = "local"

    @classmethod
    def from_value(cls, value: Any) -> "TransformSpace":
        if isinstance(value, cls):
            return value
        return cls.LOCAL if str(value or "").strip().lower() == cls.LOCAL.value else cls.WORLD


class PivotMode(Enum):
    PIVOT = "pivot"
    CENTER = "center"

    @classmethod
    def from_value(cls, value: Any) -> "PivotMode":
        if isinstance(value, cls):
            return value
        return cls.CENTER if str(value or "").strip().lower() == cls.CENTER.value else cls.PIVOT


@dataclass
class SnapSettings:
    move_step: float = 10.0
    rotate_step: float = 15.0
    scale_step: float = 0.1

    @classmethod
    def from_preferences(cls, preferences: dict[str, Any]) -> "SnapSettings":
        return cls(
            move_step=float(preferences.get("editor_snap_move_step", 10.0)),
            rotate_step=float(preferences.get("editor_snap_rotate_step", 15.0)),
            scale_step=float(preferences.get("editor_snap_scale_step", 0.1)),
        )

    def to_preferences(self) -> dict[str, float]:
        return {
            "editor_snap_move_step": float(self.move_step),
            "editor_snap_rotate_step": float(self.rotate_step),
            "editor_snap_scale_step": float(self.scale_step),
        }
