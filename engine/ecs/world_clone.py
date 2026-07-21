"""Clonacion de World sin dependencias de runtime, editor o sistemas."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Callable

from engine.ecs.component import Component
from engine.ecs.entity import Entity
from engine.serialization.json_value import clone_json_value

if TYPE_CHECKING:
    from engine.ecs.world import World


class WorldCloneError(RuntimeError):
    """Se lanza cuando el runtime world no puede clonarse de forma segura."""


def _clone_component(component: Component, *, entity_name: str) -> Component:
    component_class = type(component)
    clone_error: Exception | None = None
    try:
        return component.clone()
    except Exception as exc:
        clone_error = exc

    try:
        return copy.deepcopy(component)
    except Exception as exc:
        detail = f"{entity_name}.{component_class.__name__}"
        if clone_error is not None:
            raise WorldCloneError(
                f"World.clone: no se pudo clonar {detail}; clone() fallo: {clone_error}; deepcopy fallo: {exc}"
            ) from exc
        raise WorldCloneError(
            f"World.clone: no se pudo clonar {detail}; deepcopy fallo: {exc}"
        ) from exc


def _link_parent_transforms(world: World, pending_links: list[tuple[Entity, str]]) -> None:
    from engine.components.transform import Transform

    for entity, parent_name in pending_links:
        parent = world.get_entity_by_name(parent_name)
        if parent is None:
            continue
        child_transform = entity.get_component(Transform)
        parent_transform = parent.get_component(Transform)
        if child_transform is None:
            continue
        child_transform.parent = parent_transform


def clone_world(source: World, *, world_factory: Callable[[], World]) -> World:
    """Clona un World preservando estado, orden e aislamiento mutable."""
    new_world = world_factory()
    new_world.feature_metadata = clone_json_value(source.feature_metadata)
    pending_links: list[tuple[Entity, str]] = []
    cloned_entities: list[Entity] = []

    for entity in source.iter_all_entities():
        new_entity = Entity(entity.name)
        new_entity.serialized_id = getattr(entity, "serialized_id", None)
        new_entity.active = entity.active
        new_entity.tag = entity.tag
        new_entity.layer = entity.layer
        new_entity.groups = entity.groups
        new_entity.parent_name = entity.parent_name
        new_entity.prefab_instance = clone_json_value(entity.prefab_instance)
        new_entity.prefab_source_path = entity.prefab_source_path
        new_entity.prefab_root_name = entity.prefab_root_name

        for component in entity.iter_components():
            cloned_component = _clone_component(component, entity_name=entity.name)
            new_entity.add_component(
                cloned_component,
                metadata=entity._get_component_metadata_ref(type(component)),
            )

        cloned_entities.append(new_entity)
        if new_entity.parent_name:
            pending_links.append((new_entity, new_entity.parent_name))

    new_world._adopt_entities(cloned_entities)
    _link_parent_transforms(new_world, pending_links)
    new_world.selected_entity_name = source.selected_entity_name
    new_world._version = source._version
    new_world._structure_version = source._structure_version
    new_world._transform_version = source._transform_version
    new_world._render_version = source._render_version
    new_world._physics_version = source._physics_version
    new_world._ui_layout_version = source._ui_layout_version
    new_world._selection_version = source._selection_version
    return new_world
