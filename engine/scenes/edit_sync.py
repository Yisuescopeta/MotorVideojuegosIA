from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from engine.scenes.projection_integrity import (
    AuthoringProjectionFingerprintService,
    ProjectionIntegrityAction,
    ProjectionIntegrityGuard,
    ProjectionIntegrityCode,
    ProjectionIntegrityReport,
)
from engine.scenes.preview_leases import PreviewCancelReason
from engine.scenes.result import Err
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.editor.editor_preview_coordinator import EditorPreviewCoordinator

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
        self._integrity_guard = ProjectionIntegrityGuard(
            AuthoringProjectionFingerprintService(projection.create_world)
        )
        self._last_integrity_report: ProjectionIntegrityReport | None = None
        self._preview_coordinator: "EditorPreviewCoordinator | None" = None
        self._legacy_lease_checker: Callable[[SceneWorkspaceEntry], bool] | None = None

    @property
    def last_integrity_report(self) -> ProjectionIntegrityReport | None:
        return self._last_integrity_report

    def set_preview_coordinator(self, coordinator: "EditorPreviewCoordinator | None") -> None:
        self._preview_coordinator = coordinator

    def set_legacy_lease_checker(
        self,
        checker: Callable[[SceneWorkspaceEntry], bool] | None,
    ) -> None:
        self._legacy_lease_checker = checker

    def inspect_integrity(
        self,
        entry: SceneWorkspaceEntry,
        *,
        action: ProjectionIntegrityAction,
    ) -> ProjectionIntegrityReport:
        report = self._integrity_guard.inspect(entry, action=action)
        self._last_integrity_report = report
        return report

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

    def sync_from_edit_world(self) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        if not self.has_pending_legacy(entry):
            return False
        return self.commit_legacy_entry(entry)

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
        return False

    def prepare_for_save(
        self,
        entry: SceneWorkspaceEntry,
        *,
        failure_context: str = "scene_save",
        action: ProjectionIntegrityAction = ProjectionIntegrityAction.SAVE,
    ) -> bool:
        if entry.edit_world is None:
            return False

        if self._preview_coordinator is not None:
            cancelled = self._preview_coordinator.cancel_all(
                entry.open_document_id,
                self._preview_reason(action),
            )
            if isinstance(cancelled, Err):
                self._last_integrity_report = ProjectionIntegrityReport(
                    action=action,
                    allowed=False,
                    code=ProjectionIntegrityCode.PREVIEW_CANCEL_FAILED,
                    message=cancelled.error.user_message,
                    scene_revision=entry.scene.revision,
                    observed_scene_revision=entry.scene.revision,
                )
                return False
            if self._preview_coordinator.has_writing_leases(entry.open_document_id):
                self._last_integrity_report = ProjectionIntegrityReport(
                    action=action,
                    allowed=False,
                    code=ProjectionIntegrityCode.ACTIVE_PREVIEW,
                    message="Active preview writing leases must be closed before this action.",
                    scene_revision=entry.scene.revision,
                    observed_scene_revision=entry.scene.revision,
                )
                return False

        if self._legacy_lease_checker is not None and self._legacy_lease_checker(entry):
            self._last_integrity_report = ProjectionIntegrityReport(
                action=action,
                allowed=False,
                code=ProjectionIntegrityCode.LEGACY_LEASE_OPEN,
                message="An explicit legacy authoring lease is still open.",
                scene_revision=entry.scene.revision,
                observed_scene_revision=entry.scene.revision,
            )
            return False
        if self.has_pending_legacy(entry):
            self._last_integrity_report = ProjectionIntegrityReport(
                action=action,
                allowed=False,
                code=ProjectionIntegrityCode.LEGACY_PENDING,
                message="Pending EditWorld authoring requires an explicit legacy adapter commit.",
                scene_revision=entry.scene.revision,
                observed_scene_revision=entry.scene.revision,
            )
            return False
        return self.inspect_integrity(entry, action=action).allowed

    @staticmethod
    def _preview_reason(action: ProjectionIntegrityAction) -> PreviewCancelReason:
        return {
            ProjectionIntegrityAction.SAVE: PreviewCancelReason.SAVE,
            ProjectionIntegrityAction.AUTOSAVE: PreviewCancelReason.AUTOSAVE,
            ProjectionIntegrityAction.PLAY: PreviewCancelReason.PLAY,
            ProjectionIntegrityAction.RELOAD: PreviewCancelReason.RELOAD,
            ProjectionIntegrityAction.EXPORT: PreviewCancelReason.EXPORT,
            ProjectionIntegrityAction.LIFECYCLE: PreviewCancelReason.SCENE_SWITCH,
        }.get(action, PreviewCancelReason.INTERRUPTED)

    def commit_legacy_entry(self, entry: SceneWorkspaceEntry) -> bool:
        """Import World -> Scene only for LegacyWorldAuthoringAdapter.commit."""
        if entry.is_playing or entry.edit_world is None or not self.has_pending_legacy(entry):
            return False
        try:
            return self._sync_entry_from_edit_world(entry)
        except ValueError as exc:
            return self._reject_invalid_pending_edit_world(
                entry,
                failure_context="legacy_authoring_commit",
                error=exc,
            )

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
        world_snapshot = entry.edit_world.serialize()
        self._inject_serialized_entity_ids(entry.edit_world, world_snapshot)
        payload = self._projection.build_canonical_payload(
            entry.scene,
            world_snapshot,
        )
        data = self._projection.validate_payload(
            self._workspace.prepare_scene_payload(payload)
        )
        self._workspace.replace_entry_scene(entry, data)
        self._workspace.sync_feature_metadata_from_scene_links(entry)
        self.clear_pending(entry)
        return True

    @staticmethod
    def _inject_serialized_entity_ids(
        world: "World",
        world_snapshot: dict[str, Any],
    ) -> None:
        entities = world_snapshot.get("entities")
        if not isinstance(entities, list):
            raise ValueError("World snapshot entities must be a list")
        for index, entity_payload in enumerate(entities):
            if not isinstance(entity_payload, dict):
                raise ValueError(f"World snapshot entity {index} must be an object")
            entity_name = entity_payload.get("name")
            if not isinstance(entity_name, str) or not entity_name.strip():
                raise ValueError(f"World snapshot entity {index} has an invalid name")
            entity = world.get_entity_by_name(entity_name)
            if entity is None:
                raise ValueError(
                    f"World snapshot entity '{entity_name}' is missing from its source World"
                )
            raw_serialized_id = entity.serialized_id
            if raw_serialized_id is not None and not isinstance(raw_serialized_id, str):
                raise ValueError(
                    f"World entity '{entity_name}' has an invalid serialized_id"
                )
            serialized_id = str(raw_serialized_id or "").strip()
            raw_snapshot_id = entity_payload.get("id")
            if raw_snapshot_id is not None and not isinstance(raw_snapshot_id, str):
                raise ValueError(
                    f"World snapshot entity '{entity_name}' has an invalid id"
                )
            snapshot_id = str(raw_snapshot_id or "").strip()
            if snapshot_id and snapshot_id != serialized_id:
                raise ValueError(
                    f"World snapshot entity '{entity_name}' id does not match its source World"
                )
            if serialized_id:
                entity_payload["id"] = serialized_id
            else:
                entity_payload.pop("id", None)

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
