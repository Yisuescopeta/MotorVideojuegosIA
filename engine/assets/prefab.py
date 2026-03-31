"""
engine/assets/prefab.py - Sistema de Prefabs
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Optional

from engine.ecs.entity import Entity
from engine.ecs.world import World
from engine.serialization.schema import migrate_prefab_data, validate_prefab_data


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = copy.deepcopy(base)
        for key, value in override.items():
            merged[key] = _deep_merge(merged.get(key), value) if key in merged else copy.deepcopy(value)
        return merged
    return copy.deepcopy(override)


def _normalize_legacy_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    if "operations" in overrides:
        return copy.deepcopy(overrides)
    operations: list[dict[str, Any]] = []
    for target_path, payload in overrides.items():
        if not isinstance(payload, dict):
            continue
        for field_name in ("active", "tag", "layer", "parent"):
            if field_name in payload:
                operations.append(
                    {
                        "op": "set_entity_property",
                        "target": target_path,
                        "field": field_name,
                        "value": copy.deepcopy(payload[field_name]),
                    }
                )
        components = payload.get("components", {})
        if isinstance(components, dict):
            for component_name, component_payload in components.items():
                if not isinstance(component_payload, dict):
                    continue
                operations.append(
                    {
                        "op": "replace_component",
                        "target": target_path,
                        "component": component_name,
                        "data": copy.deepcopy(component_payload),
                    }
                )
    return {"operations": operations}


def _reorder_entities(entities: list[dict[str, Any]], parent: str | None, child_name: str, index: int) -> None:
    matching = [item for item in entities if item.get("parent") == parent]
    target = next((item for item in matching if item.get("name") == child_name), None)
    if target is None:
        return
    entities.remove(target)
    siblings = [item for item in entities if item.get("parent") == parent]
    insertion_index = 0
    if siblings:
        bounded_index = max(0, min(index, len(siblings)))
        if bounded_index >= len(siblings):
            insertion_index = max(i for i, item in enumerate(entities) if item.get("parent") == parent) + 1
        else:
            sibling = siblings[bounded_index]
            insertion_index = entities.index(sibling)
    entities.insert(insertion_index, target)


def _apply_override_operations(entities: list[dict[str, Any]], overrides: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = _normalize_legacy_overrides(overrides)
    operations = normalized.get("operations", [])
    by_name = {entity["name"]: entity for entity in entities}
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        op_name = str(operation.get("op", "")).strip()
        target = operation.get("target", "")
        target_name = None
        for entity_name, entity_payload in by_name.items():
            if entity_payload.get("prefab_source_path", "") == target:
                target_name = entity_name
                break
        if target_name is None and target in ("", None):
            target_name = next((entity["name"] for entity in entities if entity.get("prefab_source_path", "") == ""), None)
        entity_payload = by_name.get(target_name) if target_name is not None else None
        if op_name == "reorder_child":
            _reorder_entities(
                entities,
                operation.get("parent"),
                str(operation.get("child", "")),
                int(operation.get("index", 0)),
            )
            continue
        if entity_payload is None:
            continue
        if op_name == "set_field":
            component_name = str(operation.get("component", ""))
            field_name = str(operation.get("field", ""))
            entity_payload.setdefault("components", {}).setdefault(component_name, {})[field_name] = copy.deepcopy(operation.get("value"))
        elif op_name == "set_entity_property":
            entity_payload[str(operation.get("field", ""))] = copy.deepcopy(operation.get("value"))
        elif op_name == "add_component":
            entity_payload.setdefault("components", {})[str(operation.get("component", ""))] = copy.deepcopy(operation.get("data", {}))
        elif op_name == "replace_component":
            entity_payload.setdefault("components", {})[str(operation.get("component", ""))] = copy.deepcopy(operation.get("data", {}))
        elif op_name == "remove_component":
            entity_payload.setdefault("components", {}).pop(str(operation.get("component", "")), None)
    return entities


class PrefabManager:
    """Gestor estÃ¡tico para operaciones con Prefabs."""

    @staticmethod
    def save_prefab(entity: Entity, path: str, world: Optional[World] = None) -> bool:
        try:
            payload = migrate_prefab_data(PrefabManager._build_prefab_payload(entity, world))
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=4)
            print(f"[PREFAB] Entity '{entity.name}' saved to {path}")
            return True
        except Exception as exc:
            print(f"[PREFAB] Error saving prefab to {path}: {exc}")
            return False

    @staticmethod
    def _build_prefab_payload(entity: Entity, world: Optional[World]) -> dict[str, Any]:
        if world is None:
            entity_data = entity.to_dict()
            entity_data.pop("id", None)
            return migrate_prefab_data({"root_name": entity.name, "entities": [entity_data]})

        subtree = [entity] + world.get_descendants(entity.name)
        subtree.sort(key=lambda item: (0 if item.name == entity.name else 1, item.name))
        entities = []
        for node in subtree:
            data = node.to_dict()
            data.pop("id", None)
            data.pop("prefab_instance", None)
            data.pop("prefab_root_name", None)
            data.pop("prefab_source_path", None)
            if node.name == entity.name:
                prefab_root_name = entity.prefab_instance.get("root_name") if entity.prefab_instance else None
                data["name"] = prefab_root_name or entity.name
                data.pop("parent", None)
            else:
                relative = PrefabManager._relative_prefab_path(node, entity.name)
                data["name"] = relative.split("/")[-1]
                parent_path = PrefabManager._relative_parent_path(node, entity.name)
                if parent_path is not None:
                    data["parent"] = parent_path
                else:
                    data.pop("parent", None)
            entities.append(data)
        return migrate_prefab_data({"root_name": entities[0]["name"], "entities": entities})

    @staticmethod
    def _relative_prefab_path(entity: Entity, root_name: str) -> str:
        if entity.prefab_source_path:
            return entity.prefab_source_path
        if entity.name == root_name:
            return ""
        prefix = f"{root_name}/"
        return entity.name[len(prefix):] if entity.name.startswith(prefix) else entity.name

    @staticmethod
    def _relative_parent_path(entity: Entity, root_name: str) -> str | None:
        if entity.parent_name is None:
            return None
        if entity.parent_name == root_name:
            return ""
        prefix = f"{root_name}/"
        return entity.parent_name[len(prefix):] if entity.parent_name.startswith(prefix) else entity.parent_name

    @staticmethod
    def load_prefab_data(path: str) -> Optional[dict[str, Any]]:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            payload = migrate_prefab_data(copy.deepcopy(raw))
            if validate_prefab_data(payload):
                return None
            return payload
        except Exception as exc:
            print(f"[PREFAB] Error loading prefab {path}: {exc}")
            return None

    @staticmethod
    def expand_prefab_instance(
        prefab_data: dict[str, Any],
        *,
        instance_name: str,
        parent_name: str | None,
        prefab_path: str,
        overrides: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        overrides = copy.deepcopy(overrides or {})
        root_prefab_name = prefab_data.get("root_name", "Prefab")
        expanded: list[dict[str, Any]] = []

        for entity_data in prefab_data.get("entities", []):
            relative_parent = entity_data.get("parent")
            relative_path = PrefabManager._entity_relative_path(entity_data)
            world_name = instance_name if relative_path == "" else f"{instance_name}/{relative_path}"
            if relative_parent is None:
                world_parent = parent_name
            elif relative_parent == "":
                world_parent = instance_name
            else:
                world_parent = f"{instance_name}/{relative_parent}"

            normalized_overrides = _normalize_legacy_overrides(overrides)
            merged = _deep_merge(entity_data, {})
            merged["name"] = world_name
            if world_parent is not None:
                merged["parent"] = world_parent
            else:
                merged.pop("parent", None)
            if relative_path == "":
                merged["prefab_instance"] = {
                    "prefab_path": prefab_path,
                    "root_name": root_prefab_name,
                    "overrides": copy.deepcopy(overrides),
                }
                merged["prefab_root_name"] = instance_name
            else:
                merged["prefab_root_name"] = instance_name
            merged["prefab_source_path"] = relative_path
            expanded.append(merged)
        return _apply_override_operations(expanded, normalized_overrides)

    @staticmethod
    def _entity_relative_path(entity_data: dict[str, Any]) -> str:
        parent = entity_data.get("parent")
        name = entity_data.get("name", "Entity")
        if parent is None:
            return ""
        if parent == "":
            return name
        return f"{parent}/{name}"

    @staticmethod
    def instantiate_prefab(path: str, world: World, position: Optional[tuple[float, float]] = None) -> Optional[Entity]:
        data = PrefabManager.load_prefab_data(path)
        if not data:
            return None

        base_name = data.get("root_name", "Prefab")
        unique_name = base_name
        count = 1
        while world.get_entity_by_name(unique_name):
            unique_name = f"{base_name}_{count}"
            count += 1

        overrides = {}
        if position is not None:
            overrides[""] = {"components": {"Transform": {"x": position[0], "y": position[1]}}}
        expanded = PrefabManager.expand_prefab_instance(
            data,
            instance_name=unique_name,
            parent_name=None,
            prefab_path=Path(path).as_posix(),
            overrides=overrides,
        )
        registry = None
        from engine.levels.component_registry import create_default_registry
        from engine.components.transform import Transform

        registry = create_default_registry()
        created: dict[str, Entity] = {}
        for payload in expanded:
            entity = world.create_entity(payload["name"])
            entity.active = payload.get("active", True)
            entity.tag = payload.get("tag", "Untagged")
            entity.layer = payload.get("layer", "Default")
            entity.parent_name = payload.get("parent")
            entity.prefab_instance = payload.get("prefab_instance")
            entity.prefab_source_path = payload.get("prefab_source_path")
            entity.prefab_root_name = payload.get("prefab_root_name")
            for comp_name, comp_data in payload.get("components", {}).items():
                component = registry.create(comp_name, comp_data)
                if component is not None:
                    entity.add_component(component)
            created[entity.name] = entity

        for entity in created.values():
            if entity.parent_name is None:
                continue
            parent = created.get(entity.parent_name)
            if parent is None:
                continue
            child_transform = entity.get_component(Transform)
            parent_transform = parent.get_component(Transform)
            if child_transform is not None:
                child_transform.parent = parent_transform
                if parent_transform is not None and child_transform not in parent_transform.children:
                    parent_transform.children.append(child_transform)
        return created.get(unique_name)
