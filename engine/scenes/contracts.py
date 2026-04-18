from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Protocol

if TYPE_CHECKING:
    from engine.authoring.changes import Change
    from engine.ecs.world import World
    from engine.scenes.scene import Scene
    from engine.scenes.scene_manager import SceneManager
    from engine.scenes.workspace_lifecycle import SceneWorkspaceEntry


class SceneRuntimePort(Protocol):
    @property
    def current_scene(self) -> Optional["Scene"]:
        ...

    @property
    def active_world(self) -> Optional["World"]:
        ...

    def enter_play(self) -> Optional["World"]:
        ...

    def exit_play(self) -> Optional["World"]:
        ...


class SceneAuthoringPort(Protocol):
    def begin_transaction(self, label: str = "transaction", key: Optional[str] = None) -> bool:
        ...

    def apply_change(self, change: "Change | dict[str, Any]", key: Optional[str] = None) -> bool:
        ...

    def commit_transaction(self) -> Optional[Dict[str, Any]]:
        ...

    def rollback_transaction(self) -> bool:
        ...

    def create_entity(self, name: str, components: Optional[Dict[str, Dict[str, Any]]] = None) -> bool:
        ...

    def create_entity_from_data(self, entity_data: Dict[str, Any]) -> bool:
        ...

    def remove_entity(self, entity_name: str) -> bool:
        ...

    def add_component_to_entity(
        self,
        entity_name: str,
        component_name: str,
        component_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        ...

    def remove_component_from_entity(self, entity_name: str, component_name: str) -> bool:
        ...

    def apply_edit_to_world(self, entity_name: str, component_name: str, property_name: str, value: Any) -> bool:
        ...

    def update_entity_property(self, entity_name: str, property_name: str, value: Any) -> bool:
        ...

    def replace_component_data(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        ...

    def find_entity_data(self, entity_name: str) -> Optional[Dict[str, Any]]:
        ...

    def get_component_data(self, entity_name: str, component_name: str) -> Optional[Dict[str, Any]]:
        ...

    def get_feature_metadata(self) -> Dict[str, Any]:
        ...

    def set_feature_metadata(self, key: str, value: Any) -> bool:
        ...

    def set_entity_parent(self, entity_name: str, parent_name: Optional[str]) -> bool:
        ...

    def create_child_entity(
        self,
        parent_name: str,
        name: str,
        components: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> bool:
        ...

    def instantiate_prefab(
        self,
        name: str,
        prefab_path: str,
        parent: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
        root_name: Optional[str] = None,
    ) -> bool:
        ...

    def create_prefab(
        self,
        entity_name: str,
        path: str,
        replace_original: bool = False,
        instance_name: Optional[str] = None,
        prefab_locator: Optional[str] = None,
    ) -> bool:
        ...

    def unpack_prefab(self, entity_name: str) -> bool:
        ...

    def apply_prefab_overrides(self, entity_name: str) -> bool:
        ...


class SceneWorkspacePort(Protocol):
    @property
    def active_scene_key(self) -> str:
        ...

    def list_open_scenes(self) -> list[Dict[str, Any]]:
        ...

    def get_active_scene_summary(self) -> Dict[str, Any]:
        ...

    def resolve_entry(self, key_or_path: Optional[str]) -> Optional["SceneWorkspaceEntry"]:
        ...

    def ensure_scene_open(self, scene_ref: str, activate: bool = False) -> Optional["SceneWorkspaceEntry"]:
        ...

    def load_scene(
        self,
        data: Dict[str, Any],
        source_path: Optional[str] = None,
        activate: bool = True,
    ) -> "World":
        ...

    def load_scene_from_file(self, path: str, activate: bool = True) -> Optional["World"]:
        ...

    def activate_scene(self, key_or_path: str) -> Optional["World"]:
        ...

    def close_scene(self, key_or_path: str, discard_changes: bool = False) -> bool:
        ...

    def save_scene_to_file(self, path: str, key: Optional[str] = None) -> bool:
        ...

    def get_feature_metadata(self) -> Dict[str, Any]:
        ...

    def get_scene_flow(self) -> Dict[str, str]:
        ...

    def set_scene_flow_target(self, key: str, target_path: str) -> bool:
        ...

    def copy_entity_subtree(self, entity_name: str) -> bool:
        ...

    def paste_copied_entities(self, target_scene_key: Optional[str] = None) -> bool:
        ...


class _SceneManagerAdapter:
    def __init__(self, manager: "SceneManager") -> None:
        self._manager = manager


class SceneManagerRuntimeAdapter(_SceneManagerAdapter):
    @property
    def current_scene(self) -> Optional["Scene"]:
        return self._manager.current_scene

    @property
    def active_world(self) -> Optional["World"]:
        return self._manager.active_world

    def enter_play(self) -> Optional["World"]:
        return self._manager.enter_play()

    def exit_play(self) -> Optional["World"]:
        return self._manager.exit_play()


class SceneManagerAuthoringAdapter(_SceneManagerAdapter):
    def begin_transaction(self, label: str = "transaction", key: Optional[str] = None) -> bool:
        return self._manager.begin_transaction(label=label, key=key)

    def apply_change(self, change: "Change | dict[str, Any]", key: Optional[str] = None) -> bool:
        return self._manager.apply_change(change, key=key)

    def commit_transaction(self) -> Optional[Dict[str, Any]]:
        return self._manager.commit_transaction()

    def rollback_transaction(self) -> bool:
        return self._manager.rollback_transaction()

    def create_entity(self, name: str, components: Optional[Dict[str, Dict[str, Any]]] = None) -> bool:
        return self._manager.create_entity(name, components=components)

    def create_entity_from_data(self, entity_data: Dict[str, Any]) -> bool:
        return self._manager.create_entity_from_data(entity_data)

    def remove_entity(self, entity_name: str) -> bool:
        return self._manager.remove_entity(entity_name)

    def add_component_to_entity(
        self,
        entity_name: str,
        component_name: str,
        component_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return self._manager.add_component_to_entity(
            entity_name,
            component_name,
            component_data=component_data,
        )

    def remove_component_from_entity(self, entity_name: str, component_name: str) -> bool:
        return self._manager.remove_component_from_entity(entity_name, component_name)

    def apply_edit_to_world(self, entity_name: str, component_name: str, property_name: str, value: Any) -> bool:
        return self._manager.apply_edit_to_world(entity_name, component_name, property_name, value)

    def update_entity_property(self, entity_name: str, property_name: str, value: Any) -> bool:
        return self._manager.update_entity_property(entity_name, property_name, value)

    def replace_component_data(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        return self._manager.replace_component_data(entity_name, component_name, component_data)

    def find_entity_data(self, entity_name: str) -> Optional[Dict[str, Any]]:
        return self._manager.find_entity_data(entity_name)

    def get_component_data(self, entity_name: str, component_name: str) -> Optional[Dict[str, Any]]:
        return self._manager.get_component_data(entity_name, component_name)

    def get_feature_metadata(self) -> Dict[str, Any]:
        return self._manager.get_feature_metadata()

    def set_feature_metadata(self, key: str, value: Any) -> bool:
        return self._manager.set_feature_metadata(key, value)

    def set_entity_parent(self, entity_name: str, parent_name: Optional[str]) -> bool:
        return self._manager.set_entity_parent(entity_name, parent_name)

    def create_child_entity(
        self,
        parent_name: str,
        name: str,
        components: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> bool:
        return self._manager.create_child_entity(parent_name, name, components=components)

    def instantiate_prefab(
        self,
        name: str,
        prefab_path: str,
        parent: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
        root_name: Optional[str] = None,
    ) -> bool:
        return self._manager.instantiate_prefab(
            name,
            prefab_path=prefab_path,
            parent=parent,
            overrides=overrides,
            root_name=root_name,
        )

    def create_prefab(
        self,
        entity_name: str,
        path: str,
        replace_original: bool = False,
        instance_name: Optional[str] = None,
        prefab_locator: Optional[str] = None,
    ) -> bool:
        return self._manager.create_prefab(
            entity_name,
            path,
            replace_original=replace_original,
            instance_name=instance_name,
            prefab_locator=prefab_locator,
        )

    def unpack_prefab(self, entity_name: str) -> bool:
        return self._manager.unpack_prefab(entity_name)

    def apply_prefab_overrides(self, entity_name: str) -> bool:
        return self._manager.apply_prefab_overrides(entity_name)


class SceneManagerWorkspaceAdapter(_SceneManagerAdapter):
    @property
    def active_scene_key(self) -> str:
        return self._manager.active_scene_key

    def list_open_scenes(self) -> list[Dict[str, Any]]:
        return self._manager.list_open_scenes()

    def get_active_scene_summary(self) -> Dict[str, Any]:
        return self._manager.get_active_scene_summary()

    def resolve_entry(self, key_or_path: Optional[str]) -> Optional["SceneWorkspaceEntry"]:
        return self._manager.resolve_entry(key_or_path)

    def ensure_scene_open(self, scene_ref: str, activate: bool = False) -> Optional["SceneWorkspaceEntry"]:
        return self._manager.ensure_scene_open(scene_ref, activate=activate)

    def load_scene(
        self,
        data: Dict[str, Any],
        source_path: Optional[str] = None,
        activate: bool = True,
    ) -> "World":
        return self._manager.load_scene(data, source_path=source_path, activate=activate)

    def load_scene_from_file(self, path: str, activate: bool = True) -> Optional["World"]:
        return self._manager.load_scene_from_file(path, activate=activate)

    def activate_scene(self, key_or_path: str) -> Optional["World"]:
        return self._manager.activate_scene(key_or_path)

    def close_scene(self, key_or_path: str, discard_changes: bool = False) -> bool:
        return self._manager.close_scene(key_or_path, discard_changes=discard_changes)

    def save_scene_to_file(self, path: str, key: Optional[str] = None) -> bool:
        return self._manager.save_scene_to_file(path, key=key)

    def get_feature_metadata(self) -> Dict[str, Any]:
        return self._manager.get_feature_metadata()

    def get_scene_flow(self) -> Dict[str, str]:
        return self._manager.get_scene_flow()

    def set_scene_flow_target(self, key: str, target_path: str) -> bool:
        return self._manager.set_scene_flow_target(key, target_path)

    def copy_entity_subtree(self, entity_name: str) -> bool:
        return self._manager.copy_entity_subtree(entity_name)

    def paste_copied_entities(self, target_scene_key: Optional[str] = None) -> bool:
        return self._manager.paste_copied_entities(target_scene_key)
