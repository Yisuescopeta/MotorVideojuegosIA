"""
engine/scenes/scene.py - Escena con datos originales del nivel
"""

from __future__ import annotations

import copy
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from engine.ecs.entity import normalize_entity_groups
from engine.serialization.json_value import clone_json_value
from engine.serialization.schema import (
    canonicalize_scene_entity,
    migrate_scene_data,
    validate_scene_entity_for_add,
)
from engine.scenes.scene_views import (
    EntityView,
    FeatureMetadataView,
    RuleView,
    SceneSnapshot,
    entity_view,
    freeze_json,
    thaw_json,
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
        self._revision: int = 0
        self._entity_index: Dict[str, Dict[str, Any]] = {}
        self._entity_id_index: Dict[str, Dict[str, Any]] = {}
        self._scene_entry_id_index: Dict[str, Dict[str, Any]] = {}
        self._rebuild_entity_index()

    @property
    def name(self) -> str:
        return self._name

    @property
    def revision(self) -> int:
        return self._revision

    def _warn_legacy_surface(self, surface: str) -> None:
        warnings.warn(
            f"Scene.{surface} is deprecated; use snapshots/views or Scene authoring methods.",
            DeprecationWarning,
            stacklevel=3,
        )

    @property
    def data(self) -> Dict[str, Any]:
        self._warn_legacy_surface("data")
        return copy.deepcopy(self._data)

    @property
    def entities_data(self) -> list:
        self._warn_legacy_surface("entities_data")
        return copy.deepcopy(self._entities_data())

    @property
    def rules_data(self) -> list:
        self._warn_legacy_surface("rules_data")
        return copy.deepcopy(self._rules_data())

    @property
    def feature_metadata(self) -> Dict[str, Any]:
        self._warn_legacy_surface("feature_metadata")
        return copy.deepcopy(self._feature_metadata())

    def snapshot(self) -> SceneSnapshot:
        frozen = freeze_json(self.to_snapshot_dict())
        if not isinstance(frozen, dict) and not hasattr(frozen, "items"):
            raise TypeError("Scene snapshot must be a JSON object")
        return SceneSnapshot(
            name=self._name,
            revision=self._revision,
            data=frozen,
        )

    def find_entity_view(self, entity_id: str) -> EntityView | None:
        entity_data = self._find_entity_by_id_mutable(entity_id)
        return entity_view(entity_data) if entity_data is not None else None

    def list_entity_views(self) -> tuple[EntityView, ...]:
        return tuple(
            entity_view(entity_data)
            for entity_data in self._entities_data()
            if isinstance(entity_data, dict)
        )

    def rules_view(self) -> tuple[RuleView, ...]:
        return tuple(
            RuleView(data=frozen)
            for rule in self._rules_data()
            if isinstance((frozen := freeze_json(rule)), dict)
            or hasattr(frozen, "items")
        )

    def feature_metadata_view(self) -> FeatureMetadataView:
        frozen = freeze_json(self._feature_metadata())
        if not hasattr(frozen, "items"):
            raise TypeError("Scene feature metadata must be a JSON object")
        return FeatureMetadataView(data=frozen)

    def _entities_data(self) -> list[dict[str, Any]]:
        entities = self._data.setdefault("entities", [])
        return entities if isinstance(entities, list) else []

    def _rules_data(self) -> list[dict[str, Any]]:
        rules = self._data.setdefault("rules", [])
        return rules if isinstance(rules, list) else []

    def _feature_metadata(self) -> Dict[str, Any]:
        metadata = self._data.setdefault("feature_metadata", {})
        return metadata if isinstance(metadata, dict) else {}

    def _find_entity_mutable(self, entity_name: str) -> Optional[Dict[str, Any]]:
        if not isinstance(entity_name, str):
            return None
        return self._entity_index.get(entity_name)

    def _find_entity_by_id_mutable(self, entity_id: str) -> Optional[Dict[str, Any]]:
        if not isinstance(entity_id, str):
            return None
        return self._entity_id_index.get(entity_id)

    def _bump_revision(self) -> None:
        self._revision += 1

    def _restore_revision(self, revision: int) -> None:
        """Restore revision only for an atomic workspace rollback."""
        normalized = int(revision)
        if normalized < 0:
            raise ValueError("Scene revision cannot be negative")
        self._revision = normalized

    def get_signal_metadata(self) -> Dict[str, Any]:
        signals = self._feature_metadata().get("signals", {})
        return copy.deepcopy(signals) if isinstance(signals, dict) else {}

    def list_signal_connections(self) -> list[Dict[str, Any]]:
        signals = self._feature_metadata().get("signals", {})
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
        world.feature_metadata = clone_json_value(self._feature_metadata())
        for entity_data in self._entities_data():
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
        for entity_data in self._entities_data():
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
        entities = self._entities_data()
        canonical_entity = canonicalize_scene_entity(
            entity_data,
            scene_name=str(self._data.get("name", self._name) or self._name),
            index=len(entities),
            used_ids=self._entity_id_index,
        )
        return canonical_entity

    def _rename_entity_references(self, old_name: str, new_name: str, entity_id: str | None = None) -> None:
        for entity_data in self._entities_data():
            if not isinstance(entity_data, dict):
                continue
            if entity_data.get("parent") == old_name:
                entity_data["parent"] = new_name
            scene_link = entity_data.get("components", {}).get("SceneLink")
            if isinstance(scene_link, dict):
                target_id = str(scene_link.get("target_entity_id", "") or "").strip()
                if (entity_id and target_id == entity_id) or scene_link.get("target_entity_name") == old_name:
                    scene_link["target_entity_name"] = new_name
                    if not target_id and entity_id:
                        scene_link["target_entity_id"] = entity_id

        for rule in self._rules_data():
            if not isinstance(rule, dict):
                continue
            actions = rule.get("do", [])
            if not isinstance(actions, list):
                continue
            for action in actions:
                if not isinstance(action, dict):
                    continue
                action_id = str(action.get("entity_id", "") or "").strip()
                if (entity_id and action_id == entity_id) or action.get("entity") == old_name:
                    action["entity"] = new_name
                    if not action_id and entity_id:
                        action["entity_id"] = entity_id

        signals = self._feature_metadata().get("signals", {})
        connections = signals.get("connections", []) if isinstance(signals, dict) else []
        if not isinstance(connections, list):
            return
        for connection in connections:
            if not isinstance(connection, dict):
                continue
            for endpoint_key in ("source", "target"):
                endpoint = connection.get(endpoint_key)
                if not (
                    isinstance(endpoint, dict)
                    and str(endpoint.get("kind", "") or "").strip().lower() == "entity"
                ):
                    continue
                endpoint_id = str(endpoint.get("id", "") or "").strip()
                if (entity_id and endpoint_id == entity_id) or endpoint.get("name") == old_name:
                    endpoint["name"] = new_name
                    if not endpoint_id and entity_id:
                        endpoint["id"] = entity_id

    def update_component(self, entity_name: str, component_name: str, property_name: str, value: Any) -> bool:
        entity_data = self._find_entity_mutable(entity_name)
        if entity_data is None:
            return False
        components = entity_data.get("components", {})
        if component_name in components:
            if not isinstance(components[component_name], dict) or components[component_name].get(property_name) == value:
                return False
            if component_name == "SceneEntryPoint":
                self._deindex_scene_entry(entity_data)
            components[component_name][property_name] = value
            if component_name == "SceneEntryPoint":
                self._index_scene_entry(entity_data)
            self._bump_revision()
            print(f"[EDIT] Scene: {entity_name}.{component_name}.{property_name} = {value}")
            return True
        return False

    def update_component_properties(
        self,
        entity_name: str,
        component_name: str,
        properties: Dict[str, Any],
    ) -> bool:
        entity_data = self._find_entity_mutable(entity_name)
        if entity_data is None:
            return False
        components = entity_data.get("components", {})
        component_data = components.get(component_name) if isinstance(components, dict) else None
        if not isinstance(component_data, dict):
            return False
        if all(component_data.get(key) == value for key, value in properties.items()):
            return False
        if component_name == "SceneEntryPoint":
            self._deindex_scene_entry(entity_data)
        component_data.update(properties)
        if component_name == "SceneEntryPoint":
            self._index_scene_entry(entity_data)
        self._bump_revision()
        return True

    def update_component_properties_by_id(
        self,
        entity_id: str,
        component_name: str,
        properties: Dict[str, Any],
    ) -> bool:
        entity_data = self._find_entity_by_id_mutable(entity_id)
        if entity_data is None:
            return False
        components = entity_data.get("components", {})
        component_data = components.get(component_name) if isinstance(components, dict) else None
        if not isinstance(component_data, dict):
            return False
        if all(component_data.get(key) == value for key, value in properties.items()):
            return False
        if component_name == "SceneEntryPoint":
            self._deindex_scene_entry(entity_data)
        component_data.update(properties)
        if component_name == "SceneEntryPoint":
            self._index_scene_entry(entity_data)
        self._bump_revision()
        return True

    def update_entity_property(self, entity_name: str, property_name: str, value: Any) -> bool:
        if property_name == "groups":
            return self.set_entity_groups(entity_name, value)
        entity_data = self._find_entity_mutable(entity_name)
        if entity_data is None:
            return False
        if property_name == "name":
            new_name = value
            if not isinstance(new_name, str):
                return False
            if new_name == entity_name:
                return True
            existing = self._find_entity_mutable(new_name)
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
            self._bump_revision()
            return True
        if property_name == "parent":
            parent_name = value if isinstance(value, str) and value.strip() else None
            parent = self._find_entity_mutable(parent_name) if parent_name is not None else None
            if parent_name is not None and parent is None:
                return False
            next_parent_id = parent.get("id") if parent is not None else None
            if entity_data.get("parent") == parent_name and entity_data.get("parent_id") == next_parent_id:
                return False
            entity_data["parent"] = parent_name
            entity_data["parent_id"] = next_parent_id
        else:
            if entity_data.get(property_name) == value:
                return False
            entity_data[property_name] = value
        self._bump_revision()
        return True

    def get_entity_groups(self, entity_name: str) -> list[str]:
        entity_data = self._find_entity_mutable(entity_name)
        if entity_data is None:
            return []
        return list(normalize_entity_groups(entity_data.get("groups", ())))

    def set_entity_groups(self, entity_name: str, groups: Any) -> bool:
        entity_data = self._find_entity_mutable(entity_name)
        if entity_data is None:
            return False
        normalized_groups = list(normalize_entity_groups(groups))
        current_groups = list(normalize_entity_groups(entity_data.get("groups", ())))
        if current_groups == normalized_groups:
            return False
        if normalized_groups:
            entity_data["groups"] = normalized_groups
        else:
            entity_data.pop("groups", None)
        self._bump_revision()
        return True

    def replace_component_data(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        entity_data = self._find_entity_mutable(entity_name)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        if component_name not in components:
            return False
        if components[component_name] == component_data:
            return False
        if component_name == "SceneEntryPoint":
            self._deindex_scene_entry(entity_data)
        components[component_name] = component_data
        if component_name == "SceneEntryPoint":
            self._index_scene_entry(entity_data)
        self._bump_revision()
        return True

    def get_component_metadata(self, entity_name: str, component_name: str) -> Dict[str, Any]:
        entity_data = self._find_entity_mutable(entity_name)
        if entity_data is None:
            return {}
        metadata = entity_data.get("component_metadata", {})
        if not isinstance(metadata, dict):
            return {}
        value = metadata.get(component_name, {})
        return copy.deepcopy(value) if isinstance(value, dict) else {}

    def set_component_metadata(self, entity_name: str, component_name: str, metadata: Dict[str, Any]) -> bool:
        entity_data = self._find_entity_mutable(entity_name)
        if entity_data is None:
            return False
        if component_name not in entity_data.setdefault("components", {}):
            return False
        entity_metadata = entity_data.setdefault("component_metadata", {})
        if not isinstance(entity_metadata, dict):
            entity_metadata = {}
            entity_data["component_metadata"] = entity_metadata
        current_metadata = entity_metadata.get(component_name, {})
        current_metadata = current_metadata if isinstance(current_metadata, dict) else {}
        if current_metadata == metadata:
            return False
        if metadata:
            entity_metadata[component_name] = copy.deepcopy(metadata)
        else:
            entity_metadata.pop(component_name, None)
        if not entity_metadata:
            entity_data.pop("component_metadata", None)
        self._bump_revision()
        return True

    def add_entity(self, entity_data: Dict[str, Any]) -> bool:
        canonical_entity = self._canonicalize_entity_for_add(entity_data)
        errors = validate_scene_entity_for_add(
            canonical_entity,
            index=len(self._entities_data()),
            existing_names=self._entity_index,
            existing_ids=self._entity_id_index,
            existing_entry_ids=self._scene_entry_id_index,
        )
        if errors:
            return False
        entity_name = canonical_entity["name"]
        entity_id = canonical_entity["id"]
        self._entities_data().append(canonical_entity)
        self._entity_index[entity_name] = canonical_entity
        self._entity_id_index[entity_id] = canonical_entity
        self._index_scene_entry(canonical_entity)
        self._bump_revision()
        return True

    def set_component_metadata_by_id(
        self,
        entity_id: str,
        component_name: str,
        metadata: Dict[str, Any],
    ) -> bool:
        entity_data = self._find_entity_by_id_mutable(entity_id)
        if entity_data is None:
            return False
        if component_name not in entity_data.setdefault("components", {}):
            return False
        entity_metadata = entity_data.setdefault("component_metadata", {})
        if not isinstance(entity_metadata, dict):
            entity_metadata = {}
            entity_data["component_metadata"] = entity_metadata
        current_metadata = entity_metadata.get(component_name, {})
        current_metadata = current_metadata if isinstance(current_metadata, dict) else {}
        if current_metadata == metadata:
            return False
        if metadata:
            entity_metadata[component_name] = copy.deepcopy(metadata)
        else:
            entity_metadata.pop(component_name, None)
        if not entity_metadata:
            entity_data.pop("component_metadata", None)
        self._bump_revision()
        return True

    def remove_entity(self, entity_name: str) -> bool:
        if self._find_entity_mutable(entity_name) is None:
            return False
        entities = self._data.get("entities", [])
        for index, entity_data in enumerate(entities):
            if entity_data.get("name") == entity_name:
                del entities[index]
                self._rebuild_entity_index()
                self._bump_revision()
                return True
        return False

    def remove_entity_subtree(self, entity_name: str) -> bool:
        """Remove one serialized entity and every transitive child in one publish."""
        if self._find_entity_mutable(entity_name) is None:
            return False
        names_to_remove = {entity_name}
        changed = True
        while changed:
            changed = False
            for entity_data in self._entities_data():
                if not isinstance(entity_data, dict):
                    continue
                child_name = entity_data.get("name")
                if (
                    isinstance(child_name, str)
                    and child_name not in names_to_remove
                    and entity_data.get("parent") in names_to_remove
                ):
                    names_to_remove.add(child_name)
                    changed = True
        self._data["entities"] = [
            entity_data
            for entity_data in self._entities_data()
            if not isinstance(entity_data, dict)
            or entity_data.get("name") not in names_to_remove
        ]
        self._rebuild_entity_index()
        self._bump_revision()
        return True

    def remove_entity_by_id(self, entity_id: str) -> bool:
        entity_data = self._find_entity_by_id_mutable(entity_id)
        if entity_data is None:
            return False
        entities = self._entities_data()
        for index, candidate in enumerate(entities):
            if candidate is entity_data:
                del entities[index]
                self._rebuild_entity_index()
                self._bump_revision()
                return True
        return False

    def add_component(self, entity_name: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        entity_data = self._find_entity_mutable(entity_name)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        if components.get(component_name) == component_data:
            return False
        components[component_name] = component_data
        if component_name == "SceneEntryPoint":
            self._index_scene_entry(entity_data)
        self._bump_revision()
        return True

    def add_component_by_id(self, entity_id: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        entity_data = self._find_entity_by_id_mutable(entity_id)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        if components.get(component_name) == component_data:
            return False
        components[component_name] = component_data
        if component_name == "SceneEntryPoint":
            self._index_scene_entry(entity_data)
        self._bump_revision()
        return True

    def remove_component(self, entity_name: str, component_name: str) -> bool:
        entity_data = self._find_entity_mutable(entity_name)
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
        self._bump_revision()
        return True

    def remove_component_by_id(self, entity_id: str, component_name: str) -> bool:
        entity_data = self._find_entity_by_id_mutable(entity_id)
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
        self._bump_revision()
        return True

    def set_feature_metadata(self, key: str, value: Any) -> bool:
        if self._feature_metadata().get(key) == value:
            return False
        self._feature_metadata()[key] = value
        self._bump_revision()
        return True

    def remove_feature_metadata(self, key: str) -> bool:
        if key not in self._feature_metadata():
            return False
        del self._feature_metadata()[key]
        self._bump_revision()
        return True

    def find_entity(self, entity_name: str) -> Optional[Dict[str, Any]]:
        self._warn_legacy_surface("find_entity")
        entity_data = self._find_entity_mutable(entity_name)
        return copy.deepcopy(entity_data) if entity_data is not None else None

    def find_entity_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        self._warn_legacy_surface("find_entity_by_id")
        entity_data = self._find_entity_by_id_mutable(entity_id)
        return copy.deepcopy(entity_data) if entity_data is not None else None

    def update_component_by_id(self, entity_id: str, component_name: str, property_name: str, value: Any) -> bool:
        entity_data = self._find_entity_by_id_mutable(entity_id)
        if entity_data is None:
            return False
        components = entity_data.get("components", {})
        if component_name in components:
            if not isinstance(components[component_name], dict) or components[component_name].get(property_name) == value:
                return False
            if component_name == "SceneEntryPoint":
                self._deindex_scene_entry(entity_data)
            components[component_name][property_name] = value
            if component_name == "SceneEntryPoint":
                self._index_scene_entry(entity_data)
            self._bump_revision()
            print(f"[EDIT] Scene: {entity_id}.{component_name}.{property_name} = {value}")
            return True
        return False

    def update_entity_property_by_id(self, entity_id: str, property_name: str, value: Any) -> bool:
        entity_data = self._find_entity_by_id_mutable(entity_id)
        if entity_data is None:
            return False
        if property_name == "name":
            return self.rename_entity_by_id(entity_id, value)
        if property_name == "parent_id":
            return self.reparent_entity_by_id(entity_id, value)
        if property_name == "parent":
            return self.reparent_entity_by_id(entity_id, value)
        if property_name == "groups":
            normalized_groups = list(normalize_entity_groups(value))
            if list(normalize_entity_groups(entity_data.get("groups", ()))) == normalized_groups:
                return False
            if normalized_groups:
                entity_data["groups"] = normalized_groups
            else:
                entity_data.pop("groups", None)
        else:
            if entity_data.get(property_name) == value:
                return False
            entity_data[property_name] = value
        self._bump_revision()
        return True

    def rename_entity_by_id(self, entity_id: str, new_name: Any) -> bool:
        entity_data = self._find_entity_by_id_mutable(entity_id)
        if entity_data is None or not isinstance(new_name, str) or not new_name:
            return False
        old_name = entity_data.get("name")
        if not isinstance(old_name, str):
            return False
        if old_name == new_name:
            return True
        existing = self._find_entity_mutable(new_name)
        if existing is not None and existing is not entity_data:
            return False
        entity_data["name"] = new_name
        self._rename_entity_references(old_name, new_name, entity_id)
        self._rebuild_entity_index()
        self._bump_revision()
        return True

    def reparent_entity_by_id(self, entity_id: str, parent_id: Any) -> bool:
        entity_data = self._find_entity_by_id_mutable(entity_id)
        if entity_data is None:
            return False
        normalized_parent_id = parent_id.strip() if isinstance(parent_id, str) else None
        parent = (
            self._find_entity_by_id_mutable(normalized_parent_id)
            if normalized_parent_id
            else None
        )
        if normalized_parent_id and parent is None:
            return False
        if normalized_parent_id == entity_id:
            return False
        visited = {entity_id}
        current_id = normalized_parent_id
        while current_id:
            if current_id in visited:
                return False
            visited.add(current_id)
            current = self._find_entity_by_id_mutable(current_id)
            if current is None:
                return False
            raw_parent_id = current.get("parent_id")
            if isinstance(raw_parent_id, str) and raw_parent_id.strip():
                current_id = raw_parent_id.strip()
                continue
            current_id = None
        if entity_data.get("parent_id") == normalized_parent_id:
            return False
        entity_data["parent_id"] = normalized_parent_id
        entity_data["parent"] = parent.get("name") if parent is not None else None
        self._bump_revision()
        return True

    def replace_component_data_by_id(self, entity_id: str, component_name: str, component_data: Dict[str, Any]) -> bool:
        entity_data = self._find_entity_by_id_mutable(entity_id)
        if entity_data is None:
            return False
        components = entity_data.setdefault("components", {})
        if component_name not in components:
            return False
        if components[component_name] == component_data:
            return False
        if component_name == "SceneEntryPoint":
            self._deindex_scene_entry(entity_data)
        components[component_name] = component_data
        if component_name == "SceneEntryPoint":
            self._index_scene_entry(entity_data)
        self._bump_revision()
        return True

    def to_dict(self) -> Dict[str, Any]:
        return migrate_scene_data(self._data)

    def to_snapshot_dict(self) -> Dict[str, Any]:
        """Return canonical data while preserving live operation-owned empty shapes."""
        snapshot = self.to_dict()
        empty_override_ids = {
            entity_id.strip()
            for entity_data in self._entities_data()
            if isinstance(entity_data, dict)
            and isinstance((entity_id := entity_data.get("id")), str)
            and entity_id.strip()
            and isinstance((prefab_instance := entity_data.get("prefab_instance")), dict)
            and prefab_instance.get("overrides") == {}
        }
        snapshot_entities = snapshot.get("entities", [])
        if not isinstance(snapshot_entities, list):
            return snapshot
        for entity_data in snapshot_entities:
            if not isinstance(entity_data, dict):
                continue
            entity_id = entity_data.get("id")
            if not isinstance(entity_id, str) or entity_id.strip() not in empty_override_ids:
                continue
            prefab_instance = entity_data.get("prefab_instance")
            if (
                isinstance(prefab_instance, dict)
                and prefab_instance.get("overrides") == {"operations": []}
            ):
                prefab_instance["overrides"] = {}
        return snapshot

    def restore_empty_prefab_override_shapes(self, snapshot_data: Dict[str, Any]) -> None:
        """Restore exact empty override shapes from a trusted in-memory snapshot."""
        snapshot_entities = snapshot_data.get("entities", [])
        if not isinstance(snapshot_entities, list):
            return
        for snapshot_entity in snapshot_entities:
            if not isinstance(snapshot_entity, dict):
                continue
            entity_id = snapshot_entity.get("id")
            if not isinstance(entity_id, str) or not entity_id.strip():
                continue
            snapshot_prefab_instance = snapshot_entity.get("prefab_instance")
            if (
                not isinstance(snapshot_prefab_instance, dict)
                or snapshot_prefab_instance.get("overrides") != {}
            ):
                continue
            entity_data = self._find_entity_by_id_mutable(entity_id.strip())
            if entity_data is None:
                continue
            prefab_instance = entity_data.get("prefab_instance")
            if (
                isinstance(prefab_instance, dict)
                and prefab_instance.get("overrides") == {"operations": []}
            ):
                prefab_instance["overrides"] = {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any], source_path: Optional[str] = None) -> "Scene":
        name = data.get("name", "Untitled")
        return cls(name=name, data=data, source_path=source_path)

    def __repr__(self) -> str:
        entity_count = len(self._entities_data())
        return f"Scene(name='{self._name}', entities={entity_count})"
