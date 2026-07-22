"""Fail-closed, conflict-aware Transform preview commands."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from engine.components.transform import Transform
from engine.editor.editor_preview_coordinator import EditorPreviewCoordinator
from engine.scenes.preview_leases import PreviewCancelReason, PreviewLeaseCode
from engine.scenes.refs import EntityRef, OpenDocumentId
from engine.scenes.result import CommandError, CommandErrorCode, Err, MutationMetadata, Ok, Result

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.scenes.contracts import SceneWorkspacePort
    from engine.scenes.workspace_lifecycle import SceneWorkspaceEntry


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

    def update(self, handle: TransformPreviewHandle, state: TransformPreviewState) -> Result[None]: ...

    def commit(self, handle: TransformPreviewHandle, state: TransformPreviewState) -> Result[None]: ...

    def cancel(self, handle: TransformPreviewHandle, reason: PreviewCancelReason) -> Result[None]: ...


TransformCommit = Callable[[EntityRef, TransformPreviewState], Result[None] | bool]


@dataclass
class _TransformPreviewSession:
    handle: TransformPreviewHandle
    document_id: OpenDocumentId
    scene_key: str
    base_state: TransformPreviewState
    state: TransformPreviewState


class TransformPreviewCoordinator:
    """Tool-specific Transform boundary using application-owned preview lifecycle."""

    def __init__(
        self,
        workspace: "SceneWorkspacePort",
        previews: EditorPreviewCoordinator,
        commit_transform: TransformCommit,
    ) -> None:
        self._workspace = workspace
        self._previews = previews
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
        acquired = self._previews.acquire(entry, kind="transform", label=f"transform:{entity.entity_id}")
        if not acquired.success or acquired.lease is None:
            return Err(self._lease_error(acquired.code, acquired.message))
        handle = TransformPreviewHandle(
            lease_id=acquired.lease.lease_id,
            target=entity,
            base_scene_revision=entry.scene.revision,
        )
        session = _TransformPreviewSession(
            handle=handle,
            document_id=entry.open_document_id,
            scene_key=entry.key,
            base_state=state,
            state=state,
        )
        self._sessions[handle.lease_id] = session
        self._previews.bind(handle.lease_id, lambda reason: self._cancel_bound(session, reason))
        return Ok(handle)

    def update(self, handle: TransformPreviewHandle, state: TransformPreviewState) -> Result[None]:
        session = self._sessions.get(handle.lease_id)
        if session is None or session.handle != handle:
            return Err(self._error(CommandErrorCode.NOT_FOUND, "Transform preview was not found."))
        entry = self._workspace.resolve_open_document(session.document_id)
        try:
            if entry is None or entry.scene.revision != handle.base_scene_revision:
                self._cancel_bound(session, PreviewCancelReason.CONFLICT)
                return Err(self._error(CommandErrorCode.CONFLICT, "Scene revision changed during preview."))
            if self._read_state(entry, handle.target.entity_id) is None:
                self._cancel_bound(session, PreviewCancelReason.TARGET_MISSING)
                return Err(self._error(CommandErrorCode.NOT_FOUND, "Transform target disappeared."))
            if not self._apply_overlay(entry.edit_world, handle.target.entity_id, state):
                self._cancel_bound(session, PreviewCancelReason.ERROR)
                return Err(self._error(CommandErrorCode.NOT_FOUND, "Transform preview target disappeared."))
            session.state = state
            return Ok(None)
        except Exception as exc:
            self._cancel_bound(session, PreviewCancelReason.ERROR)
            return Err(self._error(CommandErrorCode.INTERNAL_ERROR, f"Transform preview update failed: {exc}"))

    def commit(self, handle: TransformPreviewHandle, state: TransformPreviewState) -> Result[None]:
        session = self._sessions.get(handle.lease_id)
        if session is None or session.handle != handle:
            return Err(self._error(CommandErrorCode.NOT_FOUND, "Transform preview was not found."))
        if state == session.base_state:
            return self.cancel(handle, PreviewCancelReason.DRAG_NO_CHANGES)
        entry = self._workspace.resolve_open_document(session.document_id)
        if entry is None or entry.scene.revision != handle.base_scene_revision:
            self._cancel_bound(session, PreviewCancelReason.CONFLICT)
            return Err(self._error(CommandErrorCode.CONFLICT, "Scene revision changed during preview."))

        callback_result: Result[None] | bool = False
        callback_exception: Exception | None = None

        def apply_preview() -> Result[None] | bool:
            nonlocal callback_result, callback_exception
            try:
                callback_result = self._commit_transform(handle.target, state)
            except Exception as exc:
                callback_exception = exc
                raise
            return callback_result

        try:
            report = self._previews.commit(
                handle.lease_id,
                entry,
                apply_preview=apply_preview,
            )
        except Exception as exc:
            self._cancel_bound(session, PreviewCancelReason.ERROR)
            return Err(self._error(CommandErrorCode.INTERNAL_ERROR, f"Transform preview commit failed: {exc}"))
        if not report.success:
            self._cancel_bound(session, PreviewCancelReason.ERROR)
            if isinstance(callback_result, Err):
                return callback_result
            if callback_exception is not None:
                return Err(
                    self._error(
                        CommandErrorCode.INTERNAL_ERROR,
                        f"Transform preview commit failed: {callback_exception}",
                    )
                )
            return Err(self._lease_error(report.code, report.message))
        self._previews.complete(handle.lease_id)
        self._sessions.pop(handle.lease_id, None)
        return Ok(
            None,
            metadata=MutationMetadata(
                changed_entities=(handle.target,),
                scene_revision=entry.scene.revision,
            ),
        )

    def cancel(self, handle: TransformPreviewHandle, reason: PreviewCancelReason) -> Result[None]:
        session = self._sessions.get(handle.lease_id)
        if session is None or session.handle != handle:
            return Err(self._error(CommandErrorCode.NOT_FOUND, "Transform preview was not found."))
        return self._previews.cancel(handle.lease_id, reason)

    def _cancel_bound(self, session: _TransformPreviewSession, reason: PreviewCancelReason) -> Result[None]:
        entry = self._workspace.resolve_open_document(session.document_id)
        restore_error: Exception | None = None
        try:
            if entry is not None:
                self._restore_overlay(entry, session.handle.target.entity_id, session.base_state)
        except Exception as exc:
            restore_error = exc
        finally:
            released = self._previews.release(session.handle.lease_id)
            self._sessions.pop(session.handle.lease_id, None)
        if isinstance(released, Err):
            return released
        if restore_error is not None:
            return Err(
                self._error(
                    CommandErrorCode.PREVIEW_CANCEL_FAILED,
                    f"Transform preview restoration failed: {restore_error}",
                )
            )
        return released

    @staticmethod
    def _restore_overlay(
        entry: "SceneWorkspaceEntry",
        entity_id: str,
        state: TransformPreviewState,
    ) -> None:
        if entry.edit_world is None or not TransformPreviewCoordinator._apply_overlay(entry.edit_world, entity_id, state):
            raise RuntimeError("Transform preview overlay could not be restored")

    @staticmethod
    def _apply_overlay(world: "World | None", entity_id: str, state: TransformPreviewState) -> bool:
        if world is None:
            return False
        entity = world.get_entity_by_serialized_id(entity_id)
        if entity is None:
            return False
        transform = entity.get_component(Transform)
        if transform is None:
            return False
        transform.local_x = state.x
        transform.local_y = state.y
        transform.local_rotation = state.rotation
        transform.local_scale_x = state.scale_x
        transform.local_scale_y = state.scale_y
        return True

    def _entry_for(self, entity: EntityRef) -> "SceneWorkspaceEntry | None":
        return self._workspace.resolve_open_document(entity.scene.document_id)

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
            PreviewLeaseCode.APPLY_FAILED: CommandErrorCode.PREVIEW_CANCEL_FAILED,
        }.get(code, CommandErrorCode.INTERNAL_ERROR)
        return cls._error(mapped, message)


__all__ = [
    "TransformPreviewCommands",
    "TransformPreviewCoordinator",
    "TransformPreviewHandle",
    "TransformPreviewState",
]
