"""Explicit, leased compatibility boundary for World -> Scene authoring."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from uuid import uuid4

from engine.scenes.edit_sync import LEGACY_AUTHORING_SYNC_REASON, SceneEditSyncCoordinator
from engine.scenes.projection_integrity import AuthoringProjectionFingerprintService
from engine.scenes.refs import OpenDocumentId
from engine.scenes.result import CommandError, CommandErrorCode, Err, Ok, Result
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry


@dataclass(frozen=True, slots=True)
class LegacyMutationLease:
    open_document_id: OpenDocumentId
    consumer: str
    owner: str
    mutation_scope: frozenset[str]
    initial_scene_revision: int
    initial_fingerprint: str
    lease_id: str
    initial_world_snapshot: dict[str, object]


class LegacyWorldAuthoringAdapter:
    """Closed allowlist; only explicit ``commit(lease)`` imports World data."""

    ALLOWED_REASONS = frozenset({LEGACY_AUTHORING_SYNC_REASON})

    def __init__(
        self,
        edit_sync: SceneEditSyncCoordinator,
        workspace: SceneWorkspace,
        fingerprint_service: AuthoringProjectionFingerprintService | None = None,
    ) -> None:
        self._edit_sync = edit_sync
        self._workspace = workspace
        self._fingerprint_service = fingerprint_service
        self._leases: dict[str, LegacyMutationLease] = {}
        self._consumer_metrics: dict[str, int] = {}

    def open_lease(
        self,
        entry: SceneWorkspaceEntry,
        *,
        consumer: str,
        owner: str,
        mutation_scope: frozenset[str],
    ) -> Result[LegacyMutationLease]:
        normalized_consumer = str(consumer or "").strip()
        normalized_owner = str(owner or "").strip()
        scope = frozenset(str(item).strip() for item in mutation_scope if str(item).strip())
        evidence = entry.projection_integrity_evidence
        if not normalized_consumer or not normalized_owner or not scope or evidence is None or entry.edit_world is None:
            return Err(
                CommandError(
                    CommandErrorCode.VALIDATION_FAILED,
                    "Legacy lease requires consumer, owner, mutation scope and projection evidence.",
                )
            )
        if self.has_open_lease(entry):
            return Err(CommandError(CommandErrorCode.PREVIEW_ACTIVE, "A legacy authoring lease is already open."))
        lease = LegacyMutationLease(
            open_document_id=entry.open_document_id,
            consumer=normalized_consumer,
            owner=normalized_owner,
            mutation_scope=scope,
            initial_scene_revision=entry.scene.revision,
            initial_fingerprint=evidence.canonical_fingerprint,
            lease_id=uuid4().hex,
            initial_world_snapshot=self._snapshot_world(entry.edit_world),
        )
        self._leases[lease.lease_id] = lease
        return Ok(lease)

    def has_open_lease(self, entry: SceneWorkspaceEntry) -> bool:
        return any(lease.open_document_id == entry.open_document_id for lease in self._leases.values())

    def cancel(self, lease: LegacyMutationLease) -> Result[None]:
        current = self._leases.get(lease.lease_id)
        if current != lease:
            return Err(CommandError(CommandErrorCode.NOT_FOUND, "Legacy authoring lease was not found."))
        entry = self._workspace.resolve_open_document(lease.open_document_id)
        if entry is None:
            self._leases.pop(lease.lease_id, None)
            self._record(lease.consumer)
            return Err(CommandError(CommandErrorCode.NOT_FOUND, "Open document for legacy lease was not found."))
        dirty_before = entry.dirty_before_pending_edit_world_sync
        self._workspace.rebuild_edit_world(entry)
        if dirty_before is not None:
            self._workspace.restore_dirty(entry, dirty_before)
        self._edit_sync.clear_pending(entry)
        self._leases.pop(lease.lease_id, None)
        self._record(lease.consumer)
        return Ok(None)

    def commit(self, lease: LegacyMutationLease) -> Result[None]:
        current = self._leases.get(lease.lease_id)
        if current != lease:
            return Err(CommandError(CommandErrorCode.NOT_FOUND, "Legacy authoring lease was not found."))
        entry = self._workspace.resolve_open_document(lease.open_document_id)
        if entry is None or entry.edit_world is None:
            return self._close_with_error(lease, "Open document for legacy lease was not found.")
        if entry.scene.revision != lease.initial_scene_revision:
            return self._close_with_error(
                lease,
                "Scene changed while legacy authoring lease was open.",
                CommandErrorCode.CONFLICT,
                entry=entry,
            )
        if (
            self._fingerprint_service is not None
            and self._fingerprint_service.fingerprint_scene(entry.scene) != lease.initial_fingerprint
        ):
            return self._close_with_error(
                lease,
                "Scene fingerprint changed while legacy authoring lease was open.",
                CommandErrorCode.CONFLICT,
                entry=entry,
            )
        current_snapshot = self._snapshot_world(entry.edit_world)
        changed_scopes = self._changed_scopes(lease.initial_world_snapshot, current_snapshot)
        outside_scope = changed_scopes - lease.mutation_scope
        if outside_scope:
            return self._close_with_error(
                lease,
                f"Legacy authoring changed fields outside scope: {sorted(outside_scope)}.",
                CommandErrorCode.VALIDATION_FAILED,
                entry=entry,
            )
        if not changed_scopes:
            self._leases.pop(lease.lease_id, None)
            self._record(lease.consumer)
            return Ok(None)

        entry.pending_edit_world_sync_reason = LEGACY_AUTHORING_SYNC_REASON
        self._workspace.mark_dirty(entry)
        try:
            committed = self._edit_sync.commit_legacy_entry(entry)
        except Exception as exc:
            return self._close_with_error(
                lease,
                f"Legacy authoring commit failed: {exc}",
                CommandErrorCode.INTERNAL_ERROR,
                entry=entry,
            )
        self._leases.pop(lease.lease_id, None)
        self._record(lease.consumer)
        if not committed:
            return Err(CommandError(CommandErrorCode.PROJECTION_DIVERGED, "Legacy authoring commit was rejected."))
        return Ok(None)

    def sync_pending(self) -> bool:
        """Deprecated compatibility entrypoint; no implicit import is performed."""
        return False

    def mark_dirty(self, *, reason: str = LEGACY_AUTHORING_SYNC_REASON) -> bool:
        if reason not in self.ALLOWED_REASONS:
            return False
        return self._edit_sync.mark_edit_world_dirty(reason=reason)

    @property
    def consumer_metrics(self) -> dict[str, int]:
        return dict(self._consumer_metrics)

    def _close_with_error(
        self,
        lease: LegacyMutationLease,
        message: str,
        code: CommandErrorCode = CommandErrorCode.NOT_FOUND,
        entry: SceneWorkspaceEntry | None = None,
    ) -> Result[None]:
        if entry is not None:
            dirty_before = entry.dirty_before_pending_edit_world_sync
            self._workspace.rebuild_edit_world(entry)
            if dirty_before is not None:
                self._workspace.restore_dirty(entry, dirty_before)
            self._edit_sync.clear_pending(entry)
        self._leases.pop(lease.lease_id, None)
        self._record(lease.consumer)
        return Err(CommandError(code, message))

    def _record(self, consumer: str) -> None:
        self._consumer_metrics[consumer] = self._consumer_metrics.get(consumer, 0) + 1

    @staticmethod
    def _changed_scopes(before: dict[str, object], after: dict[str, object]) -> set[str]:
        changed: set[str] = set()
        before_entities = before.get("entities", [])
        after_entities = after.get("entities", [])
        if before_entities != after_entities:
            before_by_id = {
                str(entity.get("id")): entity
                for entity in before_entities
                if isinstance(entity, dict) and entity.get("id")
            }
            after_by_id = {
                str(entity.get("id")): entity
                for entity in after_entities
                if isinstance(entity, dict) and entity.get("id")
            }
            if set(before_by_id) != set(after_by_id):
                changed.add("Entity")
            for entity_id in set(before_by_id) & set(after_by_id):
                before_components = before_by_id[entity_id].get("components", {})
                after_components = after_by_id[entity_id].get("components", {})
                for component_name in set(before_components) | set(after_components):
                    if before_components.get(component_name) != after_components.get(component_name):
                        changed.add(str(component_name))
                if before_by_id[entity_id].get("name") != after_by_id[entity_id].get("name"):
                    changed.add("Entity")
        if before.get("feature_metadata") != after.get("feature_metadata"):
            changed.add("FeatureMetadata")
        return changed

    @staticmethod
    def _snapshot_world(world: "World") -> dict[str, object]:
        snapshot = world.serialize()
        entities = snapshot.get("entities", [])
        if not isinstance(entities, list):
            return snapshot
        for payload in entities:
            if not isinstance(payload, dict):
                continue
            name = payload.get("name")
            entity = world.get_entity_by_name(str(name or ""))
            serialized_id = getattr(entity, "serialized_id", None) if entity is not None else None
            if isinstance(serialized_id, str) and serialized_id.strip():
                payload["id"] = serialized_id.strip()
        return snapshot


__all__ = ["LegacyMutationLease", "LegacyWorldAuthoringAdapter"]
