"""
engine/ecs/world.py - Contenedor de entidades del juego

PROPÃ“SITO:
    World es el contenedor principal que almacena todas las entidades.
    Incluye clone() para crear copias para RuntimeWorld.
"""

from __future__ import annotations

import copy
from typing import TypeVar

from engine.ecs.component import Component
from engine.ecs.entity import Entity

T = TypeVar("T", bound=Component)


class World:
    """Contenedor principal de todas las entidades del juego."""

    def __init__(self) -> None:
        """Inicializa un mundo vacÃ­o."""
        self._entities: dict[int, Entity] = {}
        self.selected_entity_name: str | None = None
        self.feature_metadata: dict = {}

    def create_entity(self, name: str = "Entity") -> Entity:
        """Crea una nueva entidad y la registra."""
        entity = Entity(name)
        self._entities[entity.id] = entity
        return entity

    def add_entity(self, entity: Entity) -> None:
        """AÃ±ade una entidad existente al mundo."""
        self._entities[entity.id] = entity

    def remove_entity(self, entity_id: int) -> None:
        """Elimina una entidad del mundo por su ID."""
        if entity_id in self._entities:
            del self._entities[entity_id]

    def destroy_entity(self, entity_id: int) -> None:
        """Alias de remove_entity para compatibilidad."""
        self.remove_entity(entity_id)

    def get_entity(self, entity_id: int) -> Entity | None:
        """Obtiene una entidad por su ID."""
        return self._entities.get(entity_id)

    def get_entity_by_name(self, name: str) -> Entity | None:
        """Busca una entidad por su nombre."""
        for entity in self._entities.values():
            if entity.name == name:
                return entity
        return None

    def get_all_entities(self) -> list[Entity]:
        """Retorna lista con todas las entidades."""
        return list(self._entities.values())

    def get_children(self, parent_name: str) -> list[Entity]:
        return [entity for entity in self._entities.values() if entity.parent_name == parent_name]

    def get_descendants(self, parent_name: str) -> list[Entity]:
        descendants: list[Entity] = []
        pending = [parent_name]
        while pending:
            current = pending.pop(0)
            children = self.get_children(current)
            descendants.extend(children)
            pending.extend(child.name for child in children)
        return descendants

    def get_entities_with(self, *component_types: type) -> list[Entity]:
        """Busca entidades que tengan TODOS los componentes especificados."""
        result = []
        for entity in self._entities.values():
            if not entity.active:
                continue
            has_all = all(entity.has_enabled_component(comp_type) for comp_type in component_types)
            if has_all:
                result.append(entity)
        return result

    def entity_count(self) -> int:
        """Retorna el nÃºmero total de entidades."""
        return len(self._entities)

    def clear(self) -> None:
        """Elimina todas las entidades."""
        self._entities.clear()

    def clone(self) -> "World":
        """
        Crea una copia profunda del World.

        Usado para crear RuntimeWorld en modo PLAY.
        """
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
                cloned_component = self._clone_component(component)
                if cloned_component is not None:
                    new_entity.add_component(cloned_component)

            new_world._entities[new_entity.id] = new_entity
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

    def _clone_component(self, component: Component) -> Component | None:
        """Clona un componente usando to_dict/from_dict."""
        component_class = type(component)
        if hasattr(component, "to_dict") and hasattr(component_class, "from_dict"):
            try:
                data = component.to_dict()
                return component_class.from_dict(data)
            except Exception:
                pass

        try:
            new_component = component_class.__new__(component_class)
            for attr_name in dir(component):
                if attr_name.startswith("_"):
                    continue
                if callable(getattr(component, attr_name)):
                    continue
                try:
                    value = getattr(component, attr_name)
                    if isinstance(value, dict):
                        value = value.copy()
                    elif isinstance(value, list):
                        value = value.copy()
                    setattr(new_component, attr_name, value)
                except Exception:
                    pass
            return new_component
        except Exception as exc:
            print(f"[WARNING] World.clone: no se pudo clonar {type(component).__name__}: {exc}")
            return None

    def __repr__(self) -> str:
        return f"World(entities={self.entity_count()})"

    def serialize(self) -> dict:
        """Serializa el World actual para guardado."""
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
                            type(component).__name__: component.to_dict()
                            for component in node.get_all_components()
                            if hasattr(component, "to_dict")
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
                if hasattr(component, "to_dict"):
                    try:
                        ent_data["components"][comp_name] = component.to_dict()
                    except Exception:
                        pass
                else:
                    data = {}
                    for attr in dir(component):
                        if not attr.startswith("_") and not callable(getattr(component, attr)):
                            val = getattr(component, attr)
                            if isinstance(val, (int, float, str, bool, list, dict)):
                                data[attr] = val
                    ent_data["components"][comp_name] = data

            entities_data.append(ent_data)

        return {
            "entities": entities_data,
            "rules": [],
            "feature_metadata": copy.deepcopy(self.feature_metadata),
        }
