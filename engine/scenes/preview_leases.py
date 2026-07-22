"""Conflict-aware leases for editor previews."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from engine.scenes.contracts import SceneHistoryPort, SceneSnapshotRestore
from engine.scenes.projection_integrity import (
    AuthoringProjectionFingerprintService,
    ProjectionIntegrityAction,
    ProjectionIntegrityGuard,
)

if TYPE_CHECKING:
    from engine.scenes.scene import Scene
    from engine.scenes.workspace_lifecycle import SceneWorkspaceEntry


class PreviewLeaseCode(str, Enum):
    ACQUIRED = "acquired"
    ACTIVE_LEASE = "active_lease"
    CANCELLED = "cancelled"
    COMMITTED = "committed"
    CONFLICT = "conflict"
    HISTORY_FAILED = "history_failed"
    INVALID_ENTRY = "invalid_entry"
    NOT_FOUND = "not_found"
    APPLY_FAILED = "apply_failed"
    INTEGRITY_BLOCKED = "integrity_blocked"


class PreviewCancelReason(str, Enum):
    USER = "user"
    SCENE_SWITCH = "scene_switch"
    PLAY = "play"
    SAVE = "save"
    UNDO_REDO = "undo_redo"
    POINTER_CAPTURE_LOST = "pointer_capture_lost"
    TARGET_MISSING = "target_missing"
    CONFLICT = "conflict"
    VALIDATION_FAILED = "validation_failed"


@dataclass(frozen=True, slots=True)
class PreviewLease:
    lease_id: str
    scene_key: str
    scene_revision: int
    base_fingerprint: str
    kind: str
    label: str


@dataclass(frozen=True, slots=True)
class PreviewLeaseReport:
    success: bool
    code: PreviewLeaseCode
    message: str
    lease: PreviewLease | None = None
    history_recorded: bool = False


@dataclass(frozen=True, slots=True)
class _PreviewLeaseState:
    lease: PreviewLease
    base_scene_snapshot: dict[str, Any]


class PreviewLeaseRegistry:
    """Owns preview identity and commit/cancel conflict boundaries."""

    def __init__(
        self,
        fingerprint_service: AuthoringProjectionFingerprintService,
        *,
        history: SceneHistoryPort,
        restore_snapshot: SceneSnapshotRestore,
    ) -> None:
        self._fingerprint_service = fingerprint_service
        self._guard = ProjectionIntegrityGuard(fingerprint_service)
        self._history = history
        self._restore_snapshot = restore_snapshot
        self._leases: dict[str, _PreviewLeaseState] = {}

    def acquire(
        self,
        entry: "SceneWorkspaceEntry",
        *,
        kind: str,
        label: str,
    ) -> PreviewLeaseReport:
        if entry.edit_world is None or entry.projection_integrity_evidence is None:
            return self._failure(
                PreviewLeaseCode.INVALID_ENTRY,
                "A preview requires an installed Scene/EditWorld projection.",
            )
        if self.active_for_scene(entry.key) is not None:
            return self._failure(
                PreviewLeaseCode.ACTIVE_LEASE,
                "The scene already has an active preview lease.",
            )
        integrity = self._guard.inspect(
            entry,
            action=ProjectionIntegrityAction.PREVIEW_COMMIT,
        )
        if not integrity.allowed:
            return self._failure(
                PreviewLeaseCode.INTEGRITY_BLOCKED,
                integrity.message,
            )

        lease = PreviewLease(
            lease_id=uuid4().hex,
            scene_key=entry.key,
            scene_revision=entry.scene_revision,
            base_fingerprint=self._fingerprint_service.fingerprint_scene(entry.scene),
            kind=str(kind or "preview"),
            label=str(label or "preview"),
        )
        self._leases[lease.lease_id] = _PreviewLeaseState(
            lease=lease,
            base_scene_snapshot=copy.deepcopy(entry.scene.to_dict()),
        )
        return PreviewLeaseReport(
            success=True,
            code=PreviewLeaseCode.ACQUIRED,
            message="Preview lease acquired.",
            lease=lease,
        )

    def active_for_scene(self, scene_key: str) -> PreviewLease | None:
        for state in self._leases.values():
            if state.lease.scene_key == scene_key:
                return state.lease
        return None

    def cancel(
        self,
        lease_id: str,
        *,
        cancel_preview: Callable[[], bool] | None = None,
    ) -> PreviewLeaseReport:
        state = self._leases.get(lease_id)
        if state is None:
            return self._failure(PreviewLeaseCode.NOT_FOUND, "Preview lease was not found.")
        if cancel_preview is not None and not cancel_preview():
            return self._failure(
                PreviewLeaseCode.APPLY_FAILED,
                "Preview cancellation did not complete.",
                lease=state.lease,
            )
        del self._leases[lease_id]
        return PreviewLeaseReport(
            success=True,
            code=PreviewLeaseCode.CANCELLED,
            message="Preview cancelled without persistent changes.",
            lease=state.lease,
        )

    def commit(
        self,
        lease_id: str,
        entry: "SceneWorkspaceEntry",
        *,
        apply_preview: Callable[[], bool],
        restore_snapshot: SceneSnapshotRestore | None = None,
    ) -> PreviewLeaseReport:
        state = self._leases.get(lease_id)
        if state is None:
            return self._failure(PreviewLeaseCode.NOT_FOUND, "Preview lease was not found.")
        lease = state.lease
        if entry.key != lease.scene_key:
            return self._failure(
                PreviewLeaseCode.CONFLICT,
                "Preview lease belongs to another scene.",
                lease=lease,
            )
        if entry.scene_revision != lease.scene_revision:
            return self._failure(
                PreviewLeaseCode.CONFLICT,
                "Scene revision changed while the preview was open.",
                lease=lease,
            )
        if self._fingerprint_service.fingerprint_scene(entry.scene) != lease.base_fingerprint:
            return self._failure(
                PreviewLeaseCode.CONFLICT,
                "Persistent Scene data changed while the preview was open.",
                lease=lease,
            )

        try:
            applied = apply_preview()
        except Exception as exc:
            return self._failure(
                PreviewLeaseCode.APPLY_FAILED,
                f"Preview commit failed: {exc}",
                lease=lease,
            )
        if not applied:
            return self._failure(
                PreviewLeaseCode.APPLY_FAILED,
                "Preview commit was rejected by the authoring boundary.",
                lease=lease,
            )

        after_snapshot = copy.deepcopy(entry.scene.to_dict())
        history = self._history
        restore = restore_snapshot or self._restore_snapshot
        post_integrity = self._guard.inspect(
            entry,
            action=ProjectionIntegrityAction.PREVIEW_COMMIT,
        )
        if not post_integrity.allowed:
            try:
                restore(lease.scene_key, copy.deepcopy(state.base_scene_snapshot))
            except Exception:
                pass
            return self._failure(
                PreviewLeaseCode.INTEGRITY_BLOCKED,
                post_integrity.message,
                lease=lease,
            )
        if state.base_scene_snapshot != after_snapshot:
            try:
                history.record_snapshot_change(
                    label=lease.label,
                    undo=lambda: restore(lease.scene_key, copy.deepcopy(state.base_scene_snapshot)),
                    redo=lambda: restore(lease.scene_key, copy.deepcopy(after_snapshot)),
                )
            except Exception as exc:
                try:
                    restore(lease.scene_key, copy.deepcopy(state.base_scene_snapshot))
                except Exception:
                    pass
                return self._failure(
                    PreviewLeaseCode.HISTORY_FAILED,
                    f"Preview history entry failed: {exc}",
                    lease=lease,
                )

        del self._leases[lease_id]
        return PreviewLeaseReport(
            success=True,
            code=PreviewLeaseCode.COMMITTED,
            message="Preview committed as one persistent history entry.",
            lease=lease,
            history_recorded=state.base_scene_snapshot != after_snapshot,
        )

    @staticmethod
    def _failure(
        code: PreviewLeaseCode,
        message: str,
        *,
        lease: PreviewLease | None = None,
    ) -> PreviewLeaseReport:
        return PreviewLeaseReport(
            success=False,
            code=code,
            message=message,
            lease=lease,
        )
