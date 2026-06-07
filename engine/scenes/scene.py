"""
engine/scenes/scene.py - Escena con datos originales del nivel
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from engine.ecs.entity import normalize_entity_groups
from engine.serialization.json_value import clone_json_value
from engine.serialization.schema import (
    canonicalize_scene_entity,
    migrate_scene_data,
    validate_scene_entity_for_add,
)

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
        self._entity_id_index: Dict[str, Dict[str, Any]] = {}
        self._scene_entry_id_index: Dict[str, Dict[str, Any]] = {}
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
        from engine.ecs.world import World

        world = World()
        world.feature_metadata = clone_json_value(self.feature_metadata)
        for entity_data in self.entities_data:
            self.materialize_entity(world, registry, entity_data)
        self._link_world_hierarchy(world, list(world.iter_all_entities()))
        return world

    def materialize_entity(
        self,
        world: "World",
        registry: "ComponentRegistry",
        entity_data: Dict[str, Any],
    ) -> list[Any]:
        """Project one serialized scene entity into an existing World."""
        from engine.assets.prefab import PrefabManager

        prefab_instance = entity_data.get("prefab_instance")
        expanded_entities: list[dict[str, Any]]
        if isinstance(prefab_instance, dict):
            prefab_path = self._resolve_prefab_path(str(prefab_instance.get("prefab_path", "")))
            prefab_data = PrefabManager.load_prefab_data(prefab_path)
            if prefab_data is None:
                expanded_entities = [entity_data]
            else:
                expanded_entities = PrefabManager.expand_prefab_instance(
                    prefab_data,
                    instance_name=str(
                        entity_data.get("name", prefab_instance.get("root_name", "Prefab"))
                    ),
                    parent_name=entity_data.get("parent"),
                    prefab_path=prefab_instance.get("prefab_path", ""),
                    overrides=prefab_instance.get("overrides", {}),
                )
                root_entity_id = entity_data.get("id")
                if isinstance(root_entity_id, str) and root_entity_id.strip():
                    for expanded_data in expanded_entities:
                        if expanded_data.get("prefab_source_path", "") == "":
                            expanded_data["id"] = root_entity_id.strip()
                            break
        else:
            expanded_entities = [entity_data]

        names = [str(item.get("name", "Entity")) for item in expanded_entities]
        if len(set(names)) != len(names):
            raise ValueError("Prefab expansion contains duplicate entity names")
        duplicate_name = next((name for name in names if world.get_entity_by_name(name) is not None), None)
        if duplicate_name is not None:
            raise ValueError(f"World already contains entity '{duplicate_name}'")

        created = []
        try:
            for expanded_data in expanded_entities:
                entity = world.create_entity(str(expanded_data.get("name", "Entity")))
                created.append(entity)
                entity_id = expanded_data.get("id")
                if isinstance(entity_id, str) and entity_id.strip():
                    entity.serialized_id = entity_id.strip()
                entity.active = expanded_data.get("active", True)
                entity.tag = expanded_data.get("tag", "Untagged")
                entity.layer = expanded_data.get("layer", "Default")
                entity.groups = normalize_entity_groups(expanded_data.get("groups", ()))
                entity.parent_name = expanded_data.get("parent")
                entity.prefab_instance = clone_json_value(expanded_data.get("prefab_instance"))
                entity.prefab_source_path = expanded_data.get("prefab_source_path")
                entity.prefab_root_name = expanded_data.get("prefab_root_name")
                component_metadata = expanded_data.get("component_metadata", {})
                for comp_name, comp_props in expanded_data.get("components", {}).items():
                    component = registry.create(comp_name, clone_json_value(comp_props))
                    entity.add_component(component, metadata=component_metadata.get(comp_name, {}))

            self._link_world_hierarchy(world, created)
            return created
        except Exception:
            for entity in reversed(created):
                world.remove_entity(entity.id)
            raise

    @staticmethod
    def _link_world_hierarchy(world: "World", entities: list[Any]) -> None:
        from engine.components.transform import Transform

        for entity in entities:
            if not entity.parent_name:
                continue
            parent = world.get_entity_by_name(entity.parent_name)
            if parent is None:
                continue
            child_transform = entity.get_component(Transform)
            parent_transform = parent.get_component(Transform)
            if child_transform is None:
                continue
            child_transform.parent = parent_transform

    def _resolve_prefab_path(self, prefab_path: str) -> str:
        path = Path(prefab_path)
        if path.is_absolute() or self._source_path is None:
            return path.as_posix()
        return (Path(self._source_path).resolve().parent / path).resolve().as_posix()

    def _rebuild_entity_index(self) -> None:
        self._entity_index.clear()
        self._entity_id_index.clear()
        self._scene_entry_id_index.clear()
        for entity_data in self.entities_data:
            if not isinstance(entity_data, dict):
                continue
            entity_name = entity_data.get("name")
            if isinstance(entity_name, str) and entity_name not in self._entity_index:
                self._entity_index[entity_name] = entity_data
            entity_id = entity_data.get("id")
            if isinstance(entity_id, str) and entity_id.strip() and entity_id not in self._entity_id_index:
                self._entity_id_index[entity_id] = entity_data
            self._index_scene_entry(entity_data)

    def _index_scene_entry(self, entity_data: Dict[str, Any]) -> None:
        entry_point = entity_data.get("components", {}).get("SceneEntryPoint")
        entry_id = entry_point.get("entry_id") if isinstance(entry_point, dict) else None
        if isinstance(entry_id, str) and entry_id.strip() and entry_id not in self._scene_entry_id_index:
            self._scene_entry_id_index[entry_id] = entity_data

    def _deindex_scene_entry(self, entity_data: Dict[str, Any]) -> None:
        entry_point = entity_data.get("components", {}).get("SceneEntryPoint")
        entry_id = entry_point.get("entry_id") if isinstance(entry_point, dict) else None
        if isinstance(entry_id, str) and self._scene_entry_id_index.get(entry_id) is entity_data:
            self._scene_entry_id_index.pop(entry_id, None)

    def _canonicalize_entity_for_add(self, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        entities = self.entities_data
        return canonicalize_scene_entity(
            entity_data,
            scene_name=str(self._data.get("name", self._name) or self._name),
            index=len(entities),
            used_ids=self._entity_id_index,
        )

    def _rename_entity_references(self, old_name: str, new_name: str, entity_id: str | None = None) -> None:
        for entity_data in self.entities_data:
            if not isinstance(entity_data, dict):
                continue
            if entity_data.get("parent") == old_name:
                entity_data["parent"] = new_name
            scene_link = entity_data.get("components", {}).get("SceneLink")
            if isinstance(scene_link, dict) and scene_link.get("target_entity_name") == old_name:
                scene_link["target_entity_name"] = new_name

        for rule in self.rules_data:
            if not isinstance(rule, dict):
                continue
            actions = rule.get("do", [])
            if not isinstance(actions, list):
                continue
            for action in actions:
                if isinstance(action, dict) and action.get("entity") == old_name:
                    action["entity"] = new_name

        signals = self.feature_metadata.get("signals", {})
        connections = signals.get("connections", []) if isinstance(signals, dict) else []
        if not isinstance(connections, list):
            return
        for connection in connections:
            if not isinstance(connection, dict):
                continue
            target = connection.get("target")
            if not (
                isinstance(target, dict)
                and str(target.get("kind", "") or "").strip().lower() == "entity"
            ):
                continue
            target_id = str(target.get("id", "") or "").strip()
            if entity_id and target_id == entity_id:
                target["name"] = new_name
            elif target.get("name") == old_name:
                target["name"] = new_name

    def update_component(self, entity_name: str, component_name: str, property_name: str, value: Any) -> bool:
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        components = entity_data.get("components", {})
        if component_name in components:
            if component_name == "SceneEntryPoint":
                self._deindex_scene_entry(entity_data)
            components[component_name][property_name] = value
            if component_name == "SceneEntryPoint":
                self._index_scene_entry(entity_data)
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
            entity_id = entity_data.get("id")
            entity_data[property_name] = new_name
            self._rename_entity_references(
                entity_name,
                new_name,
                entity_id.strip() if isinstance(entity_id, str) else None,
            )
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
        if component_name == "SceneEntryPoint":
            self._deindex_scene_entry(entity_data)
        components[component_name] = component_data
        if component_name == "SceneEntryPoint":
            self._index_scene_entry(entity_data)
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
        canonical_entity = self._canonicalize_entity_for_add(entity_data)
        errors = validate_scene_entity_for_add(
            canonical_entity,
            index=len(self.entities_data),
            existing_names=self._entity_index,
            existing_ids=self._entity_id_index,
            existing_entry_ids=self._scene_entry_id_index,
        )
        if errors:
            return False
        entity_name = canonical_entity["name"]
        entity_id = canonical_entity["id"]
        self._data.setdefault("entities", []).append(canonical_entity)
        self._entity_index[entity_name] = canonical_entity
        self._entity_id_index[entity_id] = canonical_entity
        self._index_scene_entry(canonical_entity)
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

    def remove_entity_by_id(self, entity_id: str) -> bool:
        entity_data = self.find_entity_by_id(entity_id)
        if entity_data is None:
            return False
        entity_name = entity_data.get("name")
        return self.remove_entity(entity_name) if isinstance(entity_name, str) else False

    def add_component(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        components[component_name] = component_data
        if component_name == "SceneEntryPoint":
            self._index_scene_entry(entity_data)
        return True

    def add_component_by_id(self, entity_id: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        entity_data = self.find_entity_by_id(entity_id)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        components[component_name] = component_data
        if component_name == "SceneEntryPoint":
            self._index_scene_entry(entity_data)
        return True

    def remove_component(self, entity_name: str, component_name: str) -> bool:
        entity_data = self.find_entity(entity_name)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        if component_name not in components:
            return False
        if component_name == "SceneEntryPoint":
            self._deindex_scene_entry(entity_data)
        del components[component_name]
        component_metadata = entity_data.get("component_metadata", {})
        if isinstance(component_metadata, dict):
            component_metadata.pop(component_name, None)
            if not component_metadata:
                entity_data.pop("component_metadata", None)
        return True

    def remove_component_by_id(self, entity_id: str, component_name: str) -> bool:
        entity_data = self.find_entity_by_id(entity_id)
        if entity_data is None:
            return False
        entity_name = entity_data.get("name")
        return self.remove_component(entity_name, component_name) if isinstance(entity_name, str) else False

    def set_feature_metadata(self, key: str, value: Any) -> None:
        self.feature_metadata[key] = value

    def find_entity(self, entity_name: str) -> Optional[Dict[str, Any]]:
        if not isinstance(entity_name, str):
            return None
        return self._entity_index.get(entity_name)

    def find_entity_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        if not isinstance(entity_id, str):
            return None
        return self._entity_id_index.get(entity_id)

    def update_component_by_id(self, entity_id: str, component_name: str, property_name: str, value: Any) -> bool:
        entity_data = self.find_entity_by_id(entity_id)
        if entity_data is None:
            return False
        components = entity_data.get("components", {})
        if component_name in components:
            if component_name == "SceneEntryPoint":
                self._deindex_scene_entry(entity_data)
            components[component_name][property_name] = value
            if component_name == "SceneEntryPoint":
                self._index_scene_entry(entity_data)
            print(f"[EDIT] Scene: {entity_id}.{component_name}.{property_name} = {value}")
            return True
        return False

    def update_entity_property_by_id(self, entity_id: str, property_name: str, value: Any) -> bool:
        entity_data = self.find_entity_by_id(entity_id)
        if entity_data is None:
            return False
        entity_name = entity_data.get("name")
        if isinstance(entity_name, str):
            return self.update_entity_property(entity_name, property_name, value)
        return False

    def replace_component_data_by_id(self, entity_id: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        entity_data = self.find_entity_by_id(entity_id)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        if component_name not in components:
            return False
        if component_name == "SceneEntryPoint":
            self._deindex_scene_entry(entity_data)
        components[component_name] = component_data
        if component_name == "SceneEntryPoint":
            self._index_scene_entry(entity_data)
        return True

    def to_dict(self) -> Dict[str, Any]:
        return migrate_scene_data(self._data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], source_path: Optional[str] = None) -> "Scene":
        name = data.get("name", "Untitled")
        return cls(name=name, data=data, source_path=source_path)

    def __repr__(self) -> str:
        entity_count = len(self.entities_data)
        return f"Scene(name='{self._name}', entities={entity_count})"
