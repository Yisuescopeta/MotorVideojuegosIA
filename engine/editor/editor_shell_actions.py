"""Narrow typed action channel for editor shell scene-tab interactions."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum


class SceneTabActionKind(str, Enum):
    ACTIVATE = "ACTIVATE"
    CLOSE = "CLOSE"


@dataclass(frozen=True, slots=True)
class SceneTabAction:
    kind: SceneTabActionKind
    scene_key: str


class EditorShellActionInbox:
    """One-purpose inbox; it carries only scene-tab actions."""

    def __init__(self) -> None:
        self._scene_tab_actions: deque[SceneTabAction] = deque()

    def activate_scene_tab(self, scene_key: str) -> None:
        self._append(SceneTabActionKind.ACTIVATE, scene_key)

    def close_scene_tab(self, scene_key: str) -> None:
        self._append(SceneTabActionKind.CLOSE, scene_key)

    def drain_scene_tab_actions(self) -> tuple[SceneTabAction, ...]:
        actions = tuple(self._scene_tab_actions)
        self._scene_tab_actions.clear()
        return actions

    def _append(self, kind: SceneTabActionKind, scene_key: str) -> None:
        normalized = str(scene_key or "").strip()
        if normalized:
            self._scene_tab_actions.append(SceneTabAction(kind, normalized))


__all__ = ["EditorShellActionInbox", "SceneTabAction", "SceneTabActionKind"]
