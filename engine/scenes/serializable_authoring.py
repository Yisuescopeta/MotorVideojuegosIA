from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, Optional

from engine.core.runtime_logging import log_err
from engine.scenes.contracts import PrefabOverridePort, SceneHistoryPort
from engine.scenes.edit_sync import SceneEditSyncCoordinator
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.serializable_mutation import SerializableMutationCoordinator
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry
from engine.serialization.json_value import clone_json_value

if TYPE_CHECKING:
    from engine.levels.component_registry import ComponentRegistry


class SceneSerializableAuthoring:
    """General serializable authoring outside incremental and structural edits."""

    def __init__(
        self,
        workspace: SceneWorkspace,
        edit_sync: SceneEditSyncCoordinator,
        mutations: SerializableMutationCoordinator,
        projection: SceneProjectionService,
        history: SceneHistoryPort,
        prefab_overrides: PrefabOverridePort,
        flow_policy: SceneFlowPolicy,
        registry: "ComponentRegistry",
    ) -> None:
        self._workspace = workspace
        self._edit_sync = edit_sync
        self._mutations = mutations
        self._projection = projection
        self._history = history
        self._prefab_overrides = prefab_overrides
        self._flow_policy = flow_policy
        self._registry = registry

    def get_feature_metadata(self) -> dict[str, Any]:
        entry = self._workspace.get_active_entry()
        return copy.deepcopy(entry.scene.feature_metadata) if entry is not None else {}

    def get_component_data(
        self,
        entity_name: str,
        component_name: str,
    ) -> Optional[dict[str, Any]]:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return None
        return self.get_component_data_for_entry(entry, entity_name, component_name)

    def find_entity_data_for_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
    ) -> Optional[dict[str, Any]]:
        if not self._edit_sync.flush_pending(
            entry,
            failure_context=f"read_entity:{entity_name}",
        ):
            return None
        entity_data = entry.scene.find_entity(entity_name)
        return copy.deepcopy(entity_data) if isinstance(entity_data, dict) else None

    def get_component_data_for_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
    ) -> Optional[dict[str, Any]]:
        entity_data = self.find_entity_data_for_entry(entry, entity_name)
        if entity_data is None:
            return None
        components = entity_data.get("components", {})
        component_data = components.get(component_name) if isinstance(components, dict) else None
        return copy.deepcopy(component_data) if isinstance(component_data, dict) else None

    def list_scene_entities(self, entry: SceneWorkspaceEntry) -> list[dict[str, Any]]:
        if not self._edit_sync.flush_pending(entry, failure_context="list_scene_entities"):
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
        if entry is None or not self._edit_sync.flush_pending(
            entry,
            failure_context=f"read_entity_id:{entity_id}",
        ):
            return None
        entity_data = entry.scene.find_entity_by_id(entity_id)
        return copy.deepcopy(entity_data) if isinstance(entity_data, dict) else None

    def get_component_metadata(
        self,
        entity_name: str,
        component_name: str,
    ) -> dict[str, Any]:
        entry = self._workspace.get_active_entry()
        if entry is None or not self._edit_sync.flush_pending(
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
        if entry.is_playing or entry.scene.find_entity(entity_name) is None:
            return False
        captured = self._capture_after_flush(
            entry,
            f"upsert_component:{entity_name}.{component_name}",
        )
        if captured is None:
            return False
        token, before = captured
        try:
            payload = self._prepare_component(entry, component_name, component_data)
            if not entry.scene.replace_component_data(entity_name, component_name, payload):
                if not entry.scene.add_component(entity_name, component_name, payload):
                    self._mutations.restore_snapshot(entry, token)
                    return False
                if not entry.scene.set_component_metadata(
                    entity_name,
                    component_name,
                    {"origin": self._registry.get_origin(component_name)},
                ):
                    self._mutations.restore_snapshot(entry, token)
                    return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        if not self._mutations.commit_mutation(
            entry,
            token,
            failure_context=f"upsert_component:{entity_name}.{component_name}",
        ):
            return False
        self._workspace.mark_dirty(entry)
        if record_history and entry.key == self._workspace.active_scene_key:
            self._history.record_scene_change(
                entry,
                f"{entity_name}.{component_name}",
                before,
            )
        return True

    def remove_component_for_scene(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        *,
        record_history: bool = True,
    ) -> bool:
        if entry.is_playing or entry.scene.find_entity(entity_name) is None:
            return False
        captured = self._capture_after_flush(
            entry,
            f"remove_component:{entity_name}.{component_name}",
        )
        if captured is None:
            return False
        token, before = captured
        try:
            if not entry.scene.remove_component(entity_name, component_name):
                self._mutations.restore_snapshot(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        if not self._mutations.commit_mutation(
            entry,
            token,
            failure_context=f"remove_component:{entity_name}.{component_name}",
        ):
            return False
        self._workspace.mark_dirty(entry)
        if record_history and entry.key == self._workspace.active_scene_key:
            self._history.record_scene_change(
                entry,
                f"remove_component:{entity_name}.{component_name}",
                before,
            )
        return True

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
        captured = self._capture_after_flush(entry, label)
        if captured is None:
            return False
        token, before = captured
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
                self._mutations.restore_snapshot(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        return self._commit_recorded(entry, token, before, label)

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
        captured = self._capture_after_flush(entry, label)
        if captured is None:
            return False
        token, before = captured
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
                self._mutations.restore_snapshot(entry, token)
                return False
            self._restore_renamed_selection(
                entry,
                entity_name,
                entity_id,
                property_name,
                value,
            )
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        return self._commit_recorded(entry, token, before, label)

    def update_entity_property_by_id(
        self,
        entity_id: str,
        property_name: str,
        value: Any,
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return False
        entity_data = entry.scene.find_entity_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        if not isinstance(entity_name, str):
            return False
        label = f"{entity_name}.{property_name}"
        captured = self._capture_after_flush(entry, label)
        if captured is None:
            return False
        token, before = captured
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
                self._mutations.restore_snapshot(entry, token)
                return False
            self._restore_renamed_selection(
                entry,
                entity_name,
                entity_id,
                property_name,
                value,
            )
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        return self._commit_recorded(entry, token, before, label)

    def set_entity_groups(self, entity_name: str, groups: list[str]) -> bool:
        return self.update_entity_property(entity_name, "groups", groups)

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
        entity_data = entry.scene.find_entity_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        if not isinstance(entity_name, str):
            return False
        label = f"{entity_name}.{component_name}"
        captured = self._capture_after_flush(entry, label)
        if captured is None:
            return False
        token, before = captured
        try:
            payload = self._prepare_component(entry, component_name, component_data)
            changed = entry.scene.replace_component_data_by_id(
                entity_id,
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
                self._mutations.restore_snapshot(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        return self._commit_recorded(entry, token, before, label)

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
        entity_data = entry.scene.find_entity_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        if not isinstance(entity_name, str):
            return False
        return self._add_component_for_entry(
            entry,
            entity_name,
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
        entity_data = entry.scene.find_entity_by_id(entity_id)
        entity_name = entity_data.get("name") if isinstance(entity_data, dict) else None
        if not isinstance(entity_name, str):
            return False
        return self._remove_component_for_entry(
            entry,
            entity_name,
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
        captured = self._capture_after_flush(entry, label)
        if captured is None:
            return False
        token, before = captured
        try:
            if not entry.scene.set_component_metadata(
                entity_name,
                component_name,
                metadata,
            ):
                self._mutations.restore_snapshot(entry, token)
                return False
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        return self._commit_recorded(entry, token, before, label)

    def set_feature_metadata(self, key: str, value: Any) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None:
            return False
        label = f"feature_metadata:{key}"
        captured = self._capture_after_flush(entry, label)
        if captured is None:
            return False
        token, before = captured
        try:
            entry.scene.set_feature_metadata(key, copy.deepcopy(value))
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        return self._commit_recorded(entry, token, before, label)

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
                metadata_payload[component_name] = {"origin": self._registry.get_origin(str(component_name))}
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
        captured = self._capture_after_flush(entry, label)
        if captured is None:
            return False
        token, before = captured
        current_state = self._load_authoring_component_state(
            entry,
            entity_name,
            component_name,
        )
        if current_state is None:
            self._mutations.restore_snapshot(entry, token)
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
                self._mutations.restore_snapshot(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        if not self._mutations.commit_mutation(
            entry,
            token,
            failure_context=label,
        ):
            return False
        self._workspace.mark_dirty(entry)
        if record_history:
            self._history.record_scene_change(entry, label, before)
        return True

    def _replace_component_for_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_data: dict[str, Any],
        *,
        label: str,
    ) -> bool:
        captured = self._capture_after_flush(entry, label)
        if captured is None:
            return False
        token, before = captured
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
                self._mutations.restore_snapshot(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        return self._commit_recorded(entry, token, before, label)

    def _add_component_for_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        entity_id: Optional[str],
        component_name: str,
        component_data: Optional[dict[str, Any]],
    ) -> bool:
        label = f"add_component:{entity_name}.{component_name}"
        captured = self._capture_after_flush(entry, label)
        if captured is None:
            return False
        token, before = captured
        try:
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
            if not changed_directly:
                changed = self._prefab_overrides.replace_component(
                    entry,
                    entity_name,
                    component_name,
                    payload,
                )
            if not changed:
                self._mutations.restore_snapshot(entry, token)
                return False
            if changed_directly and not entry.scene.set_component_metadata(
                entity_name,
                component_name,
                {"origin": self._registry.get_origin(component_name)},
            ):
                self._mutations.restore_snapshot(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        return self._commit_recorded(entry, token, before, label)

    def _remove_component_for_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        entity_id: Optional[str],
        component_name: str,
    ) -> bool:
        label = f"remove_component:{entity_name}.{component_name}"
        captured = self._capture_after_flush(entry, label)
        if captured is None:
            return False
        token, before = captured
        try:
            changed = (
                entry.scene.remove_component_by_id(entity_id, component_name)
                if entity_id is not None
                else entry.scene.remove_component(entity_name, component_name)
            )
            if not changed:
                changed = self._prefab_overrides.remove_component(
                    entry,
                    entity_name,
                    component_name,
                )
            if not changed:
                self._mutations.restore_snapshot(entry, token)
                return False
            self._sync_scene_link(entry, component_name)
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        return self._commit_recorded(entry, token, before, label)

    def _create_entity_payload(
        self,
        payload: dict[str, Any],
        label: str,
    ) -> bool:
        entry = self._workspace.get_active_entry()
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        if not self._edit_sync.flush_pending(entry, failure_context=label):
            return False
        token = self._mutations.capture_snapshot(entry)
        try:
            prepared = self._flow_policy.prepare_entity(entry.scene, payload)
            canonical_entity = self._projection.add_entity(
                entry.scene,
                entry.edit_world,
                prepared,
            )
            if canonical_entity is None:
                self._mutations.restore_snapshot(entry, token)
                return False
            if self._flow_policy.entity_has_scene_link(canonical_entity):
                self._workspace.sync_feature_metadata_from_scene_links(entry)
            if not self._mutations.commit_incremental_entity_mutation(
                entry,
                token,
                failure_context=label,
            ):
                return False
        except Exception as exc:
            self._mutations.restore_snapshot(entry, token)
            log_err(f"SceneSerializableAuthoring: rejected incremental entity during {label}: {exc}")
            return False
        self._workspace.mark_dirty(entry)
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
        entity_data = entry.scene.find_entity_by_id(entity_id)
        if entity_data is None:
            return False
        entity_name = str(entity_data.get("name", "") or "")
        had_scene_link = self._flow_policy.entity_has_scene_link(entity_data)
        token = self._mutations.capture_snapshot(entry)
        try:
            if not entry.scene.remove_entity_by_id(entity_id):
                self._mutations.restore_snapshot(entry, token)
                return False
            self._projection.remove_entity_from_world(
                entry.edit_world,
                entity_name,
                entity_id,
            )
            if had_scene_link:
                self._workspace.sync_feature_metadata_from_scene_links(entry)
            if not self._mutations.commit_incremental_entity_mutation(
                entry,
                token,
                failure_context=f"undo_create_entity:{entity_name}",
            ):
                return False
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        self._workspace.mark_dirty(entry)
        return True

    def _restore_entity_create_delta(
        self,
        key: str,
        entity_data: dict[str, Any],
    ) -> bool:
        entry = self._workspace.resolve_entry(key)
        if entry is None or entry.is_playing or entry.edit_world is None:
            return False
        label = f"redo_create_entity:{entity_data.get('name', '')}"
        token = self._mutations.capture_snapshot(entry)
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
                self._mutations.restore_snapshot(entry, token)
                return False
            if self._flow_policy.entity_has_scene_link(restored):
                self._workspace.sync_feature_metadata_from_scene_links(entry)
            if not self._mutations.commit_incremental_entity_mutation(
                entry,
                token,
                failure_context=label,
            ):
                return False
        except Exception:
            self._mutations.restore_snapshot(entry, token)
            return False
        self._workspace.mark_dirty(entry)
        return True

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

    def _capture_after_flush(
        self,
        entry: SceneWorkspaceEntry,
        failure_context: str,
    ) -> Optional[tuple[object, dict[str, Any]]]:
        if entry.is_playing or not self._edit_sync.flush_pending(
            entry,
            failure_context=failure_context,
        ):
            return None
        token = self._mutations.capture_snapshot(entry)
        return token, self._mutations.snapshot_scene_data(token)

    def _commit_recorded(
        self,
        entry: SceneWorkspaceEntry,
        token: object,
        before: dict[str, Any],
        label: str,
    ) -> bool:
        if not self._mutations.commit_mutation(
            entry,
            token,
            failure_context=label,
        ):
            return False
        self._workspace.mark_dirty(entry)
        self._history.record_scene_change(entry, label, before)
        return True

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
            self._workspace.sync_feature_metadata_from_scene_links(entry)

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
