"""
engine/scenes/scene.py - Escena con datos originales del nivel
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from engine.ecs.entity import normalize_entity_groups
from engine.serialization.schema import migrate_scene_data

if TYPE_CHECKING:
    from engine.ecs.world import World
    from engine.levels.component_registry import ComponentRegistry


class Scene:
    """Escena que contiene los datos serializables de authoring."""

    def __init__(self, name: str = "Untitled", data: Optional[Dict[str, Any]] = None, source_path: Optional[str] = None) -> None:
        self._name: str = name
        initial_data = data or {
            "name": name,
            "schema_version": 1,
            "entities": [],
            "rules": [],
            "feature_metadata": {},
        }
        self._data: Dict[str, Any] = migrate_scene_data(initial_data)
        self._data.setdefault("name", name)
        self._data.setdefault("entities", [])
        self._data.setdefault("rules", [])
        self._data.setdefault("feature_metadata", {})
        self._source_path: Optional[str] = source_path
        self._entity_index: Dict[str, Dict[str, Any]] = {}
        self._rebuild_entity_index()

    @property
    def name(self) -> str:
        return self._name

    @property
    def data(self) -> Dict[str, Any]:
        return self._data

    @property
    def entities_data(self) -> list:
        return self._data.get("entities", [])

    @property
    def rules_data(self) -> list:
        return self._data.get("rules", [])

    @property
    def feature_metadata(self) -> Dict[str, Any]:
        return self._data.setdefault("feature_metadata", {})

    def get_signal_metadata(self) -> Dict[str, Any]:
        signals = self.feature_metadata.get("signals", {})
        return copy.deepcopy(signals) if isinstance(signals, dict) else {}

    def list_signal_connections(self) -> list[Dict[str, Any]]:
        signals = self.feature_metadata.get("signals", {})
        if not isinstance(signals, dict):
            return []
        connections = signals.get("connections", [])
        return copy.deepcopy(connections) if isinstance(connections, list) else []

    @property
    def source_path(self) -> Optional[str]:
        return self._source_path

    def set_source_path(self, source_path: Optional[str]) -> None:
        self._source_path = source_path

    def create_world(self, registry: "ComponentRegistry") -> "World":
        from engine.assets.prefab import PrefabManager
        from engine.components.transform import Transform
        from engine.ecs.world import World

        world = World()
        world.feature_metadata = copy.deepcopy(self.feature_metadata)
        created_entities = {}
        pending_links: list[tuple[str, str]] = []

        for entity_data in self.entities_data:
            expanded_entities: list[dict[str, Any]]
            prefab_instance = entity_data.get("prefab_instance")
            if prefab_instance:
                prefab_path = self._resolve_prefab_path(prefab_instance.get("prefab_path", ""))
                prefab_data = PrefabManager.load_prefab_data(prefab_path)
                if prefab_data is None:
                    expanded_entities = [copy.deepcopy(entity_data)]
                else:
                    expanded_entities = PrefabManager.expand_prefab_instance(
                        prefab_data,
                        instance_name=entity_data.get("name", prefab_instance.get("root_name", "Prefab")),
                        parent_name=entity_data.get("parent"),
                        prefab_path=prefab_instance.get("prefab_path", ""),
                        overrides=copy.deepcopy(prefab_instance.get("overrides", {})),
                    )
            else:
                expanded_entities = [copy.deepcopy(entity_data)]

            for expanded_data in expanded_entities:
                entity_name = expanded_data.get("name", "Entity")
                entity = world.create_entity(entity_name)
                entity.active = expanded_data.get("active", True)
                entity.tag = expanded_data.get("tag", "Untagged")
                entity.layer = expanded_data.get("layer", "Default")
                entity.groups = normalize_entity_groups(expanded_data.get("groups", ()))
                entity.parent_name = expanded_data.get("parent")
                entity.prefab_instance = copy.deepcopy(expanded_data.get("prefab_instance"))
                entity.prefab_source_path = expanded_data.get("prefab_source_path")
                entity.prefab_root_name = expanded_data.get("prefab_root_name")
                component_metadata = copy.deepcopy(expanded_data.get("component_metadata", {}))

                for comp_name, comp_props in expanded_data.get("components", {}).items():
                    component = registry.create(comp_name, comp_props)
                    if component is not None:
                        entity.add_component(component, metadata=component_metadata.get(comp_name, {}))

                created_entities[entity_name] = entity
                if entity.parent_name:
                    pending_links.append((entity_name, entity.parent_name))

        for entity_name, parent_name in pending_links:
            entity = created_entities.get(entity_name)
            parent = created_entities.get(parent_name)
            if entity is None or parent is None:
                continue
            child_transform = entity.get_component(Transform)
            parent_transform = parent.get_component(Transform)
            if child_transform is not None:
                if child_transform.parent and child_transform in child_transform.parent.children:
                    child_transform.parent.children.remove(child_transform)
                child_transform.parent = parent_transform
                if parent_transform is not None and child_transform not in parent_transform.children:
                    parent_transform.children.append(child_transform)

        return world

    def _resolve_prefab_path(self, prefab_path: str) -> str:
        path = Path(prefab_path)
        if path.is_absolute() or self._source_path is None:
            return path.as_posix()
        return (Path(self._source_path).resolve().parent / path).resolve().as_posix()

    def _rebuild_entity_index(self) -> None:
        self._entity_index.clear()
        for entity_data in self.entities_data:
            if not isinstance(entity_data, dict):
                continue
            entity_name = entity_data.get("name")
            if isinstance(entity_name, str) and entity_name not in self._entity_index:
                self._entity_index[entity_name] = entity_data

    def update_component(self, entity_name: str, component_name: str, property_name: str, value: Any) -> bool:
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        components = entity_data.get("components", {})
        if component_name in components:
            components[component_name][property_name] = value
            print(f"[EDIT] Scene: {entity_name}.{component_name}.{property_name} = {value}")
            return True
        return False

    def update_entity_property(self, entity_name: str, property_name: str, value: Any) -> bool:
        if property_name == "groups":
            return self.set_entity_groups(entity_name, value)
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        if property_name == "name":
            new_name = value
            if not isinstance(new_name, str):
                return False
            if new_name == entity_name:
                return True
            existing = self.find_entity(new_name)
            if existing is not None and existing is not entity_data:
                return False
            entity_data[property_name] = new_name
            self._rebuild_entity_index()
            return True
        entity_data[property_name] = value
        return True

    def get_entity_groups(self, entity_name: str) -> list[str]:
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return []
        return list(normalize_entity_groups(entity_data.get("groups", ())))

    def set_entity_groups(self, entity_name: str, groups: Any) -> bool:
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        normalized_groups = list(normalize_entity_groups(groups))
        if normalized_groups:
            entity_data["groups"] = normalized_groups
        else:
            entity_data.pop("groups", None)
        return True

    def replace_component_data(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        if component_name not in components:
            return False
        components[component_name] = component_data
        return True

    def get_component_metadata(self, entity_name: str, component_name: str) -> Dict[str, Any]:
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return {}
        metadata = entity_data.get("component_metadata", {})
        if not isinstance(metadata, dict):
            return {}
        value = metadata.get(component_name, {})
        return copy.deepcopy(value) if isinstance(value, dict) else {}

    def set_component_metadata(self, entity_name: str, component_name: str, metadata: Dict[str, Any]) -> bool:
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        if component_name not in entity_data.setdefault("components", {}):
            return False
        entity_metadata = entity_data.setdefault("component_metadata", {})
        if not isinstance(entity_metadata, dict):
            entity_metadata = {}
            entity_data["component_metadata"] = entity_metadata
        if metadata:
            entity_metadata[component_name] = copy.deepcopy(metadata)
        else:
            entity_metadata.pop(component_name, None)
        if not entity_metadata:
            entity_data.pop("component_metadata", None)
        return True

    def add_entity(self, entity_data: Dict[str, Any]) -> bool:
        entity_name = entity_data.get("name", "")
        if self.find_entity(entity_name) is not None:
            return False
        self._data.setdefault("entities", []).append(entity_data)
        if isinstance(entity_name, str):
            self._entity_index[entity_name] = entity_data
        return True

    def remove_entity(self, entity_name: str) -> bool:
        if self.find_entity(entity_name) is None:
            return False
        entities = self._data.get("entities", [])
        for index, entity_data in enumerate(entities):
            if entity_data.get("name") == entity_name:
                del entities[index]
                self._rebuild_entity_index()
                return True
        return False

    def add_component(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        components[component_name] = component_data
        return True

    def remove_component(self, entity_name: str, component_name: str) -> bool:
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        if component_name not in components:
            return False
        del components[component_name]
        component_metadata = entity_data.get("component_metadata", {})
        if isinstance(component_metadata, dict):
            component_metadata.pop(component_name, None)
            if not component_metadata:
                entity_data.pop("component_metadata", None)
        return True

    def set_feature_metadata(self, key: str, value: Any) -> None:
        self.feature_metadata[key] = value

    def find_entity(self, entity_name: str) -> Optional[Dict[str, Any]]:
        if not isinstance(entity_name, str):
            return None
        return self._entity_index.get(entity_name)

    def to_dict(self) -> Dict[str, Any]:
        return migrate_scene_data(copy.deepcopy(self._data))

    @classmethod
    def from_dict(cls, data: Dict[str, Any], source_path: Optional[str] = None) -> "Scene":
        name = data.get("name", "Untitled")
        return cls(name=name, data=data, source_path=source_path)

    def __repr__(self) -> str:
        entity_count = len(self.entities_data)
        return f"Scene(name='{self._name}', entities={entity_count})"
