"""Single authority for editor selection and session-level UI state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from engine.scenes.refs import EntityRef, OpenSceneRef
from engine.scenes.result import CommandError, CommandErrorCode, Err, Ok, Result


class EditorMode(str, Enum):
    EDIT = "EDIT"
    PLAY = "PLAY"


@dataclass(frozen=True, slots=True)
class EditorSessionSnapshot:
    active_scene: OpenSceneRef | None
    selection: EntityRef | None
    mode: EditorMode
    active_tab: str
    revision: int


class EditorSession:
    """Owns one active scene, one selection, mode and active editor tab."""

    def __init__(self, *, active_tab: str = "SCENE") -> None:
        self._active_scene: OpenSceneRef | None = None
        self._selection: EntityRef | None = None
        self._mode = EditorMode.EDIT
        self._active_tab = str(active_tab or "SCENE").strip() or "SCENE"
        self._revision = 0

    @property
    def snapshot(self) -> EditorSessionSnapshot:
        return EditorSessionSnapshot(
            active_scene=self._active_scene,
            selection=self._selection,
            mode=self._mode,
            active_tab=self._active_tab,
            revision=self._revision,
        )

    def activate_scene(self, scene: OpenSceneRef) -> EditorSessionSnapshot:
        if self._active_scene != scene:
            self._active_scene = scene
            if self._selection is not None and self._selection.scene != scene:
                self._selection = None
            self._bump()
        return self.snapshot

    def select(self, entity: EntityRef) -> Result[EditorSessionSnapshot]:
        if self._active_scene is None:
            return Err(
                CommandError(
                    CommandErrorCode.NOT_FOUND,
                    "Cannot select an entity without an active scene.",
                    field="active_scene",
                )
            )
        if entity.scene != self._active_scene:
            return Err(
                CommandError(
                    CommandErrorCode.VALIDATION_FAILED,
                    "Selected entity belongs to a different open scene.",
                    field="selection",
                )
            )
        if self._selection != entity:
            self._selection = entity
            self._bump()
        return Ok(self.snapshot)

    def clear_selection(self) -> EditorSessionSnapshot:
        if self._selection is not None:
            self._selection = None
            self._bump()
        return self.snapshot

    def set_mode(self, mode: EditorMode) -> EditorSessionSnapshot:
        normalized = EditorMode(mode)
        if self._mode != normalized:
            self._mode = normalized
            self._bump()
        return self.snapshot

    def activate_tab(self, tab: str) -> EditorSessionSnapshot:
        normalized = str(tab or "").strip()
        if not normalized:
            raise ValueError("Editor tab must be non-empty")
        if self._active_tab != normalized:
            self._active_tab = normalized
            self._bump()
        return self.snapshot

    def _bump(self) -> None:
        self._revision += 1


__all__ = ["EditorMode", "EditorSession", "EditorSessionSnapshot"]
