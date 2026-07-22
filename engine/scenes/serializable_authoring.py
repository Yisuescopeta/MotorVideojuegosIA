from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from engine.scenes.component_authoring import SceneComponentAuthoring
from engine.scenes.contracts import PrefabOverridePort, SceneHistoryPort
from engine.scenes.edit_sync import SceneEditSyncCoordinator
from engine.scenes.entity_authoring import SceneEntityAuthoring
from engine.scenes.scene_flow import SceneFlowPolicy
from engine.scenes.scene_projection import SceneProjectionService
from engine.scenes.serializable_mutation import SerializableMutationCoordinator
from engine.scenes.serializable_pipeline import SceneSerializableAuthoringPipeline
from engine.scenes.workspace_lifecycle import SceneWorkspace, SceneWorkspaceEntry

if TYPE_CHECKING:
    from engine.levels.component_registry import ComponentRegistry


class SceneSerializableAuthoring:
    """Compatibility facade over component and entity authoring owners."""

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
        self._pipeline = SceneSerializableAuthoringPipeline(
            workspace,
            edit_sync,
            mutations,
            history,
        )
        self._component_authoring = SceneComponentAuthoring(
            workspace,
            self._pipeline,
            projection,
            prefab_overrides,
            flow_policy,
            registry,
        )
        self._entity_authoring = SceneEntityAuthoring(
            workspace,
            self._pipeline,
            projection,
            history,
            prefab_overrides,
            flow_policy,
            registry,
        )

    @property
    def component_authoring(self) -> SceneComponentAuthoring:
        return self._component_authoring

    @property
    def entity_authoring(self) -> SceneEntityAuthoring:
        return self._entity_authoring

    @property
    def transaction_pipeline(self) -> SceneSerializableAuthoringPipeline:
        return self._pipeline

    def get_feature_metadata(self) -> dict[str, Any]:
        return self._component_authoring.get_feature_metadata()

    def get_component_data(
        self,
        entity_name: str,
        component_name: str,
    ) -> Optional[dict[str, Any]]:
        return self._component_authoring.get_component_data(entity_name, component_name)

    def get_component_data_for_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
    ) -> Optional[dict[str, Any]]:
        return self._component_authoring.get_component_data_for_entry(
            entry,
            entity_name,
            component_name,
        )

    def get_component_metadata(
        self,
        entity_name: str,
        component_name: str,
    ) -> dict[str, Any]:
        return self._component_authoring.get_component_metadata(
            entity_name,
            component_name,
        )

    def upsert_component_for_scene(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        component_data: dict[str, Any],
        *,
        record_history: bool = True,
    ) -> bool:
        return self._component_authoring.upsert_component_for_scene(
            entry,
            entity_name,
            component_name,
            component_data,
            record_history=record_history,
        )

    def remove_component_for_scene(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
        component_name: str,
        *,
        record_history: bool = True,
    ) -> bool:
        return self._component_authoring.remove_component_for_scene(
            entry,
            entity_name,
            component_name,
            record_history=record_history,
        )

    def apply_edit_to_world(
        self,
        entity_name: str,
        component_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        return self._component_authoring.apply_edit_to_world(
            entity_name,
            component_name,
            property_name,
            value,
        )

    def apply_edit_to_world_by_id(
        self,
        entity_id: str,
        component_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        return self._component_authoring.apply_edit_to_world_by_id(
            entity_id,
            component_name,
            property_name,
            value,
        )

    def replace_component_data(
        self,
        entity_name: str,
        component_name: str,
        component_data: dict[str, Any],
    ) -> bool:
        return self._component_authoring.replace_component_data(
            entity_name,
            component_name,
            component_data,
        )

    def replace_component_data_by_id(
        self,
        entity_id: str,
        component_name: str,
        component_data: dict[str, Any],
    ) -> bool:
        return self._component_authoring.replace_component_data_by_id(
            entity_id,
            component_name,
            component_data,
        )

    def add_component_to_entity(
        self,
        entity_name: str,
        component_name: str,
        component_data: Optional[dict[str, Any]] = None,
    ) -> bool:
        return self._component_authoring.add_component_to_entity(
            entity_name,
            component_name,
            component_data,
        )

    def add_component_to_entity_by_id(
        self,
        entity_id: str,
        component_name: str,
        component_data: Optional[dict[str, Any]] = None,
    ) -> bool:
        return self._component_authoring.add_component_to_entity_by_id(
            entity_id,
            component_name,
            component_data,
        )

    def remove_component_from_entity(
        self,
        entity_name: str,
        component_name: str,
    ) -> bool:
        return self._component_authoring.remove_component_from_entity(
            entity_name,
            component_name,
        )

    def remove_component_from_entity_by_id(
        self,
        entity_id: str,
        component_name: str,
    ) -> bool:
        return self._component_authoring.remove_component_from_entity_by_id(
            entity_id,
            component_name,
        )

    def set_component_enabled(
        self,
        entity_name: str,
        component_name: str,
        enabled: bool,
    ) -> bool:
        return self._component_authoring.set_component_enabled(
            entity_name,
            component_name,
            enabled,
        )

    def set_component_metadata(
        self,
        entity_name: str,
        component_name: str,
        metadata: dict[str, Any],
    ) -> bool:
        return self._component_authoring.set_component_metadata(
            entity_name,
            component_name,
            metadata,
        )

    def set_feature_metadata(self, key: str, value: Any) -> bool:
        return self._component_authoring.set_feature_metadata(key, value)

    def set_scene_flow_target(self, key: str, target_path: str) -> bool:
        return self._component_authoring.set_scene_flow_target(key, target_path)

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
        return self._component_authoring.apply_authoring_component_state(
            entry,
            entity_name,
            component_name,
            component_state,
            record_history=record_history,
            label=label,
        )

    def find_entity_data_for_entry(
        self,
        entry: SceneWorkspaceEntry,
        entity_name: str,
    ) -> Optional[dict[str, Any]]:
        return self._entity_authoring.find_entity_data_for_entry(entry, entity_name)

    def list_scene_entities(self, entry: SceneWorkspaceEntry) -> list[dict[str, Any]]:
        return self._entity_authoring.list_scene_entities(entry)

    def find_entity_data(self, entity_name: str) -> Optional[dict[str, Any]]:
        return self._entity_authoring.find_entity_data(entity_name)

    def find_entity_data_by_id(self, entity_id: str) -> Optional[dict[str, Any]]:
        return self._entity_authoring.find_entity_data_by_id(entity_id)

    def update_entity_property(
        self,
        entity_name: str,
        property_name: str,
        value: Any,
    ) -> bool:
        return self._entity_authoring.update_entity_property(
            entity_name,
            property_name,
            value,
        )

    def update_entity_property_by_id(
        self,
        entity_id: str,
        property_name: str,
        value: Any,
    ) -> bool:
        return self._entity_authoring.update_entity_property_by_id(
            entity_id,
            property_name,
            value,
        )

    def set_entity_groups(self, entity_name: str, groups: list[str]) -> bool:
        return self._entity_authoring.set_entity_groups(entity_name, groups)

    def create_entity(
        self,
        name: str,
        components: Optional[dict[str, dict[str, Any]]] = None,
    ) -> bool:
        return self._entity_authoring.create_entity(name, components)

    def create_entity_from_data(self, entity_data: dict[str, Any]) -> bool:
        return self._entity_authoring.create_entity_from_data(entity_data)
