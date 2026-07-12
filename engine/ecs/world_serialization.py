"""Serializacion de World sin dependencias de runtime, editor o sistemas."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

from engine.ecs.component import (
    Component,
    LegacyComponentSerializationWarning,
    has_explicit_serialization_contract,
    has_explicit_to_dict,
    is_official_component_type,
)
from engine.ecs.entity import Entity
from engine.serialization.json_value import clone_json_value

if TYPE_CHECKING:
    from engine.ecs.world import World


class WorldSerializationError(RuntimeError):
    """Se lanza cuando la serializacion de la escena perderia datos."""


def _serialize_component(entity: Entity, component: Component) -> dict[str, Any]:
    component_type = type(component)
    component_name = component_type.__name__
    has_contract = has_explicit_serialization_contract(component_type)

    if is_official_component_type(component_type) and not has_contract:
        raise WorldSerializationError(
            "World.serialize: componente oficial "
            f"{entity.name}.{component_name} debe implementar to_dict()/from_dict() explicitos"
        )

    has_incomplete_legacy_contract = has_explicit_to_dict(component_type) and not has_contract

    try:
        payload = component.to_dict()
    except Exception as exc:
        raise WorldSerializationError(
            f"World.serialize: no se pudo serializar {entity.name}.{component_name}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WorldSerializationError(
            "World.serialize: "
            f"{entity.name}.{component_name}.to_dict() debe devolver dict, "
            f"no {type(payload).__name__}"
        )
    if has_incomplete_legacy_contract:
        warnings.warn(
            (
                f"{component_type.__module__}.{component_name} tiene un contrato "
                "de serializacion legacy incompleto; implemente from_dict() explicito"
            ),
            LegacyComponentSerializationWarning,
            stacklevel=3,
        )
    return payload


def serialize_world(source: World) -> dict[str, Any]:
    """Serializa un World preservando payload, orden y compatibilidad legacy."""
    entities_data = []
    consumed_prefab_entities: set[str] = set()
    for entity in source.iter_all_entities():
        if entity.name in consumed_prefab_entities:
            continue

        if entity.prefab_instance is not None and entity.prefab_source_path in (None, ""):
            subtree = [entity] + source.get_descendants(entity.name)
            overrides = {}
            for node in subtree:
                relative_path = node.prefab_source_path or ""
                components = {}
                for component in node.iter_components():
                    components[type(component).__name__] = _serialize_component(node, component)
                override_data = {
                    "active": node.active,
                    "tag": node.tag,
                    "layer": node.layer,
                    "components": components,
                }
                if node.groups:
                    override_data["groups"] = list(node.groups)
                overrides[relative_path] = override_data
                consumed_prefab_entities.add(node.name)
            prefab_entity_data = {
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
            if entity.groups:
                prefab_entity_data["groups"] = list(entity.groups)
            entities_data.append(prefab_entity_data)
            continue

        ent_data: dict[str, Any] = {
            "name": entity.name,
            "active": entity.active,
            "tag": entity.tag,
            "layer": entity.layer,
            "components": {},
        }
        if entity.groups:
            ent_data["groups"] = list(entity.groups)
        if entity.parent_name is not None:
            ent_data["parent"] = entity.parent_name
        if entity.prefab_instance is not None:
            ent_data["prefab_instance"] = clone_json_value(entity.prefab_instance)
        if entity.prefab_source_path is not None:
            ent_data["prefab_source_path"] = entity.prefab_source_path
        if entity.prefab_root_name is not None:
            ent_data["prefab_root_name"] = entity.prefab_root_name

        for component in entity.iter_components():
            comp_name = type(component).__name__
            ent_data["components"][comp_name] = _serialize_component(entity, component)

            metadata = entity._get_component_metadata_ref(type(component))
            if metadata:
                ent_data.setdefault("component_metadata", {})[comp_name] = clone_json_value(metadata)

        entities_data.append(ent_data)

    return {
        "entities": entities_data,
        "rules": [],
        "feature_metadata": clone_json_value(source.feature_metadata),
    }
