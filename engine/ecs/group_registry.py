"""Indice runtime de grupos para consultas rapidas por entidad."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from engine.ecs.entity import Entity, normalize_entity_groups

if TYPE_CHECKING:
    from engine.ecs.world import World


class GroupRegistry:
    """Indice runtime de grupos para consultas rapidas por entidad."""

    def __init__(self, world: World) -> None:
        self._world = world
        self._group_index: dict[str, set[int]] = defaultdict(set)
        self._ordered_entity_ids: dict[str, tuple[int, ...]] = {}
        self._ordered_group_names: tuple[str, ...] | None = None

    def clear(self) -> None:
        self._group_index.clear()
        self._ordered_entity_ids.clear()
        self._ordered_group_names = None

    def _invalidate_group(self, group_name: str) -> None:
        self._ordered_entity_ids.pop(group_name, None)

    def entity_renamed(self, entity: Entity) -> None:
        for group_name in entity.groups:
            self._invalidate_group(group_name)

    def register_entity(self, entity: Entity) -> None:
        for group_name in entity.groups:
            self._group_index[group_name].add(entity.id)
            self._invalidate_group(group_name)
        if entity.groups:
            self._ordered_group_names = None

    def unregister_entity(self, entity: Entity, groups: Any = None) -> None:
        normalized_groups = normalize_entity_groups(entity.groups if groups is None else groups)
        for group_name in normalized_groups:
            member_ids = self._group_index.get(group_name)
            if member_ids is None:
                continue
            member_ids.discard(entity.id)
            self._invalidate_group(group_name)
            if not member_ids:
                self._group_index.pop(group_name, None)
                self._ordered_group_names = None

    def update_entity_groups(self, entity: Entity, previous_groups: Any, current_groups: Any) -> None:
        previous = set(normalize_entity_groups(previous_groups))
        current = set(normalize_entity_groups(current_groups))
        for group_name in previous - current:
            member_ids = self._group_index.get(group_name)
            if member_ids is None:
                continue
            member_ids.discard(entity.id)
            self._invalidate_group(group_name)
            if not member_ids:
                self._group_index.pop(group_name, None)
        for group_name in current - previous:
            self._group_index[group_name].add(entity.id)
            self._invalidate_group(group_name)
        if previous != current:
            self._ordered_group_names = None

    def list_groups(self) -> list[str]:
        if self._ordered_group_names is None:
            self._ordered_group_names = tuple(sorted(self._group_index))
        return list(self._ordered_group_names)

    def get_entity_names(self, group_name: str) -> list[str]:
        return [
            self._world._entities[entity_id].name
            for entity_id in self._get_ordered_entity_ids(group_name)
            if entity_id in self._world._entities
        ]

    def get_entities(self, group_name: str) -> list[Entity]:
        return [
            self._world._entities[entity_id]
            for entity_id in self._get_ordered_entity_ids(group_name)
            if entity_id in self._world._entities
        ]

    def _get_ordered_entity_ids(self, group_name: str) -> tuple[int, ...]:
        normalized_group = str(group_name or "").strip()
        if not normalized_group:
            return ()
        ordered_ids = self._ordered_entity_ids.get(normalized_group)
        if ordered_ids is None:
            member_ids = self._group_index.get(normalized_group)
            if not member_ids:
                return ()
            ordered_ids = tuple(
                sorted(
                    member_ids,
                    key=lambda entity_id: self._world._entities[entity_id].name,
                )
            )
            self._ordered_entity_ids[normalized_group] = ordered_ids
        return ordered_ids

    def has(self, group_name: str, entity_name: str) -> bool:
        entity = self._world.get_entity_by_name(entity_name)
        return entity is not None and self.has_entity(group_name, entity)

    def has_entity(self, group_name: str, entity: Entity) -> bool:
        """Comprueba si una entidad concreta pertenece al grupo por su id."""
        normalized_group = str(group_name or "").strip()
        if not normalized_group:
            return False
        return entity.id in self._group_index.get(normalized_group, set())

    def get_first_entity(self, group_name: str) -> Entity | None:
        """Obtiene la primera entidad activa del grupo, o None si está vacío."""
        for entity_id in self._get_ordered_entity_ids(group_name):
            ent = self._world._entities.get(entity_id)
            if ent is None:
                continue
            if ent.active:
                return ent
        return None

    def count(self, group_name: str) -> int:
        """Número de entidades actualmente en el grupo."""
        normalized_group = str(group_name or "").strip()
        if not normalized_group:
            return 0
        return len(self._group_index.get(normalized_group, set()))

    def is_empty(self, group_name: str) -> bool:
        """Indica si el grupo no tiene miembros."""
        return self.count(group_name) == 0
