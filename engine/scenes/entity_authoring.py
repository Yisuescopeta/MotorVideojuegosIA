from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Optional

from engine.core.runtime_logging import log_err
from engine.scenes.contracts import (
    PrefabOverridePort,
    SceneHistoryPort,
    SceneSerializableTransactionPort,
)
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry
from engine.serialization.json_value import clone_json_value

if TYPE_CHECKING:
    from engine.levels.component_registry import ComponentRegistry


class SceneEntityAuthoring:
    """Owns serializable entity queries, CRUD, and differential create history."""

    def __init__(
        self,
        workspace: SceneWorkspace,
        pipeline: SceneSerializableTransactionPort,
        projection: SceneProjectionService,
        history: SceneHistoryPort,
        prefab_overrides: PrefabOverridePort,
        flow_policy: SceneFlowPolicy,
        registry: "ComponentRegistry",
    ) -> None:
        self._workspace = workspace
        self._pipeline = pipeline
        self._projection = projection
        self._history = history
        self._prefab_overrides = prefab_overrides
        self._flow_policy = flow_policy
        self._registry = registry

    def find_entity_data_for_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
    ) -> Optional[dict[str, Any]]:
        if not self._pipeline.flush_pending(
            entry,
            failure_context=f"read_entity:{entity_name}",
        ):
            return None
        entity_data = entry.scene.find_entity(entity_name)
        return copy.deepcopy(entity_data) if isinstance(entity_data, dict) else None

    def list_scene_entities(self, entry: SceneWorkspaceEntry) -> list[dict[str, Any]]:
        if not self._pipeline.flush_pending(entry, failure_context="list_scene_entities"):
            return []
        entities: list[dict[str, Any]] = []
        for entity_data in entry.scene.entities_data:
            if not isinstance(entity_data, dict):
                continue
            components = entity_data.get("components", {})
            component_names = sorted(components) if isinstance(components, dict) else []
            entities.append(
                {
                    "name": str(entity_data.get("name", "") or ""),
                    "scene_name": entry.scene.name,
                    "scene_path": entry.source_path,
                    "scene_key": entry.key,
                    "scene_ref": entry.source_path or entry.key,
                    "has_scene_link": "SceneLink" in component_names,
                    "component_names": component_names,
                }
            )
        return entities

    def find_entity_data(self, entity_name: str) -> Optional[dict[str, Any]]:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return None
        return self.find_entity_data_for_entry(entry, entity_name)

    def find_entity_data_by_id(self, entity_id: str) -> Optional[dict[str, Any]]:
        entry = self._workspace.get_active_entry()
        if entry is None or not self._pipeline.flush_pending(
            entry,
            failure_context=f"read_entity_id:{entity_id}",
        ):
            return None
        entity_data = entry.scene.find_entity_by_id(entity_id)
        return copy.deepcopy(entity_data) if isinstance(entity_data, dict) else None

    def update_entity_property(
        self,
        entity_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return False
        label = f"{entity_name}.{property_name}"
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        entity_id = self._workspace.entity_id_for_name(entry, entity_name)
        try:
            changed = entry.scene.update_entity_property(
                entity_name,
                property_name,
                copy.deepcopy(value),
            )
            if not changed:
                changed = self._prefab_overrides.update_entity_property(
                    entry,
                    entity_name,
                    property_name,
                    value,
                )
            if not changed:
                self._pipeline.rollback(entry, token)
                return False
            self._restore_renamed_selection(
                entry,
                entity_name,
                entity_id,
                property_name,
                value,
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

    def update_entity_property_by_id(
        self,
        entity_id: str,
        property_name: str,
        value: Any,
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return False
        entity_name = self._entity_name_by_id_after_flush(
            entry,
            entity_id,
            failure_context=f"update_entity_property_id:{entity_id}",
        )
        if entity_name is None:
            return False
        label = f"{entity_name}.{property_name}"
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, before = transaction
        try:
            changed = entry.scene.update_entity_property_by_id(
                entity_id,
                property_name,
                copy.deepcopy(value),
            )
            if not changed:
                changed = self._prefab_overrides.update_entity_property(
                    entry,
                    entity_name,
                    property_name,
                    value,
                )
            if not changed:
                self._pipeline.rollback(entry, token)
                return False
            self._restore_renamed_selection(
                entry,
                entity_name,
                entity_id,
                property_name,
                value,
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

    def set_entity_groups(self, entity_name: str, groups: list[str]) -> bool:
        return self.update_entity_property(entity_name, "groups", groups)

    def create_entity(
        self,
        name: str,
        components: Optional[dict[str, dict[str, Any]]] = None,
    ) -> bool:
        payload: dict[str, Any] = {
            "name": name,
            "active": True,
            "tag": "Untagged",
            "layer": "Default",
            "parent": None,
            "components": components
            or {
                "Transform": {
                    "enabled": True,
                    "x": 0.0,
                    "y": 0.0,
                    "rotation": 0.0,
                    "scale_x": 1.0,
                    "scale_y": 1.0,
                }
            },
            "component_metadata": {},
        }
        component_payload = payload["components"]
        metadata_payload = payload["component_metadata"]
        if isinstance(component_payload, dict) and isinstance(metadata_payload, dict):
            for component_name in component_payload:
                metadata_payload[component_name] = {
                    "origin": self._registry.get_origin(str(component_name))
                }
        return self._create_entity_payload(payload, f"create_entity:{name}")

    def create_entity_from_data(self, entity_data: dict[str, Any]) -> bool:
        payload = clone_json_value(entity_data)
        payload.setdefault("active", True)
        payload.setdefault("tag", "Untagged")
        payload.setdefault("layer", "Default")
        payload.setdefault("parent", None)
        payload.setdefault("components", {})
        payload.setdefault("component_metadata", {})
        components = payload.get("components", {})
        metadata = payload.get("component_metadata", {})
        if not isinstance(components, dict) or not isinstance(metadata, dict):
            return False
        for component_name in components:
            component_metadata = metadata.setdefault(component_name, {})
            if not isinstance(component_metadata, dict):
                return False
            component_metadata.setdefault(
                "origin",
                self._registry.get_origin(component_name),
            )
        name = str(payload.get("name", "") or "")
        return self._create_entity_payload(payload, f"create_entity:{name}")

    def _create_entity_payload(
        self,
        payload: dict[str, Any],
        label: str,
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, _before = transaction
        try:
            prepared = self._flow_policy.prepare_entity(entry.scene, payload)
            canonical_entity = self._projection.add_entity(
                entry.scene,
                entry.edit_world,
                prepared,
            )
            if canonical_entity is None:
                self._pipeline.rollback(entry, token)
                return False
            if self._flow_policy.entity_has_scene_link(canonical_entity):
                self._workspace.sync_feature_metadata_from_scene_links(entry)
            if not self._pipeline.commit_incremental(
                entry,
                token,
                failure_context=label,
            ):
                return False
        except Exception as exc:
            self._pipeline.rollback(entry, token)
            log_err(f"SceneEntityAuthoring: rejected incremental entity during {label}: {exc}")
            return False
        self._record_entity_create_delta(entry, label, canonical_entity)
        return True

    def _record_entity_create_delta(
        self,
        entry: SceneWorkspaceEntry,
        label: str,
        entity_data: dict[str, Any],
    ) -> None:
        key = entry.key
        payload = clone_json_value(entity_data)
        entity_id = str(entity_data.get("id", "") or "")
        self._history.record_differential_change(
            label=label,
            undo=lambda key=key, entity_id=entity_id: self._remove_entity_create_delta(
                key,
                entity_id,
            ),
            redo=lambda key=key, payload=payload: self._restore_entity_create_delta(
                key,
                payload,
            ),
        )

    def _remove_entity_create_delta(self, key: str, entity_id: str) -> bool:
        entry = self._workspace.resolve_entry(key)
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        if not self._pipeline.flush_pending(
            entry,
            failure_context=f"undo_create_entity_id:{entity_id}",
        ):
            return False
        entity_data = entry.scene.find_entity_by_id(entity_id)
        if entity_data is None:
            return False
        entity_name = str(entity_data.get("name", "") or "")
        had_scene_link = self._flow_policy.entity_has_scene_link(entity_data)
        transaction = self._pipeline.begin(
            entry,
            failure_context=f"undo_create_entity:{entity_name}",
        )
        if transaction is None:
            return False
        token, _before = transaction
        try:
            if not entry.scene.remove_entity_by_id(entity_id):
                self._pipeline.rollback(entry, token)
                return False
            self._projection.remove_entity_from_world(
                entry.edit_world,
                entity_name,
                entity_id,
            )
            if had_scene_link:
                self._workspace.sync_feature_metadata_from_scene_links(entry)
            return self._pipeline.commit_incremental(
                entry,
                token,
                failure_context=f"undo_create_entity:{entity_name}",
            )
        except Exception:
            self._pipeline.rollback(entry, token)
            return False

    def _restore_entity_create_delta(
        self,
        key: str,
        entity_data: dict[str, Any],
    ) -> bool:
        entry = self._workspace.resolve_entry(key)
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        label = f"redo_create_entity:{entity_data.get('name', '')}"
        transaction = self._pipeline.begin(entry, failure_context=label)
        if transaction is None:
            return False
        token, _before = transaction
        try:
            prepared = self._flow_policy.prepare_entity(
                entry.scene,
                clone_json_value(entity_data),
            )
            restored = self._projection.add_entity(
                entry.scene,
                entry.edit_world,
                prepared,
            )
            if restored is None:
                self._pipeline.rollback(entry, token)
                return False
            if self._flow_policy.entity_has_scene_link(restored):
                self._workspace.sync_feature_metadata_from_scene_links(entry)
            return self._pipeline.commit_incremental(
                entry,
                token,
                failure_context=label,
            )
        except Exception:
            self._pipeline.rollback(entry, token)
            return False

    def _entity_name_by_id_after_flush(
        self,
        entry: SceneWorkspaceEntry,
        entity_id: str,
        *,
        failure_context: str,
    ) -> Optional[str]:
        if entry.is_playing or not self._pipeline.flush_pending(
            entry,
            failure_context=failure_context,
        ):
            return None
        entity_data = entry.scene.find_entity_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        return entity_name if isinstance(entity_name, str) else None

    def _restore_renamed_selection(
        self,
        entry: SceneWorkspaceEntry,
        old_name: str,
        entity_id: Optional[str],
        property_name: str,
        value: Any,
    ) -> None:
        if property_name != "name" or not isinstance(value, str):
            return
        selected_matches = (entity_id is not None and entry.selected_entity_id == entity_id) or (
            entry.selected_entity_id is None and entry.selected_entity_name == old_name
        )
        if selected_matches:
            self._workspace.select_entity(
                entry,
                entity_name=value,
                entity_id=entity_id,
            )
