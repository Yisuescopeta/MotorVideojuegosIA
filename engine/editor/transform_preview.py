"""Typed transform preview boundary for the editor tools migration."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from engine.scenes.preview_leases import PreviewCancelReason, PreviewLeaseCode, PreviewLeaseRegistry
from engine.scenes.refs import EntityRef
from engine.scenes.result import CommandError, CommandErrorCode, Err, MutationMetadata, Ok, Result

if TYPE_CHECKING:
    from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry


@dataclass(frozen=True, slots=True)
class TransformPreviewState:
    x: float
    y: float
    rotation: float
    scale_x: float
    scale_y: float

    def __post_init__(self) -> None:
        for field_name in ("x", "y", "rotation", "scale_x", "scale_y"):
            value = float(getattr(self, field_name))
            if not math.isfinite(value):
                raise ValueError(f"Transform preview field {field_name} must be finite")
            object.__setattr__(self, field_name, value)


@dataclass(frozen=True, slots=True)
class TransformPreviewHandle:
    lease_id: str
    target: EntityRef
    base_scene_revision: int


class TransformPreviewCommands(Protocol):
    def begin(self, entity: EntityRef) -> Result[TransformPreviewHandle]: ...

    def update(
        self,
        handle: TransformPreviewHandle,
        state: TransformPreviewState,
    ) -> Result[None]: ...

    def commit(
        self,
        handle: TransformPreviewHandle,
        state: TransformPreviewState,
    ) -> Result[None]: ...

    def cancel(
        self,
        handle: TransformPreviewHandle,
        reason: PreviewCancelReason,
    ) -> Result[None]: ...


TransformCommit = Callable[[EntityRef, TransformPreviewState], bool]


@dataclass
class _TransformPreviewSession:
    handle: TransformPreviewHandle
    scene_key: str
    state: TransformPreviewState


class TransformPreviewCoordinator:
    """Coordinates typed transform state without mutating Scene during preview."""

    def __init__(
        self,
        workspace: "SceneWorkspace",
        leases: PreviewLeaseRegistry,
        commit_transform: TransformCommit,
    ) -> None:
        self._workspace = workspace
        self._leases = leases
        self._commit_transform = commit_transform
        self._sessions: dict[str, _TransformPreviewSession] = {}

    def begin(self, entity: EntityRef) -> Result[TransformPreviewHandle]:
        entry = self._entry_for(entity)
        if entry is None:
            return Err(self._error(CommandErrorCode.NOT_FOUND, "Transform target was not found."))
        if entry.is_playing:
            return Err(self._error(CommandErrorCode.CONFLICT, "Transform preview is unavailable in PLAY."))
        state = self._read_state(entry, entity.entity_id)
        if state is None:
            return Err(self._error(CommandErrorCode.NOT_FOUND, "Entity has no Transform component."))
        acquired = self._leases.acquire(
            entry,
            kind="transform",
            label=f"transform:{entity.entity_id}",
        )
        if not acquired.success or acquired.lease is None:
            return Err(self._lease_error(acquired.code, acquired.message))
        handle = TransformPreviewHandle(
            lease_id=acquired.lease.lease_id,
            target=entity,
            base_scene_revision=entry.scene_revision,
        )
        self._sessions[handle.lease_id] = _TransformPreviewSession(
            handle=handle,
            scene_key=entry.key,
            state=state,
        )
        return Ok(handle)

    def update(
        self,
        handle: TransformPreviewHandle,
        state: TransformPreviewState,
    ) -> Result[None]:
        session = self._sessions.get(handle.lease_id)
        if session is None or session.handle != handle:
            return Err(self._error(CommandErrorCode.NOT_FOUND, "Transform preview was not found."))
        entry = self._workspace.resolve_entry(session.scene_key)
        if entry is None or entry.scene_revision != handle.base_scene_revision:
            self._cancel_conflicted(session)
            return Err(self._error(CommandErrorCode.CONFLICT, "Scene revision changed during preview."))
        if self._read_state(entry, handle.target.entity_id) is None:
            self._cancel_conflicted(session)
            return Err(self._error(CommandErrorCode.NOT_FOUND, "Transform target disappeared."))
        session.state = state
        return Ok(None)

    def commit(
        self,
        handle: TransformPreviewHandle,
        state: TransformPreviewState,
    ) -> Result[None]:
        session = self._sessions.get(handle.lease_id)
        if session is None or session.handle != handle:
            return Err(self._error(CommandErrorCode.NOT_FOUND, "Transform preview was not found."))
        entry = self._workspace.resolve_entry(session.scene_key)
        if entry is None or entry.scene_revision != handle.base_scene_revision:
            self._cancel_conflicted(session)
            return Err(self._error(CommandErrorCode.CONFLICT, "Scene revision changed during preview."))
        report = self._leases.commit(
            handle.lease_id,
            entry,
            apply_preview=lambda: self._commit_transform(handle.target, state),
        )
        if not report.success:
            self._cancel_conflicted(session)
            return Err(self._lease_error(report.code, report.message))
        self._sessions.pop(handle.lease_id, None)
        return Ok(
            None,
            metadata=MutationMetadata(
                changed_entities=(handle.target,),
                scene_revision=entry.scene_revision,
            ),
        )

    def cancel(
        self,
        handle: TransformPreviewHandle,
        reason: PreviewCancelReason,
    ) -> Result[None]:
        session = self._sessions.get(handle.lease_id)
        if session is None or session.handle != handle:
            return Err(self._error(CommandErrorCode.NOT_FOUND, "Transform preview was not found."))
        report = self._leases.cancel(handle.lease_id)
        if not report.success:
            return Err(self._lease_error(report.code, report.message))
        self._sessions.pop(handle.lease_id, None)
        return Ok(None)

    def _entry_for(self, entity: EntityRef) -> "SceneWorkspaceEntry | None":
        for entry in self._workspace.entries.values():
            if entry.open_document_id == entity.scene.document_id:
                return entry
        return None

    @staticmethod
    def _read_state(entry: "SceneWorkspaceEntry", entity_id: str) -> TransformPreviewState | None:
        view = entry.scene.find_entity_view(entity_id)
        if view is None:
            return None
        components = view.get("components", {})
        transform = components.get("Transform") if isinstance(components, Mapping) else None
        if not isinstance(transform, Mapping):
            return None
        try:
            return TransformPreviewState(
                x=transform.get("x", 0.0),
                y=transform.get("y", 0.0),
                rotation=transform.get("rotation", 0.0),
                scale_x=transform.get("scale_x", 1.0),
                scale_y=transform.get("scale_y", 1.0),
            )
        except (TypeError, ValueError):
            return None

    def _cancel_conflicted(self, session: _TransformPreviewSession) -> None:
        self._leases.cancel(session.handle.lease_id)
        self._sessions.pop(session.handle.lease_id, None)

    @staticmethod
    def _error(code: CommandErrorCode, message: str) -> CommandError:
        return CommandError(code=code, user_message=message)

    @classmethod
    def _lease_error(cls, code: PreviewLeaseCode, message: str) -> CommandError:
        mapped = {
            PreviewLeaseCode.ACTIVE_LEASE: CommandErrorCode.PREVIEW_ACTIVE,
            PreviewLeaseCode.CONFLICT: CommandErrorCode.CONFLICT,
            PreviewLeaseCode.INTEGRITY_BLOCKED: CommandErrorCode.PROJECTION_DIVERGED,
            PreviewLeaseCode.HISTORY_FAILED: CommandErrorCode.PERSISTENCE_FAILED,
            PreviewLeaseCode.NOT_FOUND: CommandErrorCode.NOT_FOUND,
        }.get(code, CommandErrorCode.INTERNAL_ERROR)
        return cls._error(mapped, message)


__all__ = [
    "TransformPreviewCommands",
    "TransformPreviewCoordinator",
    "TransformPreviewHandle",
    "TransformPreviewState",
]
