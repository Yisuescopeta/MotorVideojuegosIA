"""Cursor visual state enum shared between editor and runtime."""
from enum import IntEnum


class CursorVisualState(IntEnum):
    DEFAULT = 0
    INTERACTIVE = 1
    TEXT = 2
