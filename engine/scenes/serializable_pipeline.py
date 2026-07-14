from __future__ import annotations

from typing import Any

from engine.scenes.contracts import SceneHistoryPort
from engine.scenes.edit_sync import SceneEditSyncCoordinator
from engine.scenes.serializable_mutation import SerializableMutationCoordinator
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry


class SceneSerializableAuthoringPipeline:
    """Single transaction boundary shared by serializable authoring owners."""

    def __init__(
        self,
        workspace: SceneWorkspace,
        edit_sync: SceneEditSyncCoordinator,
        mutations: SerializableMutationCoordinator,
        history: SceneHistoryPort,
    ) -> None:
        self._workspace = workspace
        self._edit_sync = edit_sync
        self._mutations = mutations
        self._history = history

    def flush_pending(
        self,
        entry: SceneWorkspaceEntry,
        *,
        failure_context: str,
    ) -> bool:
        return self._edit_sync.flush_pending(
            entry,
            failure_context=failure_context,
        )

    def begin(
        self,
        entry: SceneWorkspaceEntry,
        *,
        failure_context: str,
    ) -> tuple[object, dict[str, Any]] | None:
        if entry.is_playing or not self.flush_pending(
            entry,
            failure_context=failure_context,
        ):
            return None
        token = self._mutations.capture_snapshot(entry)
        return token, self._mutations.snapshot_scene_data(token)

    def rollback(
        self,
        entry: SceneWorkspaceEntry,
        token: object,
    ) -> None:
        self._mutations.restore_snapshot(entry, token)

    def commit_snapshot(
        self,
        entry: SceneWorkspaceEntry,
        token: object,
        before: dict[str, Any],
        *,
        label: str,
        record_history: bool = True,
    ) -> bool:
        if not self._mutations.commit_mutation(
            entry,
            token,
            failure_context=label,
        ):
            return False
        self._workspace.mark_dirty(entry)
        if record_history:
            self._history.record_scene_change(entry, label, before)
        return True

    def commit_incremental(
        self,
        entry: SceneWorkspaceEntry,
        token: object,
        *,
        failure_context: str,
    ) -> bool:
        if not self._mutations.commit_incremental_entity_mutation(
            entry,
            token,
            failure_context=failure_context,
        ):
            return False
        self._workspace.mark_dirty(entry)
        return True
