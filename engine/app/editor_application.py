"""Application-owned editor composition and capability wiring."""

from __future__ import annotations

from engine.editor.editor_preview_coordinator import EditorPreviewCoordinator
from engine.editor.editor_session import EditorSession
from engine.editor.transform_preview import TransformPreviewCommands, TransformPreviewCoordinator
from engine.scenes.scene_manager import SceneManager


class EditorApplication:
    """Own the editor lifecycle authorities and expose narrow tool capabilities."""

    def __init__(self, scene_manager: SceneManager, game: "Game | None" = None) -> None:
        self.scene_manager = scene_manager
        self.editor_session = EditorSession()
        self.preview_coordinator = EditorPreviewCoordinator(
            scene_manager.create_preview_lease_registry()
        )
        scene_manager.set_preview_coordinator(self.preview_coordinator)
        self.transform_preview_commands: TransformPreviewCommands = TransformPreviewCoordinator(
            scene_manager.workspace_port,
            self.preview_coordinator,
            scene_manager.apply_transform_preview,
        )
        if game is not None:
            game.set_editor_session(self.editor_session)
            game.set_transform_preview_commands(self.transform_preview_commands)


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.core.game import Game


__all__ = ["EditorApplication"]
