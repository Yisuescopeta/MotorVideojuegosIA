from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from engine.core.runtime_logging import log_err
from engine.scenes.edit_sync import SceneEditSyncCoordinator, SceneEditSyncSnapshot
from engine.scenes.projection_integrity import ProjectionIntegrityEvidence
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.workspace_lifecycle import (
    SceneSelectionSnapshot,
    SceneWorkspace,
    SceneWorkspaceEntry,
)

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.scenes.scene import Scene


class _MutationState:
    def __init__(
        self,
        *,
        scene: Scene,
        world: World,
        selection: SceneSelectionSnapshot,
        dirty: bool,
        edit_sync_snapshot: SceneEditSyncSnapshot,
        scene_revision: int,
        projection_integrity_evidence: ProjectionIntegrityEvidence | None,
    ) -> None:
        self.scene = scene
        self.world = world
        self.selection = selection
        self.dirty = dirty
        self.edit_sync_snapshot = edit_sync_snapshot
        self.scene_revision = scene_revision
        self.projection_integrity_evidence = projection_integrity_evidence


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

    def capture_snapshot(
        self,
        entry: SceneWorkspaceEntry,
        *,
        clone_world: bool = False,
    ) -> object:
        if entry.edit_world is None:
            raise ValueError("serializable mutation requires an edit world")
        source_path = entry.scene.source_path
        fallback_name = entry.scene.name
        snapshot_data = entry.scene.to_snapshot_dict()
        prepared = self._workspace.prepare_scene_payload(copy.deepcopy(snapshot_data))
        scene = self._projection.create_scene(
            prepared,
            source_path=source_path,
            fallback_name=fallback_name,
        )
        self._workspace.sync_scene_links_from_feature_metadata(scene)
        scene.restore_empty_prefab_override_shapes(snapshot_data)
        return _MutationState(
            scene=scene,
            world=entry.edit_world.clone() if clone_world else entry.edit_world,
            selection=self._workspace.capture_selection(entry),
            dirty=entry.dirty,
            edit_sync_snapshot=self._edit_sync.capture_snapshot(entry),
            scene_revision=entry.scene_revision,
            projection_integrity_evidence=entry.projection_integrity_evidence,
        )

    def snapshot_scene_data(self, snapshot: object) -> dict[str, Any]:
        return self._state(snapshot).scene.to_snapshot_dict()

    def snapshot_entry_scene_data(self, entry: SceneWorkspaceEntry) -> dict[str, Any]:
        """Return a defensive scene snapshot for history boundaries."""
        return entry.scene.to_snapshot_dict()

    def restore_scene_data(self, scene_key: str, data: dict[str, Any]) -> bool:
        """Restore one edit scene through workspace and pending-sync authorities."""
        entry = self._workspace.resolve_entry(scene_key)
        if entry is None or entry.is_playing:
            return False
        selection = self._workspace.capture_selection(entry)
        try:
            self._install_payload(
                entry,
                data,
                selection=selection,
            )
        except ValueError:
            return False
        self._edit_sync.clear_pending(entry)
        self._workspace.mark_dirty(entry)
        return True

    def restore_snapshot(
        self,
        entry: SceneWorkspaceEntry,
        snapshot: object,
    ) -> None:
        state = self._state(snapshot)
        self._workspace.restore_entry_state(
            entry,
            state.scene,
            state.world,
            scene_revision=state.scene_revision,
            projection_integrity_evidence=state.projection_integrity_evidence,
        )
        self._workspace.restore_selection(entry, state.selection)
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
                entry.scene.to_snapshot_dict(),
                selection=selection,
            )
        except Exception as exc:
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
            self._projection.validate_payload(entry.scene.to_snapshot_dict())
            self._edit_sync.clear_pending(entry)
            self._workspace.install_entry_state(
                entry,
                entry.scene,
                entry.edit_world,
                rebuild_projection=False,
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
        snapshot_data = copy.deepcopy(data)
        prepared = self._workspace.prepare_scene_payload(copy.deepcopy(snapshot_data))
        scene = self._projection.create_scene(
            prepared,
            source_path=source_path,
            fallback_name=fallback_name,
        )
        self._workspace.sync_scene_links_from_feature_metadata(scene)
        scene.restore_empty_prefab_override_shapes(snapshot_data)
        world = self._projection.create_world(scene)
        self._workspace.install_entry_state(entry, scene, world)
        self._workspace.restore_selection(entry, selection)

    @staticmethod
    def _state(snapshot: object) -> _MutationState:
        if not isinstance(snapshot, _MutationState):
            raise TypeError("snapshot was not created by SerializableMutationCoordinator")
        return snapshot
