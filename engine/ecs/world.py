"""
engine/ecs/world.py - Contenedor de entidades del juego

PROPÓSITO:
    World es el contenedor principal que almacena todas las entidades.
    Incluye clone() para crear copias para RuntimeWorld.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Callable, Iterable, Iterator, TypeVar

from engine.ecs import world_clone as _world_clone
from engine.ecs import world_serialization as _world_serialization
from engine.ecs.component import Component
from engine.ecs.entity import Entity
from engine.ecs.group_registry import GroupRegistry as _GroupRegistry

T = TypeVar("T", bound=Component)
WorldCloneError = _world_clone.WorldCloneError
WorldSerializationError = _world_serialization.WorldSerializationError


class World:
    """Contenedor principal de todas las entidades del juego."""

    def __init__(self) -> None:
        self._entities: dict[int, Entity] = {}
        self._name_index: dict[str, int] = {}
        self._serialized_id_index: dict[str, int] = {}
        self._children_index: dict[str | None, set[int]] = defaultdict(set)
        self._component_index: dict[type, set[int]] = defaultdict(set)
        self._component_owner_index: dict[int, int] = {}
        self._component_query_cache: dict[tuple[type, ...], tuple[int, ...]] = {}
        self._component_query_cache_hits: int = 0
        self._component_query_cache_misses: int = 0
        self._component_query_cache_invalidations: int = 0
        # Legacy compatibility: tests and old callers still poke these fields
        # directly, so keep them available alongside the canonical indexes.
        self._entities_by_name: dict[str, Entity] = {}
        self._entities_by_component: dict[type, list[Entity]] = defaultdict(list)
        self.group_registry = _GroupRegistry(self)
        self._version: int = 0
        self._structure_version: int = 0
        self._transform_version: int = 0
        self._render_version: int = 0
        self._physics_version: int = 0
        self._ui_layout_version: int = 0
        self._selection_version: int = 0
        self._selected_entity_name: str | None = None
        self.feature_metadata: dict = {}
        self.on_entity_destroyed: list[Callable[[Entity], None]] = []

    @property
    def version(self) -> int:
        return self._version

    @property
    def structure_version(self) -> int:
        return self._structure_version

    @property
    def transform_version(self) -> int:
        return self._transform_version

    @property
    def render_version(self) -> int:
        return self._render_version

    @property
    def physics_version(self) -> int:
        return self._physics_version

    @property
    def ui_layout_version(self) -> int:
        return self._ui_layout_version

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

    def touch_transform(self) -> None:
        self._transform_version += 1
        self.touch()

    def touch_render(self) -> None:
        self._render_version += 1
        self.touch()

    def touch_physics(self) -> None:
        self._physics_version += 1
        self.touch()

    def touch_ui_layout(self) -> None:
        self._ui_layout_version += 1
        self.touch()

    def _touch_structure(self) -> None:
        self._structure_version += 1
        self.touch()

    def _touch_component_membership(self, component_type: type | None) -> None:
        self._touch_structure()
        self._touch_component_specific(component_type)

    def _touch_component_specific(self, component_type: type | None) -> None:
        if component_type is None:
            return

        from engine.components.canvas import Canvas
        from engine.components.collider import Collider
        from engine.components.recttransform import RectTransform
        from engine.components.renderorder2d import RenderOrder2D
        from engine.components.renderstyle2d import RenderStyle2D
        from engine.components.sprite import Sprite
        from engine.components.tilemap import Tilemap
        from engine.components.transform import Transform
        from engine.components.uibutton import UIButton

        if issubclass(component_type, Transform):
            self._transform_version += 1
        if issubclass(component_type, Collider):
            self._physics_version += 1
        if issubclass(component_type, (Sprite, Tilemap, RenderOrder2D, RenderStyle2D)):
            self._render_version += 1
        if issubclass(component_type, (RectTransform, Canvas, UIButton)):
            self._ui_layout_version += 1

    def create_entity(self, name: str = "Entity") -> Entity:
        entity = Entity(name)
        self.add_entity(entity)
        return entity

    def add_entity(self, entity: Entity) -> None:
        existing = self._entities.get(entity.id)
        if existing is not None:
            self._deindex_entity(existing)
            self._legacy_remove_name(existing)
            for component in existing.iter_components():
                self._legacy_remove_component_entity(type(component), existing)
            existing._set_owner_world(None)
        self._entities[entity.id] = entity
        entity._set_owner_world(self)
        self._index_entity(entity)
        self._entities_by_name[entity.name] = entity
        for component in entity.iter_components():
            self._legacy_add_component_entity(type(component), entity)
        self._touch_structure()

    def remove_entity(self, entity_id: int) -> None:
        entity = self._entities.get(entity_id)
        if entity is None:
            return
        for callback in list(self.on_entity_destroyed):
            callback(entity)
        self._deindex_entity(entity)
        self._legacy_remove_name(entity)
        for component in entity.iter_components():
            self._legacy_remove_component_entity(type(component), entity)
        entity._set_owner_world(None)
        del self._entities[entity_id]
        if self._selected_entity_name == entity.name:
            self.selected_entity_name = None
        self._touch_structure()

    def destroy_entity(self, entity_id: int) -> None:
        self.remove_entity(entity_id)

    def get_entity(self, entity_id: int) -> Entity | None:
        return self._entities.get(entity_id)

    def get_entity_by_name(self, name: str) -> Entity | None:
        entity_id = self._name_index.get(name)
        if entity_id is not None:
            return self._entities.get(entity_id)
        return self._entities_by_name.get(name)

    def get_entity_by_serialized_id(self, entity_id: str) -> Entity | None:
        normalized = str(entity_id or "").strip()
        if not normalized:
            return None
        runtime_id = self._serialized_id_index.get(normalized)
        return self._entities.get(runtime_id) if runtime_id is not None else None

    def get_entity_by_component_instance(self, component: Component) -> Entity | None:
        entity_id = self._component_owner_index.get(id(component))
        return self._entities.get(entity_id) if entity_id is not None else None

    def has_any_component_type(self, *component_types: type) -> bool:
        """Indica si existe alguna instancia de los tipos de componente dados."""
        for component_type in component_types:
            if self._component_index.get(component_type):
                return True
        for component_type in component_types:
            if self._entities_by_component.get(component_type):
                return True
        return False

    def get_all_entities(self) -> list[Entity]:
        return list(self.iter_all_entities())

    def iter_all_entities(self) -> Iterable[Entity]:
        """Itera todas las entidades sin crear una lista temporal."""
        return self._entities.values()

    def iter_entities(self) -> Iterator[Entity]:
        """Itera entidades activas sin crear una lista temporal."""
        return (entity for entity in self._entities.values() if entity.active)

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
            return list(self.iter_entities())

        query_key = tuple(component_types)
        candidate_ids = self._component_query_cache.get(query_key)
        if candidate_ids is None:
            self._component_query_cache_misses += 1
            if all(component_type in self._component_index for component_type in component_types):
                indexed_sets = [self._component_index[component_type] for component_type in component_types]
                smallest = min(indexed_sets, key=len)
                if len(indexed_sets) == 1:
                    candidate_ids = tuple(sorted(smallest))
                else:
                    intersection = set(smallest)
                    for indexed_ids in indexed_sets:
                        if indexed_ids is not smallest:
                            intersection.intersection_update(indexed_ids)
                        if not intersection:
                            break
                    candidate_ids = tuple(sorted(intersection))
                self._component_query_cache[query_key] = candidate_ids
        else:
            self._component_query_cache_hits += 1

        if candidate_ids is not None:
            return [
                self._entities[entity_id]
                for entity_id in candidate_ids
                if entity_id in self._entities and self._entities[entity_id].active and all(self._entities[entity_id].has_enabled_component(comp_type) for comp_type in component_types)
            ]

        legacy_lists = [self._entities_by_component.get(component_type, ()) for component_type in component_types]
        legacy_seed = min(legacy_lists, key=len)
        fallback_entities = [
            entity
            for entity in legacy_seed
            if entity.active and all(entity.has_enabled_component(comp_type) for comp_type in component_types)
        ]
        if fallback_entities:
            return sorted(fallback_entities, key=lambda entity: entity.id)
        return []

    def entity_count(self) -> int:
        return len(self._entities)

    def clear(self) -> None:
        # Snapshot de entidades para permitir que los observers vean la entidad
        # antes de que sea desindexada, respetando el mismo contrato que remove_entity().
        entidades = list(self._entities.values())
        for entity in entidades:
            for callback in list(self.on_entity_destroyed):
                callback(entity)
        for entity in entidades:
            entity._set_owner_world(None)
        self._entities.clear()
        self._name_index.clear()
        self._serialized_id_index.clear()
        self._children_index.clear()
        self._component_index.clear()
        self._component_owner_index.clear()
        self._clear_component_query_cache()
        self._entities_by_name.clear()
        self._entities_by_component.clear()
        self.group_registry.clear()
        self.selected_entity_name = None
        self._touch_structure()

    def clone(self) -> "World":
        return _world_clone.clone_world(self, world_factory=World)

    def _adopt_entities(self, entities: Iterable[Entity]) -> None:
        for entity in entities:
            self._entities[entity.id] = entity
            entity._set_owner_world(self)
            self._entities_by_name[entity.name] = entity
            for component in entity.iter_components():
                self._legacy_add_component_entity(type(component), entity)
        self._rebuild_indexes()
        self._touch_structure()

    def _rebuild_indexes(self) -> None:
        self._name_index.clear()
        self._serialized_id_index.clear()
        self._children_index.clear()
        self._component_index.clear()
        self._component_owner_index.clear()
        self._clear_component_query_cache()
        self.group_registry.clear()
        for entity in self._entities.values():
            self._index_entity(entity)

    def _index_entity(self, entity: Entity) -> None:
        self._name_index[entity.name] = entity.id
        serialized_id = self._normalize_serialized_id(getattr(entity, "serialized_id", None))
        if serialized_id is not None:
            self._serialized_id_index[serialized_id] = entity.id
        self._children_index[entity.parent_name].add(entity.id)
        self.group_registry.register_entity(entity)
        for component in entity.iter_components():
            self._index_component(entity, type(component), component)

    def _deindex_entity(self, entity: Entity) -> None:
        if self._name_index.get(entity.name) == entity.id:
            del self._name_index[entity.name]
        serialized_id = self._normalize_serialized_id(getattr(entity, "serialized_id", None))
        if serialized_id is not None and self._serialized_id_index.get(serialized_id) == entity.id:
            del self._serialized_id_index[serialized_id]
        child_ids = self._children_index.get(entity.parent_name)
        if child_ids is not None:
            child_ids.discard(entity.id)
            if not child_ids:
                self._children_index.pop(entity.parent_name, None)
        self.group_registry.unregister_entity(entity)
        for component in entity.iter_components():
            self._deindex_component(entity, type(component), component)

    def _index_component(self, entity: Entity, component_type: type, component: Component) -> None:
        self._component_index[component_type].add(entity.id)
        self._component_owner_index[id(component)] = entity.id
        self._invalidate_component_query_cache(component_type)

    def _deindex_component(self, entity: Entity, component_type: type, component: Component) -> None:
        component_ids = self._component_index.get(component_type)
        if component_ids is not None:
            component_ids.discard(entity.id)
            if not component_ids:
                self._component_index.pop(component_type, None)
        self._component_owner_index.pop(id(component), None)
        self._invalidate_component_query_cache(component_type)

    def _clear_component_query_cache(self) -> None:
        if self._component_query_cache:
            self._component_query_cache_invalidations += len(self._component_query_cache)
            self._component_query_cache.clear()

    def _invalidate_component_query_cache(self, component_type: type) -> None:
        stale_keys = [
            query_key
            for query_key in self._component_query_cache
            if component_type in query_key
        ]
        for query_key in stale_keys:
            del self._component_query_cache[query_key]
        self._component_query_cache_invalidations += len(stale_keys)

    def _legacy_remove_name(self, entity: Entity) -> None:
        if self._entities_by_name.get(entity.name) is entity:
            self._entities_by_name.pop(entity.name, None)

    def _legacy_add_component_entity(self, component_type: type, entity: Entity) -> None:
        self._entities_by_component[component_type].append(entity)

    def _legacy_remove_component_entity(self, component_type: type, entity: Entity) -> None:
        entities = self._entities_by_component.get(component_type)
        if entities is None:
            return
        try:
            entities.remove(entity)
        except ValueError:
            return
        if not entities:
            self._entities_by_component.pop(component_type, None)

    @staticmethod
    def _normalize_serialized_id(value: object) -> str | None:
        normalized = str(value or "").strip()
        return normalized if normalized else None

    def _on_entity_changed(self, entity: Entity, event: str, **payload: object) -> None:
        if entity.id not in self._entities:
            return

        if event == "entity_field_changed":
            field = str(payload.get("field", ""))
            previous = payload.get("previous")
            current = payload.get("current")
            if field == "name":
                if previous is not None:
                    if self._entities_by_name.get(str(previous)) is entity:
                        del self._entities_by_name[str(previous)]
                    if self._name_index.get(str(previous)) == entity.id:
                        del self._name_index[str(previous)]
                self._name_index[str(current)] = entity.id
                self._entities_by_name[str(current)] = entity
                self.group_registry.entity_renamed(entity)
                if self._selected_entity_name == previous:
                    self.selected_entity_name = str(current)
            elif field == "serialized_id":
                previous_id = self._normalize_serialized_id(previous)
                if previous_id is not None and self._serialized_id_index.get(previous_id) == entity.id:
                    del self._serialized_id_index[previous_id]
                current_id = self._normalize_serialized_id(current)
                if current_id is not None:
                    self._serialized_id_index[current_id] = entity.id
            elif field == "parent_name":
                previous_parent = str(previous) if previous is not None else None
                current_parent = str(current) if current is not None else None
                previous_children = self._children_index.get(previous_parent)
                if previous_children is not None:
                    previous_children.discard(entity.id)
                    if not previous_children:
                        self._children_index.pop(previous_parent, None)
                self._children_index[current_parent].add(entity.id)
            elif field == "groups":
                self.group_registry.update_entity_groups(entity, previous, current)
            if field in {"name", "parent_name", "groups", "active"}:
                self._touch_structure()
            else:
                self.touch()
            return

        if event == "component_added":
            component_type = payload.get("component_type")
            previous_component = payload.get("previous_component")
            component = payload.get("component")
            if isinstance(component_type, type) and isinstance(previous_component, Component):
                self._deindex_component(entity, component_type, previous_component)
                self._legacy_remove_component_entity(component_type, entity)
            if isinstance(component_type, type) and isinstance(component, Component):
                self._index_component(entity, component_type, component)
                self._legacy_add_component_entity(component_type, entity)
            self._touch_component_membership(component_type if isinstance(component_type, type) else None)
            return

        if event == "component_removed":
            component_type = payload.get("component_type")
            component = payload.get("component")
            if isinstance(component_type, type) and isinstance(component, Component):
                self._deindex_component(entity, component_type, component)
                self._legacy_remove_component_entity(component_type, entity)
            self._touch_component_membership(component_type if isinstance(component_type, type) else None)
            return

        if event == "component_metadata_changed":
            self.touch()

    def __repr__(self) -> str:
        return f"World(entities={self.entity_count()}, version={self.version})"

    def serialize(self) -> dict:
        return _world_serialization.serialize_world(self)
