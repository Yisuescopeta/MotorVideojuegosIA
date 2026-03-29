"""
engine/ecs/world.py - Contenedor de entidades del juego

PROPÓSITO:
    World es el contenedor principal que almacena todas las entidades.
    Incluye clone() para crear copias para RuntimeWorld.
"""

from __future__ import annotations

import copy
from collections import defaultdict, deque
from typing import Any, TypeVar

from engine.ecs.component import Component
from engine.ecs.entity import Entity

T = TypeVar("T", bound=Component)


class WorldCloneError(RuntimeError):
    """Se lanza cuando el runtime world no puede clonarse de forma segura."""


class WorldSerializationError(RuntimeError):
    """Se lanza cuando la serializacion de la escena perderia datos."""


class World:
    """Contenedor principal de todas las entidades del juego."""

    def __init__(self) -> None:
        self._entities: dict[int, Entity] = {}
        self._name_index: dict[str, int] = {}
        self._children_index: dict[str | None, set[int]] = defaultdict(set)
        self._component_index: dict[type, set[int]] = defaultdict(set)
        self._component_owner_index: dict[int, int] = {}
        self._version: int = 0
        self._selection_version: int = 0
        self._selected_entity_name: str | None = None
        self.feature_metadata: dict = {}

    @property
    def version(self) -> int:
        return self._version

    @property
    def selection_version(self) -> int:
        return self._selection_version

    @property
    def selected_entity_name(self) -> str | None:
        return self._selected_entity_name

    @selected_entity_name.setter
    def selected_entity_name(self, value: str | None) -> None:
        normalized = str(value) if value else None
        if self._selected_entity_name == normalized:
            return
        self._selected_entity_name = normalized
        self._selection_version += 1

    def touch(self) -> None:
        self._version += 1

    def create_entity(self, name: str = "Entity") -> Entity:
        entity = Entity(name)
        self.add_entity(entity)
        return entity

    def add_entity(self, entity: Entity) -> None:
        existing = self._entities.get(entity.id)
        if existing is not None:
            self._deindex_entity(existing)
            existing._set_owner_world(None)
        self._entities[entity.id] = entity
        entity._set_owner_world(self)
        self._index_entity(entity)
        self.touch()

    def remove_entity(self, entity_id: int) -> None:
        entity = self._entities.get(entity_id)
        if entity is None:
            return
        self._deindex_entity(entity)
        entity._set_owner_world(None)
        del self._entities[entity_id]
        if self._selected_entity_name == entity.name:
            self.selected_entity_name = None
        self.touch()

    def destroy_entity(self, entity_id: int) -> None:
        self.remove_entity(entity_id)

    def get_entity(self, entity_id: int) -> Entity | None:
        return self._entities.get(entity_id)

    def get_entity_by_name(self, name: str) -> Entity | None:
        entity_id = self._name_index.get(name)
        return self._entities.get(entity_id) if entity_id is not None else None

    def get_entity_by_component_instance(self, component: Component) -> Entity | None:
        entity_id = self._component_owner_index.get(id(component))
        return self._entities.get(entity_id) if entity_id is not None else None

    def get_all_entities(self) -> list[Entity]:
        return list(self._entities.values())

    def get_children(self, parent_name: str | None) -> list[Entity]:
        child_ids = self._children_index.get(parent_name, set())
        return [self._entities[entity_id] for entity_id in sorted(child_ids) if entity_id in self._entities]

    def get_descendants(self, parent_name: str) -> list[Entity]:
        descendants: list[Entity] = []
        pending = deque([parent_name])
        while pending:
            current = pending.popleft()
            children = self.get_children(current)
            descendants.extend(children)
            pending.extend(child.name for child in children)
        return descendants

    def get_entities_with(self, *component_types: type) -> list[Entity]:
        if not component_types:
            return [entity for entity in self._entities.values() if entity.active]

        candidate_ids: set[int] | None = None
        for component_type in component_types:
            indexed_ids = self._component_index.get(component_type, set())
            candidate_ids = set(indexed_ids) if candidate_ids is None else candidate_ids.intersection(indexed_ids)
            if not candidate_ids:
                return []

        return [
            self._entities[entity_id]
            for entity_id in sorted(candidate_ids or set())
            if entity_id in self._entities and self._entities[entity_id].active and all(self._entities[entity_id].has_enabled_component(comp_type) for comp_type in component_types)
        ]

    def entity_count(self) -> int:
        return len(self._entities)

    def clear(self) -> None:
        for entity in self._entities.values():
            entity._set_owner_world(None)
        self._entities.clear()
        self._name_index.clear()
        self._children_index.clear()
        self._component_index.clear()
        self._component_owner_index.clear()
        self.selected_entity_name = None
        self.touch()

    def clone(self) -> "World":
        new_world = World()
        new_world.feature_metadata = copy.deepcopy(self.feature_metadata)
        pending_links: list[tuple[Entity, str]] = []

        for entity in self._entities.values():
            new_entity = Entity(entity.name)
            new_entity.active = entity.active
            new_entity.tag = entity.tag
            new_entity.layer = entity.layer
            new_entity.parent_name = entity.parent_name
            new_entity.prefab_instance = copy.deepcopy(entity.prefab_instance)
            new_entity.prefab_source_path = entity.prefab_source_path
            new_entity.prefab_root_name = entity.prefab_root_name

            for component in entity.get_all_components():
                cloned_component = self._clone_component(component, entity_name=entity.name)
                new_entity.add_component(
                    cloned_component,
                    metadata=entity.get_component_metadata(type(component)),
                )

            new_world.add_entity(new_entity)
            if new_entity.parent_name:
                pending_links.append((new_entity, new_entity.parent_name))

        self._link_parent_transforms(new_world, pending_links)
        new_world.selected_entity_name = self.selected_entity_name
        return new_world

    def _link_parent_transforms(self, world: "World", pending_links: list[tuple[Entity, str]]) -> None:
        from engine.components.transform import Transform

        for entity, parent_name in pending_links:
            parent = world.get_entity_by_name(parent_name)
            if parent is None:
                continue
            child_transform = entity.get_component(Transform)
            parent_transform = parent.get_component(Transform)
            if child_transform is None:
                continue
            if child_transform.parent and child_transform in child_transform.parent.children:
                child_transform.parent.children.remove(child_transform)
            child_transform.parent = parent_transform
            if parent_transform is not None and child_transform not in parent_transform.children:
                parent_transform.children.append(child_transform)

    def _clone_component(self, component: Component, *, entity_name: str) -> Component:
        component_class = type(component)
        serialize_error: Exception | None = None
        if hasattr(component, "to_dict") and hasattr(component_class, "from_dict"):
            try:
                data = component.to_dict()
                return component_class.from_dict(data)
            except Exception as exc:
                serialize_error = exc

        try:
            return copy.deepcopy(component)
        except Exception as exc:
            detail = f"{entity_name}.{component_class.__name__}"
            if serialize_error is not None:
                raise WorldCloneError(
                    f"World.clone: no se pudo clonar {detail}; to_dict/from_dict fallo: {serialize_error}; deepcopy fallo: {exc}"
                ) from exc
            raise WorldCloneError(
                f"World.clone: no se pudo clonar {detail}; deepcopy fallo: {exc}"
            ) from exc

    def _serialize_component(self, entity: Entity, component: Component) -> dict[str, Any]:
        component_name = type(component).__name__
        if hasattr(component, "to_dict"):
            try:
                return component.to_dict()
            except Exception as exc:
                raise WorldSerializationError(
                    f"World.serialize: no se pudo serializar {entity.name}.{component_name}: {exc}"
                ) from exc

        data: dict[str, Any] = {}
        for attr in dir(component):
            if attr.startswith("_"):
                continue
            try:
                value = getattr(component, attr)
            except Exception as exc:
                raise WorldSerializationError(
                    f"World.serialize: no se pudo leer {entity.name}.{component_name}.{attr}: {exc}"
                ) from exc
            if callable(value):
                continue
            if isinstance(value, (int, float, str, bool, list, dict)):
                data[attr] = value
        return data

    def _index_entity(self, entity: Entity) -> None:
        self._name_index[entity.name] = entity.id
        self._children_index[entity.parent_name].add(entity.id)
        for component in entity.get_all_components():
            self._index_component(entity, type(component), component)

    def _deindex_entity(self, entity: Entity) -> None:
        if self._name_index.get(entity.name) == entity.id:
            del self._name_index[entity.name]
        child_ids = self._children_index.get(entity.parent_name)
        if child_ids is not None:
            child_ids.discard(entity.id)
            if not child_ids:
                self._children_index.pop(entity.parent_name, None)
        for component in entity.get_all_components():
            self._deindex_component(entity, type(component), component)

    def _index_component(self, entity: Entity, component_type: type, component: Component) -> None:
        self._component_index[component_type].add(entity.id)
        self._component_owner_index[id(component)] = entity.id

    def _deindex_component(self, entity: Entity, component_type: type, component: Component) -> None:
        component_ids = self._component_index.get(component_type)
        if component_ids is not None:
            component_ids.discard(entity.id)
            if not component_ids:
                self._component_index.pop(component_type, None)
        self._component_owner_index.pop(id(component), None)

    def _on_entity_changed(self, entity: Entity, event: str, **payload: object) -> None:
        if entity.id not in self._entities:
            return

        if event == "entity_field_changed":
            field = str(payload.get("field", ""))
            previous = payload.get("previous")
            current = payload.get("current")
            if field == "name":
                if previous is not None and self._name_index.get(str(previous)) == entity.id:
                    del self._name_index[str(previous)]
                self._name_index[str(current)] = entity.id
                if self._selected_entity_name == previous:
                    self.selected_entity_name = str(current)
            elif field == "parent_name":
                previous_children = self._children_index.get(previous)
                if previous_children is not None:
                    previous_children.discard(entity.id)
                    if not previous_children:
                        self._children_index.pop(previous, None)
                self._children_index[current].add(entity.id)
            self.touch()
            return

        if event == "component_added":
            component_type = payload.get("component_type")
            previous_component = payload.get("previous_component")
            component = payload.get("component")
            if previous_component is not None and component_type is not None:
                self._deindex_component(entity, component_type, previous_component)
            if component_type is not None and component is not None:
                self._index_component(entity, component_type, component)
            self.touch()
            return

        if event == "component_removed":
            component_type = payload.get("component_type")
            component = payload.get("component")
            if component_type is not None and component is not None:
                self._deindex_component(entity, component_type, component)
            self.touch()
            return

        if event == "component_metadata_changed":
            self.touch()

    def __repr__(self) -> str:
        return f"World(entities={self.entity_count()}, version={self.version})"

    def serialize(self) -> dict:
        entities_data = []
        consumed_prefab_entities: set[str] = set()
        for entity in self._entities.values():
            if entity.name in consumed_prefab_entities:
                continue

            if entity.prefab_instance is not None and entity.prefab_source_path in (None, ""):
                subtree = [entity] + self.get_descendants(entity.name)
                overrides = {}
                for node in subtree:
                    relative_path = node.prefab_source_path or ""
                    overrides[relative_path] = {
                        "active": node.active,
                        "tag": node.tag,
                        "layer": node.layer,
                        "components": {
                            type(component).__name__: self._serialize_component(node, component)
                            for component in node.get_all_components()
                        },
                    }
                    consumed_prefab_entities.add(node.name)
                entities_data.append(
                    {
                        "name": entity.name,
                        "active": entity.active,
                        "tag": entity.tag,
                        "layer": entity.layer,
                        "parent": entity.parent_name,
                        "prefab_instance": {
                            "prefab_path": entity.prefab_instance.get("prefab_path", ""),
                            "root_name": entity.prefab_instance.get("root_name", entity.name),
                            "overrides": overrides,
                        },
                    }
                )
                continue

            ent_data = {
                "name": entity.name,
                "active": entity.active,
                "tag": entity.tag,
                "layer": entity.layer,
                "components": {},
            }
            if entity.parent_name is not None:
                ent_data["parent"] = entity.parent_name
            if entity.prefab_instance is not None:
                ent_data["prefab_instance"] = copy.deepcopy(entity.prefab_instance)
            if entity.prefab_source_path is not None:
                ent_data["prefab_source_path"] = entity.prefab_source_path
            if entity.prefab_root_name is not None:
                ent_data["prefab_root_name"] = entity.prefab_root_name

            for component in entity.get_all_components():
                comp_name = type(component).__name__
                ent_data["components"][comp_name] = self._serialize_component(entity, component)

                metadata = entity.get_component_metadata(type(component))
                if metadata:
                    ent_data.setdefault("component_metadata", {})[comp_name] = copy.deepcopy(metadata)

            entities_data.append(ent_data)

        return {
            "entities": entities_data,
            "rules": [],
            "feature_metadata": copy.deepcopy(self.feature_metadata),
        }
