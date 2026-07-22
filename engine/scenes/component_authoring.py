from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Optional

from engine.scenes.contracts import (
    PrefabOverridePort,
    SceneSerializableTransactionPort,
)
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry

if TYPE_CHECKING:
    from engine.levels.component_registry import ComponentRegistry


class SceneComponentAuthoring:
    """Owns serializable component queries, CRUD, metadata, and fallbacks."""

    def __init__(
        self,
        workspace: SceneWorkspace,
        pipeline: SceneSerializableTransactionPort,
        projection: SceneProjectionService,
        prefab_overrides: PrefabOverridePort,
        flow_policy: SceneFlowPolicy,
        registry: "ComponentRegistry",
    ) -> None:
        self._workspace = workspace
        self._pipeline = pipeline
        self._projection = projection
        self._prefab_overrides = prefab_overrides
        self._flow_policy = flow_policy
        self._registry = registry

    def get_feature_metadata(self) -> dict[str, Any]:
        entry = self._workspace.get_active_entry()
        return entry.scene.feature_metadata_view().to_dict() if entry is not None else {}

    def get_component_data(
        self,
        entity_name: str,
        component_name: str,
    ) -> Optional[dict[str, Any]]:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return None
        return self.get_component_data_for_entry(entry, entity_name, component_name)

    def get_component_data_for_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
    ) -> Optional[dict[str, Any]]:
        if not self._pipeline.flush_pending(
            entry,
            failure_context=f"read_component:{entity_name}.{component_name}",
        ):
            return None
        entity_data = entry.scene.find_entity(entity_name)
        if not isinstance(entity_data, dict):
            return None
        components = entity_data.get("components", {})
        component_data = components.get(component_name) if isinstance(components, dict) else None
        return copy.deepcopy(component_data) if isinstance(component_data, dict) else None

    def get_component_metadata(
        self,
        entity_name: str,
        component_name: str,
    ) -> dict[str, Any]:
        entry = self._workspace.get_active_entry()
        if entry is None or not self._pipeline.flush_pending(
            entry,
            failure_context=f"read_metadata:{entity_name}.{component_name}",
        ):
            return {}
        return copy.deepcopy(entry.scene.get_component_metadata(entity_name, component_name))

    def upsert_component_for_scene(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_data: dict[str, Any],
        *,
        record_history: bool = True,
    ) -> bool:
        label = f"{entity_name}.{component_name}"
        transaction = self._pipeline.begin(
            entry,
            failure_context=f"upsert_component:{label}",
        )
        if transaction is None:
            return False
        token, before = transaction
        if entry.scene.find_entity(entity_name) is None:
            self._pipeline.rollback(entry, token)
            return False
        try:
            payload = self._prepare_component(entry, component_name, component_data)
            if not entry.scene.replace_component_data(entity_name, component_name, payload):
                if not entry.scene.add_component(entity_name, component_name, payload):
                    self._pipeline.rollback(entry, token)
                    return False
                if not entry.scene.set_component_metadata(
                    entity_name,
                    component_name,
                    {"origin": self._registry.get_origin(component_name)},
                ):
                    self._pipeline.rollback(entry, token)
                    return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._pipeline.rollback(entry, token)
            return False
        return self._pipeline.commit_snapshot(
            entry,
            token,
            before,
            label=label,
            record_history=(
                record_history and entry.key == self._workspace.active_scene_key
            ),
        )

    def remove_component_for_scene(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        *,
        record_history: bool = True,
    ) -> bool:
        label = f"remove_component:{entity_name}.{component_name}"
        transaction = self._pipeline.begin(
            entry,
            failure_context=label,
        )
        if transaction is None:
            return False
        token, before = transaction
        if entry.scene.find_entity(entity_name) is None:
            self._pipeline.rollback(entry, token)
            return False
        try:
            if not entry.scene.remove_component(entity_name, component_name):
                self._pipeline.rollback(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._pipeline.rollback(entry, token)
            return False
        return self._pipeline.commit_snapshot(
            entry,
            token,
            before,
            label=label,
            record_history=(
                record_history and entry.key == self._workspace.active_scene_key
            ),
        )

    def apply_edit_to_world(
        self,
        entity_name: str,
        component_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None or entry.edit_world is None:
            return False
        label = f"{entity_name}.{component_name}.{property_name}"
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        try:
            changed = entry.scene.update_component(
                entity_name,
                component_name,
                property_name,
                copy.deepcopy(value),
            )
            if not changed:
                changed = self._prefab_overrides.update_component_property(
                    entry,
                    entity_name,
                    component_name,
                    property_name,
                    value,
                )
            if not changed:
                self._pipeline.rollback(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._pipeline.rollback(entry, token)
            return False
        return self._pipeline.commit_snapshot(
            entry,
            token,
            before,
            label=label,
        )

    def replace_component_data(
        self,
        entity_name: str,
        component_name: str,
        component_data: dict[str, Any],
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None or entry.edit_world is None:
            return False
        return self._replace_component_for_entry(
            entry,
            entity_name,
            component_name,
            component_data,
            label=f"{entity_name}.{component_name}",
        )

    def replace_component_data_by_id(
        self,
        entity_id: str,
        component_name: str,
        component_data: dict[str, Any],
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None or entry.edit_world is None:
            return False
        label = f"entity_id:{entity_id}.{component_name}"
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        try:
            if entity_id is not None and entry.scene.find_entity_by_id(entity_id) is None and not self._world_has_entity_id(entry, entity_id):
                self._pipeline.rollback(entry, token)
                return False
            payload = self._prepare_component(entry, component_name, component_data)
            changed = entry.scene.replace_component_data_by_id(
                entity_id,
                component_name,
                payload,
            )
            if not changed:
                replace_by_id = getattr(self._prefab_overrides, "replace_component_by_id", None)
                if callable(replace_by_id):
                    changed = replace_by_id(entry, entity_id, component_name, payload)
            if not changed:
                self._pipeline.rollback(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._pipeline.rollback(entry, token)
            return False
        return self._pipeline.commit_snapshot(
            entry,
            token,
            before,
            label=label,
        )

    def add_component_to_entity(
        self,
        entity_name: str,
        component_name: str,
        component_data: Optional[dict[str, Any]] = None,
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return False
        return self._add_component_for_entry(
            entry,
            entity_name,
            None,
            component_name,
            component_data,
        )

    def add_component_to_entity_by_id(
        self,
        entity_id: str,
        component_name: str,
        component_data: Optional[dict[str, Any]] = None,
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return False
        return self._add_component_for_entry(
            entry,
            None,
            entity_id,
            component_name,
            component_data,
        )

    def remove_component_from_entity(
        self,
        entity_name: str,
        component_name: str,
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return False
        return self._remove_component_for_entry(
            entry,
            entity_name,
            None,
            component_name,
        )

    def remove_component_from_entity_by_id(
        self,
        entity_id: str,
        component_name: str,
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return False
        return self._remove_component_for_entry(
            entry,
            None,
            entity_id,
            component_name,
        )

    def set_component_enabled(
        self,
        entity_name: str,
        component_name: str,
        enabled: bool,
    ) -> bool:
        return self.apply_edit_to_world(
            entity_name,
            component_name,
            "enabled",
            enabled,
        )

    def set_component_metadata(
        self,
        entity_name: str,
        component_name: str,
        metadata: dict[str, Any],
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return False
        label = f"{entity_name}.{component_name}.metadata"
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        try:
            if not entry.scene.set_component_metadata(
                entity_name,
                component_name,
                metadata,
            ):
                self._pipeline.rollback(entry, token)
                return False
        except Exception:
            self._pipeline.rollback(entry, token)
            return False
        return self._pipeline.commit_snapshot(
            entry,
            token,
            before,
            label=label,
        )

    def set_feature_metadata(self, key: str, value: Any) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return False
        label = f"feature_metadata:{key}"
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        try:
            entry.scene.set_feature_metadata(key, copy.deepcopy(value))
        except Exception:
            self._pipeline.rollback(entry, token)
            return False
        return self._pipeline.commit_snapshot(
            entry,
            token,
            before,
            label=label,
        )

    def set_scene_flow_target(self, key: str, target_path: str) -> bool:
        entry = self._workspace.get_active_entry()
        scene_key = str(key).strip()
        if entry is None or not scene_key:
            return False
        label = f"scene_flow:{scene_key}"
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        try:
            self._flow_policy.set_metadata_target(
                entry.scene,
                scene_key,
                target_path,
            )
        except Exception:
            self._pipeline.rollback(entry, token)
            return False
        return self._pipeline.commit_snapshot(
            entry,
            token,
            before,
            label=label,
        )

    def apply_authoring_component_state(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_state: dict[str, Any],
        *,
        record_history: bool,
        label: str,
    ) -> bool:
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        current_state = self._load_authoring_component_state(
            entry,
            entity_name,
            component_name,
        )
        if current_state is None:
            self._pipeline.rollback(entry, token)
            return False
        updated_state = copy.deepcopy(current_state)
        updated_state.update(copy.deepcopy(component_state))
        try:
            self._workspace.select_entity(entry, entity_name=entity_name)
            payload = self._prepare_component(entry, component_name, updated_state)
            changed = entry.scene.replace_component_data(
                entity_name,
                component_name,
                payload,
            )
            if not changed:
                changed = self._prefab_overrides.replace_component(
                    entry,
                    entity_name,
                    component_name,
                    payload,
                )
            if not changed:
                self._pipeline.rollback(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._pipeline.rollback(entry, token)
            return False
        return self._pipeline.commit_snapshot(
            entry,
            token,
            before,
            label=label,
            record_history=record_history,
        )

    def _replace_component_for_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_data: dict[str, Any],
        *,
        label: str,
    ) -> bool:
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        try:
            payload = self._prepare_component(entry, component_name, component_data)
            changed = entry.scene.replace_component_data(
                entity_name,
                component_name,
                payload,
            )
            if not changed:
                changed = self._prefab_overrides.replace_component(
                    entry,
                    entity_name,
                    component_name,
                    payload,
                )
            if not changed:
                self._pipeline.rollback(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._pipeline.rollback(entry, token)
            return False
        return self._pipeline.commit_snapshot(
            entry,
            token,
            before,
            label=label,
        )

    def _add_component_for_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: Optional[str],
        entity_id: Optional[str],
        component_name: str,
        component_data: Optional[dict[str, Any]],
    ) -> bool:
        target_label = entity_name or f"entity_id:{entity_id}"
        label = f"add_component:{target_label}.{component_name}"
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        try:
            if entity_id is not None and entry.scene.find_entity_by_id(entity_id) is None and not self._world_has_entity_id(entry, entity_id):
                self._pipeline.rollback(entry, token)
                return False
            payload = self._prepare_component(
                entry,
                component_name,
                component_data or {"enabled": True},
            )
            changed_directly = (
                entry.scene.add_component_by_id(entity_id, component_name, payload)
                if entity_id is not None
                else entry.scene.add_component(entity_name, component_name, payload)
            )
            changed = changed_directly
            if not changed_directly and entity_name is not None:
                changed = self._prefab_overrides.replace_component(
                    entry,
                    entity_name,
                    component_name,
                    payload,
                )
            if not changed and entity_id is not None:
                replace_by_id = getattr(self._prefab_overrides, "replace_component_by_id", None)
                if callable(replace_by_id):
                    changed = replace_by_id(entry, entity_id, component_name, payload)
            if not changed:
                self._pipeline.rollback(entry, token)
                return False
            if changed_directly:
                metadata = {"origin": self._registry.get_origin(component_name)}
                metadata_changed = (
                    entry.scene.set_component_metadata_by_id(entity_id, component_name, metadata)
                    if entity_id is not None
                    else entry.scene.set_component_metadata(entity_name, component_name, metadata)
                )
                if not metadata_changed:
                    self._pipeline.rollback(entry, token)
                    return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._pipeline.rollback(entry, token)
            return False
        return self._pipeline.commit_snapshot(
            entry,
            token,
            before,
            label=label,
        )

    def _remove_component_for_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: Optional[str],
        entity_id: Optional[str],
        component_name: str,
    ) -> bool:
        target_label = entity_name or f"entity_id:{entity_id}"
        label = f"remove_component:{target_label}.{component_name}"
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        try:
            if entity_id is not None and entry.scene.find_entity_by_id(entity_id) is None and not self._world_has_entity_id(entry, entity_id):
                self._pipeline.rollback(entry, token)
                return False
            changed = (
                entry.scene.remove_component_by_id(entity_id, component_name)
                if entity_id is not None
                else entry.scene.remove_component(entity_name, component_name)
            )
            if not changed and entity_name is not None:
                changed = self._prefab_overrides.remove_component(
                    entry,
                    entity_name,
                    component_name,
                )
            if not changed and entity_id is not None:
                remove_by_id = getattr(self._prefab_overrides, "remove_component_by_id", None)
                if callable(remove_by_id):
                    changed = remove_by_id(entry, entity_id, component_name)
            if not changed:
                self._pipeline.rollback(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._pipeline.rollback(entry, token)
            return False
        return self._pipeline.commit_snapshot(
            entry,
            token,
            before,
            label=label,
        )

    def apply_edit_to_world_by_id(
        self,
        entity_id: str,
        component_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None or entry.edit_world is None:
            return False
        label = f"entity_id:{entity_id}.{component_name}.{property_name}"
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        try:
            if entry.scene.find_entity_by_id(entity_id) is None and not self._world_has_entity_id(entry, entity_id):
                self._pipeline.rollback(entry, token)
                return False
            changed = entry.scene.update_component_by_id(
                entity_id,
                component_name,
                property_name,
                copy.deepcopy(value),
            )
            if not changed:
                update_by_id = getattr(self._prefab_overrides, "update_component_property_by_id", None)
                if callable(update_by_id):
                    changed = update_by_id(
                        entry,
                        entity_id,
                        component_name,
                        property_name,
                        value,
                    )
            if not changed:
                self._pipeline.rollback(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._pipeline.rollback(entry, token)
            return False
        return self._pipeline.commit_snapshot(entry, token, before, label=label)

    def _load_authoring_component_state(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
    ) -> Optional[dict[str, Any]]:
        entity_data = entry.scene.find_entity(entity_name)
        if entity_data is not None:
            components = entity_data.get("components", {})
            component_data = components.get(component_name) if isinstance(components, dict) else None
            if isinstance(component_data, dict):
                return copy.deepcopy(component_data)
        if entry.edit_world is None:
            return None
        entity = entry.edit_world.get_entity_by_name(entity_name)
        if entity is None:
            return None
        component_class = self._registry.get(component_name)
        component = entity.get_component(component_class) if component_class is not None else None
        if component is None or not hasattr(component, "to_dict"):
            return None
        component_data = component.to_dict()
        return copy.deepcopy(component_data) if isinstance(component_data, dict) else None

    @staticmethod
    def _world_has_entity_id(entry: SceneWorkspaceEntry, entity_id: str) -> bool:
        return (
            entry.edit_world is not None
            and entry.edit_world.get_entity_by_serialized_id(entity_id) is not None
        )

    def _prepare_component(
        self,
        entry: SceneWorkspaceEntry,
        component_name: str,
        component_data: dict[str, Any],
    ) -> dict[str, Any]:
        payload = (
            self._flow_policy.prepare_component(entry.scene, component_data)
            if component_name == "SceneLink"
            else copy.deepcopy(component_data)
        )
        return self._projection.canonicalize_component_payload(
            component_name,
            payload,
        )

    def _sync_scene_link(
        self,
        entry: SceneWorkspaceEntry,
        component_name: str,
    ) -> None:
        if component_name == "SceneLink":
            self._flow_policy.sync_metadata_from_links(entry.scene)
