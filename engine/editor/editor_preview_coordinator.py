"""Application-owned preview lifecycle authority."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from engine.scenes.preview_leases import (
    PreviewCancelReason,
    PreviewLease,
    PreviewLeaseCode,
    PreviewLeaseRegistry,
    PreviewLeaseReport,
)
from engine.scenes.refs import OpenDocumentId
from engine.scenes.result import CommandError, CommandErrorCode, Err, Ok, Result

if TYPE_CHECKING:
    from engine.scenes.workspace_lifecycle import SceneWorkspaceEntry


PreviewCancellation = Callable[[PreviewCancelReason], Result[None]]


class EditorPreviewCoordinator:
    """Single editor-level authority for all preview lease lifecycle."""

    def __init__(self, registry: PreviewLeaseRegistry) -> None:
        self._registry = registry
        self._cancellers: dict[str, PreviewCancellation] = {}

    def acquire(
        self,
        entry: "SceneWorkspaceEntry",
        *,
        kind: str,
        label: str,
    ) -> PreviewLeaseReport:
        return self._registry.acquire(entry, kind=kind, label=label)

    def bind(self, lease_id: str, cancellation: PreviewCancellation) -> None:
        if not lease_id:
            raise ValueError("Preview lease id must be non-empty")
        self._cancellers[lease_id] = cancellation

    def active_for(self, document_id: OpenDocumentId) -> tuple[PreviewLease, ...]:
        return self._registry.active_for(document_id)

    def has_writing_leases(self, document_id: OpenDocumentId) -> bool:
        return bool(self.active_for(document_id))

    def cancel(
        self,
        lease_id: str,
        reason: PreviewCancelReason,
    ) -> Result[None]:
        cancellation = self._cancellers.get(lease_id)
        if cancellation is not None:
            try:
                result = cancellation(reason)
            except Exception as exc:
                self._cancellers.pop(lease_id, None)
                return Err(
                    CommandError(
                        CommandErrorCode.PREVIEW_CANCEL_FAILED,
                        f"Preview cancellation failed: {exc}",
                    )
                )
            if isinstance(result, Err):
                # The tool callback owns cleanup, even when restoration reports
                # an error. Keep no stale local session callback around.
                self._cancellers.pop(lease_id, None)
                return result
            self._cancellers.pop(lease_id, None)
            return result

        report = self._registry.cancel(lease_id)
        if not report.success:
            return Err(self._error_for_report(report))
        self._cancellers.pop(lease_id, None)
        return Ok(None)

    def release(self, lease_id: str) -> Result[None]:
        """Release lease after tool-owned overlay restoration."""
        report = self._registry.cancel(lease_id)
        if not report.success:
            return Err(self._error_for_report(report))
        self._cancellers.pop(lease_id, None)
        return Ok(None)

    def complete(self, lease_id: str) -> None:
        """Forget tool cancellation callback after registry commit."""
        self._cancellers.pop(lease_id, None)

    def commit(
        self,
        lease_id: str,
        entry: "SceneWorkspaceEntry",
        *,
        apply_preview: Callable[[], Result[None] | bool],
    ) -> PreviewLeaseReport:
        """Commit one tool preview through registry conflict/history rules."""
        return self._registry.commit(lease_id, entry, apply_preview=apply_preview)

    def cancel_all(
        self,
        document_id: OpenDocumentId,
        reason: PreviewCancelReason,
    ) -> Result[None]:
        for lease in self.active_for(document_id):
            result = self.cancel(lease.lease_id, reason)
            if isinstance(result, Err):
                return result
        if self.has_writing_leases(document_id):
            return Err(
                CommandError(
                    CommandErrorCode.PREVIEW_CANCEL_FAILED,
                    "Preview cancellation left an active writing lease.",
                )
            )
        return Ok(None)

    @classmethod
    def _error_for_report(cls, report: PreviewLeaseReport) -> CommandError:
        mapped = {
            PreviewLeaseCode.ACTIVE_LEASE: CommandErrorCode.PREVIEW_ACTIVE,
            PreviewLeaseCode.CONFLICT: CommandErrorCode.CONFLICT,
            PreviewLeaseCode.INTEGRITY_BLOCKED: CommandErrorCode.PROJECTION_DIVERGED,
            PreviewLeaseCode.HISTORY_FAILED: CommandErrorCode.PERSISTENCE_FAILED,
            PreviewLeaseCode.NOT_FOUND: CommandErrorCode.NOT_FOUND,
            PreviewLeaseCode.APPLY_FAILED: CommandErrorCode.PREVIEW_CANCEL_FAILED,
        }.get(report.code, CommandErrorCode.INTERNAL_ERROR)
        return CommandError(mapped, report.message)


__all__ = ["EditorPreviewCoordinator", "PreviewCancellation"]
