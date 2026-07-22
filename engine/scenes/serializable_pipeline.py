from __future__ import annotations

import copy
from typing import Any

from engine.core.runtime_logging import log_err
from engine.scenes.contracts import SceneHistoryPort
from engine.scenes.edit_sync import SceneEditSyncCoordinator
from engine.scenes.post_commit import (
    DomainEvent,
    PostCommitEventPublisher,
    changed_entity_refs,
)
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
        self._post_commit_publisher: PostCommitEventPublisher | None = None

    def set_post_commit_publisher(
        self,
        publisher: PostCommitEventPublisher | None,
    ) -> None:
        """Attach the editor notification output without exposing a bus."""
        self._post_commit_publisher = publisher

    def flush_pending(
        self,
        entry: SceneWorkspaceEntry,
        *,
        failure_context: str,
    ) -> bool:
        has_pending_legacy = self._edit_sync.has_pending_legacy(entry)
        if has_pending_legacy and entry.key != self._workspace.active_scene_key:
            return False
        if not has_pending_legacy:
            return self._edit_sync.flush_pending(
                entry,
                failure_context=failure_context,
            )
        try:
            guard = self._mutations.capture_snapshot(entry)
        except Exception as exc:
            log_err(
                "SceneSerializableAuthoringPipeline: failed to guard pending flush "
                f"{failure_context}: {exc}"
            )
            return False
        try:
            return self._edit_sync.flush_pending(
                entry,
                failure_context=failure_context,
            )
        except Exception as exc:
            self._mutations.restore_snapshot(entry, guard)
            log_err(
                "SceneSerializableAuthoringPipeline: failed pending flush "
                f"{failure_context}: {exc}"
            )
            return False

    def begin(
        self,
        entry: SceneWorkspaceEntry,
        *,
        failure_context: str,
        clone_world: bool = False,
    ) -> tuple[object, dict[str, Any]] | None:
        if entry.is_playing or not self.flush_pending(
            entry,
            failure_context=failure_context,
        ):
            return None
        try:
            token = self._mutations.capture_snapshot(
                entry,
                clone_world=clone_world,
            )
            return token, self._mutations.snapshot_scene_data(token)
        except Exception as exc:
            log_err(
                "SceneSerializableAuthoringPipeline: failed to begin "
                f"{failure_context}: {exc}"
            )
            return None

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
            try:
                before_snapshot = copy.deepcopy(before)
                after_snapshot = self._mutations.snapshot_entry_scene_data(entry)
                if before_snapshot != after_snapshot:
                    key = entry.key
                    self._history.record_snapshot_change(
                        label=label,
                        undo=lambda: self._mutations.restore_scene_data(
                            key,
                            copy.deepcopy(before_snapshot),
                        ),
                        redo=lambda: self._mutations.restore_scene_data(
                            key,
                            copy.deepcopy(after_snapshot),
                        ),
                    )
            except Exception as exc:
                self._mutations.restore_snapshot(entry, token)
                log_err(
                    "SceneSerializableAuthoringPipeline: failed to record "
                    f"{label}: {exc}"
                )
                return False
        after_snapshot = self._mutations.snapshot_entry_scene_data(entry)
        if before != after_snapshot:
            self._publish_commit(
                entry,
                label=label,
                before=before,
                after=after_snapshot,
            )
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
        before_snapshot = self._mutations.snapshot_scene_data(token)
        after_snapshot = self._mutations.snapshot_entry_scene_data(entry)
        if before_snapshot != after_snapshot:
            self._publish_commit(
                entry,
                label=failure_context,
                before=before_snapshot,
                after=after_snapshot,
            )
        return True

    def _publish_commit(
        self,
        entry: SceneWorkspaceEntry,
        *,
        label: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None:
        publisher = self._post_commit_publisher
        if publisher is None:
            return
        publisher.publish(
            DomainEvent(
                scene=entry.open_scene_ref,
                scene_revision=entry.scene.revision,
                label=str(label or "scene_commit"),
                changed_entities=changed_entity_refs(
                    entry.open_scene_ref,
                    before,
                    after,
                ),
            )
        )
