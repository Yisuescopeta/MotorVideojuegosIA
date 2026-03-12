"""
engine/editor/undo_redo.py - Historial simple de authoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List


@dataclass
class UndoRedoOperation:
    label: str
    undo: Callable[[], None]
    redo: Callable[[], None]


class UndoRedoManager:
    """Historial de operaciones serializables aplicadas desde editor o servicios."""

    def __init__(self) -> None:
        self._undo_stack: List[UndoRedoOperation] = []
        self._redo_stack: List[UndoRedoOperation] = []

    def push(self, label: str, undo: Callable[[], None], redo: Callable[[], None]) -> None:
        self._undo_stack.append(UndoRedoOperation(label=label, undo=undo, redo=redo))
        self._redo_stack.clear()

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        operation = self._undo_stack.pop()
        operation.undo()
        self._redo_stack.append(operation)
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        operation = self._redo_stack.pop()
        operation.redo()
        self._undo_stack.append(operation)
        return True

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
