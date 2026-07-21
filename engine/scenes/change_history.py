from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable

from engine.core.runtime_logging import log_err
from engine.scenes.contracts import SceneSnapshotRestore


@dataclass
class SceneTransactionState:
    label: str
    key: str
    before: dict[str, Any]
    changes: list[dict[str, Any]] = field(default_factory=list)


class SceneChangeCoordinator:
    """Passive history storage, grouping, and restoration coordinator."""

    def __init__(self) -> None:
        self._history: Any = None
        self._active_transaction: SceneTransactionState | None = None

    @property
    def has_active_transaction(self) -> bool:
        return self._active_transaction is not None

    @property
    def active_transaction_scene_key(self) -> str | None:
        transaction = self._active_transaction
        return transaction.key if transaction is not None else None

    def set_history_manager(self, history: Any) -> None:
        self._history = history

    def _push_history(
        self,
        *,
        label: str,
        undo: Callable[[], bool],
        redo: Callable[[], bool],
    ) -> None:
        history = self._history
        if history is None:
            return
        capture_checkpoint = getattr(history, "capture_checkpoint", None)
        restore_checkpoint = getattr(history, "restore_checkpoint", None)
        if not callable(capture_checkpoint) or not callable(restore_checkpoint):
            history.push(label=label, undo=undo, redo=redo)
            return
        checkpoint = capture_checkpoint()
        try:
            history.push(label=label, undo=undo, redo=redo)
        except Exception as push_error:
            try:
                restore_checkpoint(checkpoint)
            except Exception as restore_error:
                log_err(
                    "SceneChangeCoordinator: failed to restore history checkpoint "
                    f"after push failure: {restore_error}"
                )
                raise push_error from restore_error
            raise

    def begin_transaction(
        self,
        *,
        label: str,
        scene_key: str,
        before: dict[str, Any],
    ) -> bool:
        if self._active_transaction is not None:
            return False
        self._active_transaction = SceneTransactionState(
            label=label,
            key=scene_key,
            before=copy.deepcopy(before),
        )
        return True

    def append_transaction_change(self, change: dict[str, Any]) -> bool:
        transaction = self._active_transaction
        if transaction is None:
            return False
        transaction.changes.append(copy.deepcopy(change))
        return True

    def discard_transaction(self) -> bool:
        if self._active_transaction is None:
            return False
        self._active_transaction = None
        return True

    def commit_transaction(
        self,
        after: dict[str, Any] | None,
        restore: SceneSnapshotRestore,
    ) -> dict[str, Any] | None:
        transaction = self._active_transaction
        if transaction is None:
            return None
        if after is None:
            self.discard_transaction()
            return None

        key = transaction.key
        before_snapshot = copy.deepcopy(transaction.before)
        after_snapshot = copy.deepcopy(after)
        changes_snapshot = copy.deepcopy(transaction.changes)
        result = {
            "label": transaction.label,
            "scene_key": key,
            "changes": changes_snapshot,
        }
        if before_snapshot != after_snapshot:
            self._push_history(
                label=transaction.label,
                undo=lambda: restore(key, copy.deepcopy(before_snapshot)),
                redo=lambda: restore(key, copy.deepcopy(after_snapshot)),
            )
        self._active_transaction = None
        return result

    def rollback_transaction(self, restore: SceneSnapshotRestore) -> bool:
        transaction = self._active_transaction
        if transaction is None:
            return False
        self._active_transaction = None
        return restore(transaction.key, copy.deepcopy(transaction.before))

    def record_snapshot_change(
        self,
        *,
        label: str,
        undo: Callable[[], bool],
        redo: Callable[[], bool],
    ) -> None:
        if self._history is None or self.has_active_transaction:
            return
        self._push_history(label=label, undo=undo, redo=redo)

    def record_differential_change(
        self,
        *,
        label: str,
        undo: Callable[[], bool],
        redo: Callable[[], bool],
    ) -> None:
        if self._history is None or self.has_active_transaction:
            return
        self._push_history(label=label, undo=undo, redo=redo)
