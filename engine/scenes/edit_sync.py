from __future__ import annotations

from dataclasses import dataclass

from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry

LEGACY_AUTHORING_SYNC_REASON = "legacy_authoring"
TRANSIENT_PREVIEW_SYNC_REASON = "transient_preview"


@dataclass(frozen=True)
class SceneEditSyncSnapshot:
    """Opaque snapshot of pending edit-sync state."""

    _reason: str | None
    _dirty_before_pending: bool | None


class SceneEditSyncCoordinator:
    """Owns pending edit-world synchronization policy and state transitions."""

    def __init__(
        self,
        workspace: SceneWorkspace,
        projection: SceneProjectionService,
    ) -> None:
        self._workspace = workspace
        self._projection = projection

    @staticmethod
    def has_pending_legacy(entry: SceneWorkspaceEntry) -> bool:
        return entry.pending_edit_world_sync_reason == LEGACY_AUTHORING_SYNC_REASON

    @staticmethod
    def has_pending_transient(entry: SceneWorkspaceEntry) -> bool:
        return entry.pending_edit_world_sync_reason == TRANSIENT_PREVIEW_SYNC_REASON

    @staticmethod
    def capture_snapshot(entry: SceneWorkspaceEntry) -> SceneEditSyncSnapshot:
        return SceneEditSyncSnapshot(
            entry.pending_edit_world_sync_reason,
            entry.dirty_before_pending_edit_world_sync,
        )

    @staticmethod
    def restore_snapshot(
        entry: SceneWorkspaceEntry,
        snapshot: SceneEditSyncSnapshot,
    ) -> None:
        entry.pending_edit_world_sync_reason = snapshot._reason
        entry.dirty_before_pending_edit_world_sync = snapshot._dirty_before_pending

    @staticmethod
    def capture_pending_reason(entry: SceneWorkspaceEntry) -> str | None:
        return entry.pending_edit_world_sync_reason

    @staticmethod
    def restore_pending_reason(
        entry: SceneWorkspaceEntry,
        reason: str | None,
    ) -> None:
        entry.pending_edit_world_sync_reason = reason
        entry.dirty_before_pending_edit_world_sync = None

    @staticmethod
    def clear_pending(entry: SceneWorkspaceEntry) -> None:
        entry.pending_edit_world_sync_reason = None
        entry.dirty_before_pending_edit_world_sync = None

    def sync_from_edit_world(self, force: bool = False) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        if not force and not self.has_pending_legacy(entry):
            return False
        return self._sync_entry_from_edit_world(entry)

    def mark_edit_world_dirty(self, reason: str = LEGACY_AUTHORING_SYNC_REASON) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        if reason == TRANSIENT_PREVIEW_SYNC_REASON:
            if not self.has_pending_legacy(entry):
                entry.pending_edit_world_sync_reason = TRANSIENT_PREVIEW_SYNC_REASON
            return True
        if not self.has_pending_legacy(entry):
            entry.dirty_before_pending_edit_world_sync = entry.dirty
        self._workspace.mark_dirty(entry)
        entry.pending_edit_world_sync_reason = LEGACY_AUTHORING_SYNC_REASON
        return True

    def flush_pending(
        self,
        entry: SceneWorkspaceEntry,
        *,
        failure_context: str = "legacy_authoring_flush",
    ) -> bool:
        if not self.has_pending_legacy(entry) or entry.key != self._workspace.active_scene_key:
            return True
        return self._sync_or_reject(entry, failure_context=failure_context)

    def prepare_for_save(
        self,
        entry: SceneWorkspaceEntry,
        *,
        failure_context: str = "scene_save",
    ) -> bool:
        if entry.edit_world is None:
            return False
        if self.has_pending_transient(entry):
            self._workspace.rebuild_edit_world(entry)
            self.clear_pending(entry)
            return True
        if self.has_pending_legacy(entry):
            return self.flush_pending(entry, failure_context=failure_context)
        if entry.edit_world.version != entry.edit_world_version:
            if entry.is_playing:
                return True
            if not self._sync_or_reject(entry, failure_context=failure_context):
                return False
        return True

    def _sync_or_reject(
        self,
        entry: SceneWorkspaceEntry,
        *,
        failure_context: str,
    ) -> bool:
        try:
            return self._sync_entry_from_edit_world(entry)
        except ValueError as exc:
            return self._reject_invalid_pending_edit_world(
                entry,
                failure_context=failure_context,
                error=exc,
            )

    def _sync_entry_from_edit_world(self, entry: SceneWorkspaceEntry) -> bool:
        if entry.is_playing or entry.edit_world is None:
            return False
        self._workspace.select_entity(
            entry,
            entity_name=entry.edit_world.selected_entity_name,
        )
        payload = self._projection.build_canonical_payload(
            entry.scene,
            entry.edit_world.serialize(),
        )
        data = self._projection.validate_payload(
            self._workspace.prepare_scene_payload(payload)
        )
        self._workspace.replace_entry_scene(entry, data)
        self._workspace.sync_feature_metadata_from_scene_links(entry)
        self.clear_pending(entry)
        return True

    def _reject_invalid_pending_edit_world(
        self,
        entry: SceneWorkspaceEntry,
        *,
        failure_context: str,
        error: ValueError,
    ) -> bool:
        dirty = (
            entry.dirty_before_pending_edit_world_sync
            if entry.dirty_before_pending_edit_world_sync is not None
            else entry.dirty
        )
        self._workspace.rebuild_edit_world(entry)
        self._workspace.restore_dirty(entry, dirty)
        self.clear_pending(entry)
        return False
