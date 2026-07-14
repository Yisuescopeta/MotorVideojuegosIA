from __future__ import annotations

import copy
from typing import Any

from engine.core.runtime_logging import log_err
from engine.scenes.edit_sync import SceneEditSyncCoordinator, SceneEditSyncSnapshot
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.workspace_lifecycle import (
    SceneSelectionSnapshot,
    SceneWorkspace,
    SceneWorkspaceEntry,
)


class _MutationState:
    def __init__(
        self,
        *,
        scene_data: dict[str, Any],
        selection: SceneSelectionSnapshot,
        dirty: bool,
        edit_sync_snapshot: SceneEditSyncSnapshot,
    ) -> None:
        self.scene_data = scene_data
        self.selection = selection
        self.dirty = dirty
        self.edit_sync_snapshot = edit_sync_snapshot


class SerializableMutationCoordinator:
    """Owns capture, commit, and semantic rollback for serializable mutations."""

    def __init__(
        self,
        workspace: SceneWorkspace,
        projection: SceneProjectionService,
        edit_sync: SceneEditSyncCoordinator,
    ) -> None:
        self._workspace = workspace
        self._projection = projection
        self._edit_sync = edit_sync

    def capture_snapshot(self, entry: SceneWorkspaceEntry) -> object:
        return _MutationState(
            scene_data=copy.deepcopy(entry.scene.to_dict()),
            selection=self._workspace.capture_selection(entry),
            dirty=entry.dirty,
            edit_sync_snapshot=self._edit_sync.capture_snapshot(entry),
        )

    def snapshot_scene_data(self, snapshot: object) -> dict[str, Any]:
        return copy.deepcopy(self._state(snapshot).scene_data)

    def restore_snapshot(
        self,
        entry: SceneWorkspaceEntry,
        snapshot: object,
    ) -> None:
        state = self._state(snapshot)
        self._install_payload(
            entry,
            state.scene_data,
            selection=state.selection,
        )
        self._workspace.restore_dirty(entry, state.dirty)
        self._edit_sync.restore_snapshot(entry, state.edit_sync_snapshot)

    def commit_mutation(
        self,
        entry: SceneWorkspaceEntry,
        snapshot: object,
        *,
        failure_context: str,
    ) -> bool:
        self._state(snapshot)
        selection = self._workspace.capture_selection(entry)
        try:
            self._install_payload(
                entry,
                entry.scene.to_dict(),
                selection=selection,
            )
        except ValueError as exc:
            self.restore_snapshot(entry, snapshot)
            log_err(f"SceneManager: rejected invalid serializable mutation during {failure_context}: {exc}")
            return False
        self._edit_sync.clear_pending(entry)
        return True

    def commit_incremental_entity_mutation(
        self,
        entry: SceneWorkspaceEntry,
        snapshot: object,
        *,
        failure_context: str,
    ) -> bool:
        """Validate and publish an in-place Scene/World entity mutation."""
        self._state(snapshot)
        if entry.edit_world is None:
            self.restore_snapshot(entry, snapshot)
            return False
        try:
            self._projection.validate_payload(entry.scene.to_dict())
            self._edit_sync.clear_pending(entry)
            self._workspace.install_entry_state(
                entry,
                entry.scene,
                entry.edit_world,
            )
        except Exception as exc:
            self.restore_snapshot(entry, snapshot)
            log_err(f"SceneManager: rejected incremental entity mutation during {failure_context}: {exc}")
            return False
        return True

    def _install_payload(
        self,
        entry: SceneWorkspaceEntry,
        data: dict[str, Any],
        *,
        selection: SceneSelectionSnapshot,
    ) -> None:
        source_path = entry.scene.source_path
        fallback_name = entry.scene.name
        prepared = self._workspace.prepare_scene_payload(data)
        scene = self._projection.create_scene(
            prepared,
            source_path=source_path,
            fallback_name=fallback_name,
        )
        self._workspace.sync_scene_links_from_feature_metadata(scene)
        world = self._projection.create_world(scene)
        self._workspace.install_entry_state(entry, scene, world)
        self._workspace.restore_selection(entry, selection)

    @staticmethod
    def _state(snapshot: object) -> _MutationState:
        if not isinstance(snapshot, _MutationState):
            raise TypeError("snapshot was not created by SerializableMutationCoordinator")
        return snapshot
