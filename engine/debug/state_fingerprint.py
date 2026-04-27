from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


def _normalize_scalar(value: Any, float_precision: int) -> Any:
    if isinstance(value, float):
        return round(value, float_precision)
    return value


def _normalize_value(value: Any, float_precision: int) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize_value(value[key], float_precision)
            for key in sorted(value.keys(), key=lambda item: str(item))
        }
    if isinstance(value, list):
        return [_normalize_value(item, float_precision) for item in value]
    if isinstance(value, tuple):
        return [_normalize_value(item, float_precision) for item in value]
    return _normalize_scalar(value, float_precision)


def world_state_payload(world: Any, *, float_precision: int = 6) -> dict[str, Any]:
    entities: list[dict[str, Any]] = []
    world_entities = world.iter_all_entities() if hasattr(world, "iter_all_entities") else world.get_all_entities()
    for entity in sorted(world_entities, key=lambda item: item.name):
        components: dict[str, Any] = {}
        metadata: dict[str, Any] = {}
        entity_components = entity.iter_components() if hasattr(entity, "iter_components") else entity.get_all_components()
        for component in sorted(entity_components, key=lambda item: type(item).__name__):
            component_name = type(component).__name__
            if hasattr(component, "to_dict"):
                components[component_name] = _normalize_value(component.to_dict(), float_precision)
            else:
                raw_payload = {}
                for attr_name in dir(component):
                    if attr_name.startswith("_"):
                        continue
                    attr_value = getattr(component, attr_name)
                    if callable(attr_value):
                        continue
                    if isinstance(attr_value, (int, float, str, bool, list, dict, tuple, type(None))):
                        raw_payload[attr_name] = attr_value
                components[component_name] = _normalize_value(raw_payload, float_precision)
            component_metadata = entity.get_component_metadata(type(component))
            if component_metadata:
                metadata[component_name] = _normalize_value(component_metadata, float_precision)
        entity_payload: dict[str, Any] = {
            "name": entity.name,
            "active": entity.active,
            "tag": entity.tag,
            "layer": entity.layer,
            "parent": entity.parent_name,
            "components": components,
        }
        if entity.prefab_instance is not None:
            entity_payload["prefab_instance"] = _normalize_value(copy.deepcopy(entity.prefab_instance), float_precision)
        if entity.prefab_source_path is not None:
            entity_payload["prefab_source_path"] = entity.prefab_source_path
        if entity.prefab_root_name is not None:
            entity_payload["prefab_root_name"] = entity.prefab_root_name
        if metadata:
            entity_payload["component_metadata"] = metadata
        entities.append(entity_payload)
    return {
        "selected_entity_name": world.selected_entity_name,
        "feature_metadata": _normalize_value(copy.deepcopy(world.feature_metadata), float_precision),
        "entities": entities,
    }


def compute_world_hash(world: Any, *, float_precision: int = 6) -> str:
    payload = world_state_payload(world, float_precision=float_precision)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def world_fingerprint(
    world: Any,
    *,
    frame: int | None = None,
    time: float | None = None,
    float_precision: int = 6,
) -> dict[str, Any]:
    payload = world_state_payload(world, float_precision=float_precision)
    return {
        "frame": frame,
        "time": round(time, float_precision) if time is not None else None,
        "entity_count": len(payload["entities"]),
        "selected_entity_name": payload["selected_entity_name"],
        "world_hash": compute_world_hash(world, float_precision=float_precision),
        "state": payload,
    }
