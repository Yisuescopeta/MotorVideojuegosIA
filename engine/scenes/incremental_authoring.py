from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable

from engine.components.recttransform import RectTransform
from engine.components.transform import Transform
from engine.scenes.contracts import SceneHistoryPort
from engine.scenes.edit_sync import SceneEditSyncCoordinator
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry

_EDITABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "Transform": ("x", "y", "rotation", "scale_x", "scale_y"),
    "RectTransform": (
        "anchored_x",
        "anchored_y",
        "width",
        "height",
        "rotation",
        "scale_x",
        "scale_y",
    ),
}


@dataclass
class AuthoringComponentDelta:
    entity_name: str
    component_name: str
    old_properties: dict[str, Any] = field(default_factory=dict)
    new_properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthoringTransactionState:
    label: str
    key: str
    changes: dict[tuple[str, str], AuthoringComponentDelta] = field(default_factory=dict)


class SceneIncrementalAuthoring:
    """Edits existing Transform projections without rebuilding the scene."""

    def __init__(
        self,
        workspace: SceneWorkspace,
        edit_sync: SceneEditSyncCoordinator,
        history: SceneHistoryPort,
    ) -> None:
        self._workspace = workspace
        self._edit_sync = edit_sync
        self._history = history
        self._transaction: AuthoringTransactionState | None = None

    @staticmethod
    def supports(component_name: str, property_name: str) -> bool:
        fields = _EDITABLE_FIELDS.get(component_name)
        return fields is not None and property_name in fields

    @staticmethod
    def normalize_state(
        component_name: str,
        component_state: dict[str, Any],
    ) -> dict[str, float]:
        fields = _EDITABLE_FIELDS.get(component_name)
        if fields is None:
            return {}
        return {
            field_name: float(component_state[field_name])
            for field_name in fields
            if field_name in component_state
        }

    @staticmethod
    def can_apply(
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
    ) -> bool:
        if entry.is_playing or component_name not in _EDITABLE_FIELDS:
            return False
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is None:
            return False
        component_data = entity_data.get("components", {}).get(component_name)
        return isinstance(component_data, dict)

    def apply_state(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_state: dict[str, Any],
        *,
        record_history: bool,
        label: str,
    ) -> bool:
        if not self.can_apply(entry, entity_name, component_name):
            return False
        old_properties, new_properties = self._apply_properties_to_entry(
            entry,
            entity_name,
            component_name,
            component_state,
        )
        if not new_properties:
            return True
        if self._record_transaction_delta(
            entry,
            entity_name,
            component_name,
            old_properties,
            new_properties,
        ):
            return True
        if record_history:
            key = entry.key
            old_snapshot = copy.deepcopy(old_properties)
            new_snapshot = copy.deepcopy(new_properties)

            def undo() -> bool:
                return self._apply_history_delta(
                    key,
                    entity_name,
                    component_name,
                    old_snapshot,
                )

            def redo() -> bool:
                return self._apply_history_delta(
                    key,
                    entity_name,
                    component_name,
                    new_snapshot,
                )

            undo_action: Callable[[], bool] = undo
            redo_action: Callable[[], bool] = redo
            self._history.record_differential_change(
                label=label,
                undo=undo_action,
                redo=redo_action,
            )
        return True

    def begin_transaction(self, entry: SceneWorkspaceEntry, label: str) -> bool:
        if entry.is_playing or self._transaction is not None:
            return False
        self._transaction = AuthoringTransactionState(
            label=str(label or "authoring_transaction"),
            key=entry.key,
        )
        return True

    def update_transaction(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_state: dict[str, Any],
    ) -> bool:
        transaction = self._transaction
        if transaction is None or entry.key != transaction.key:
            return False
        return self.apply_state(
            entry,
            entity_name,
            component_name,
            component_state,
            record_history=True,
            label=transaction.label,
        )

    def commit_transaction(self) -> dict[str, Any] | None:
        transaction = self._transaction
        if transaction is None:
            return None
        self._transaction = None
        changes = [
            copy.deepcopy(delta)
            for delta in transaction.changes.values()
            if delta.old_properties != delta.new_properties
        ]
        if changes:
            key = transaction.key
            undo_changes = copy.deepcopy(changes)
            redo_changes = copy.deepcopy(changes)

            def undo() -> bool:
                return self._apply_transaction_deltas(
                    key,
                    undo_changes,
                    use_old=True,
                )

            def redo() -> bool:
                return self._apply_transaction_deltas(
                    key,
                    redo_changes,
                    use_old=False,
                )

            undo_action: Callable[[], bool] = undo
            redo_action: Callable[[], bool] = redo
            self._history.record_differential_change(
                label=transaction.label,
                undo=undo_action,
                redo=redo_action,
            )
        return {
            "label": transaction.label,
            "scene_key": transaction.key,
            "changed_component_count": len(changes),
        }

    def cancel_transaction(self) -> bool:
        transaction = self._transaction
        if transaction is None:
            return False
        self._transaction = None
        return self._apply_transaction_deltas(
            transaction.key,
            list(transaction.changes.values()),
            use_old=True,
        )

    def _apply_history_delta(
        self,
        key: str,
        entity_name: str,
        component_name: str,
        properties: dict[str, Any],
    ) -> bool:
        entry = self._workspace.resolve_entry(key)
        if entry is None or not self.can_apply(entry, entity_name, component_name):
            return False
        self._apply_properties_to_entry(
            entry,
            entity_name,
            component_name,
            properties,
        )
        return True

    def _apply_properties_to_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_state: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is None:
            return {}, {}
        component_data = entity_data.get("components", {}).get(component_name)
        if not isinstance(component_data, dict):
            return {}, {}

        old_properties: dict[str, Any] = {}
        new_properties: dict[str, Any] = {}
        for field_name, value in self.normalize_state(
            component_name,
            component_state,
        ).items():
            previous = component_data.get(field_name)
            if previous == value:
                continue
            old_properties[field_name] = previous
            new_properties[field_name] = value

        if not new_properties:
            return old_properties, new_properties
        if not entry.scene.update_component_properties(
            entity_name,
            component_name,
            new_properties,
        ):
            return {}, {}
        self._workspace.select_entity(entry, entity_name=entity_name)
        self._workspace.mark_dirty(entry)
        self._edit_sync.clear_pending(entry)
        self._apply_properties_to_edit_world(
            entry,
            entity_name,
            component_name,
            component_data,
        )
        if entry.edit_world is not None:
            self._workspace.install_entry_state(entry, entry.scene, entry.edit_world)
        return old_properties, new_properties

    def _record_transaction_delta(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        old_properties: dict[str, Any],
        new_properties: dict[str, Any],
    ) -> bool:
        transaction = self._transaction
        if transaction is None or transaction.key != entry.key:
            return False
        delta_key = (entity_name, component_name)
        delta = transaction.changes.get(delta_key)
        if delta is None:
            delta = AuthoringComponentDelta(
                entity_name=entity_name,
                component_name=component_name,
            )
            transaction.changes[delta_key] = delta
        for field_name, old_value in old_properties.items():
            if field_name not in delta.old_properties:
                delta.old_properties[field_name] = old_value
            delta.new_properties[field_name] = new_properties[field_name]
            if delta.new_properties[field_name] == delta.old_properties[field_name]:
                delta.old_properties.pop(field_name, None)
                delta.new_properties.pop(field_name, None)
        if not delta.new_properties:
            transaction.changes.pop(delta_key, None)
        return True

    def _apply_transaction_deltas(
        self,
        key: str,
        changes: list[AuthoringComponentDelta],
        *,
        use_old: bool,
    ) -> bool:
        entry = self._workspace.resolve_entry(key)
        if entry is None:
            return False
        for delta in changes:
            if not self.can_apply(entry, delta.entity_name, delta.component_name):
                return False
            properties = delta.old_properties if use_old else delta.new_properties
            self._apply_properties_to_entry(
                entry,
                delta.entity_name,
                delta.component_name,
                properties,
            )
        return True

    def _apply_properties_to_edit_world(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        properties: dict[str, Any],
    ) -> None:
        if entry.edit_world is None:
            return
        entity = entry.edit_world.get_entity_by_name(entity_name)
        if entity is None:
            return
        if component_name == "Transform":
            transform = entity.get_component(Transform)
            if transform is None:
                return
            field_to_attribute = {
                "x": "local_x",
                "y": "local_y",
                "rotation": "local_rotation",
                "scale_x": "local_scale_x",
                "scale_y": "local_scale_y",
            }
            changed = False
            for field_name, value in properties.items():
                attribute = field_to_attribute.get(field_name)
                if attribute is None:
                    continue
                next_value = float(value)
                if getattr(transform, attribute) == next_value:
                    continue
                setattr(transform, attribute, next_value)
                changed = True
            if changed:
                entry.edit_world.touch_transform()
            return
        if component_name != "RectTransform":
            return
        rect_transform = entity.get_component(RectTransform)
        if rect_transform is None:
            return
        changed = False
        for field_name, value in properties.items():
            if field_name not in _EDITABLE_FIELDS["RectTransform"]:
                continue
            next_value = float(value)
            if getattr(rect_transform, field_name) == next_value:
                continue
            setattr(rect_transform, field_name, next_value)
            changed = True
        if changed:
            entry.edit_world.touch_ui_layout()
