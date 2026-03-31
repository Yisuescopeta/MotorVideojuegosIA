from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from engine.authoring.changes import Change
from engine.scenes.workspace_lifecycle import SceneWorkspaceEntry


@dataclass(frozen=True)
class SceneChangeCoordinatorContext:
    resolve_entry: Callable[[Optional[str]], Optional[SceneWorkspaceEntry]]
    restore_entry_scene: Callable[[SceneWorkspaceEntry, dict[str, Any]], None]
    snapshot_scene: Callable[[SceneWorkspaceEntry], dict[str, Any]]
    edit_component: Callable[[str, str, str, Any], bool]
    set_entity_property: Callable[[str, str, Any], bool]
    add_component: Callable[[str, str, Optional[dict[str, Any]]], bool]
    remove_component: Callable[[str, str], bool]
    create_entity: Callable[[str, Optional[dict[str, dict[str, Any]]]], bool]
    delete_entity: Callable[[str], bool]


@dataclass
class SceneTransactionState:
    label: str
    key: str
    before: dict[str, Any]
    changes: list[dict[str, Any]] = field(default_factory=list)


class SceneChangeCoordinator:
    def __init__(self, context: SceneChangeCoordinatorContext) -> None:
        self._context = context
        self._history: Any = None
        self._suspend_history = False
        self._active_transaction: SceneTransactionState | None = None
        self._dispatch = {
            "edit_component": self._apply_edit_component,
            "set_entity_property": self._apply_set_entity_property,
            "add_component": self._apply_add_component,
            "remove_component": self._apply_remove_component,
            "create_entity": self._apply_create_entity,
            "delete_entity": self._apply_delete_entity,
        }

    def set_history_manager(self, history: Any) -> None:
        self._history = history

    def begin_transaction(self, label: str = "transaction", key: Optional[str] = None) -> bool:
        entry = self._context.resolve_entry(key)
        if entry is None or entry.is_playing or self._active_transaction is not None:
            return False
        self._active_transaction = SceneTransactionState(
            label=label,
            key=entry.key,
            before=self._context.snapshot_scene(entry),
        )
        self._suspend_history = True
        return True

    def apply_change(self, change: Change | dict[str, Any], key: Optional[str] = None) -> bool:
        _ = key
        payload = change if isinstance(change, Change) else Change.from_dict(change)
        handler = self._dispatch.get(payload.kind)
        success = handler(payload) if handler is not None else False
        if success and self._active_transaction is not None:
            self._active_transaction.changes.append(payload.to_dict())
        return success

    def commit_transaction(self) -> Optional[dict[str, Any]]:
        if self._active_transaction is None:
            return None
        transaction = self._active_transaction
        entry = self._context.resolve_entry(transaction.key)
        if entry is None:
            self._active_transaction = None
            self._suspend_history = False
            return None
        after = self._context.snapshot_scene(entry)
        if self._history is not None and transaction.before != after:
            key = transaction.key
            before = copy.deepcopy(transaction.before)
            after_snapshot = copy.deepcopy(after)
            self._history.push(
                label=transaction.label,
                undo=lambda key=key, before=before: self.restore_scene_data_for_key(key, before),
                redo=lambda key=key, after=after_snapshot: self.restore_scene_data_for_key(key, after),
            )
        result = {
            "label": transaction.label,
            "scene_key": transaction.key,
            "changes": copy.deepcopy(transaction.changes),
        }
        self._active_transaction = None
        self._suspend_history = False
        return result

    def rollback_transaction(self) -> bool:
        if self._active_transaction is None:
            return False
        transaction = self._active_transaction
        self._active_transaction = None
        self._suspend_history = False
        return self.restore_scene_data_for_key(transaction.key, copy.deepcopy(transaction.before))

    def record_scene_change(self, entry: SceneWorkspaceEntry, label: str, before: dict[str, Any]) -> None:
        if self._history is None or self._suspend_history:
            return
        after = self._context.snapshot_scene(entry)
        key = entry.key
        before_snapshot = copy.deepcopy(before)
        self._history.push(
            label=label,
            undo=lambda key=key, before=before_snapshot: self.restore_scene_data_for_key(key, before),
            redo=lambda key=key, after=after: self.restore_scene_data_for_key(key, after),
        )

    def restore_scene_data_for_key(self, key: str, data: dict[str, Any]) -> bool:
        entry = self._context.resolve_entry(key)
        if entry is None or entry.is_playing:
            return False
        try:
            self._context.restore_entry_scene(entry, data)
        except ValueError:
            return False
        entry.dirty = True
        return True

    def _apply_edit_component(self, change: Change) -> bool:
        return self._context.edit_component(change.entity, change.component, change.field, change.value)

    def _apply_set_entity_property(self, change: Change) -> bool:
        return self._context.set_entity_property(change.entity, change.field, change.value)

    def _apply_add_component(self, change: Change) -> bool:
        return self._context.add_component(change.entity, change.component, change.data)

    def _apply_remove_component(self, change: Change) -> bool:
        return self._context.remove_component(change.entity, change.component)

    def _apply_create_entity(self, change: Change) -> bool:
        components = change.data.get("components") if isinstance(change.data, dict) else None
        return self._context.create_entity(change.entity, components)

    def _apply_delete_entity(self, change: Change) -> bool:
        return self._context.delete_entity(change.entity)
