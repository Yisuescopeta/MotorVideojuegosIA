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


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = copy.deepcopy(base)
        for key, value in override.items():
            merged[key] = _deep_merge(merged.get(key), value) if key in merged else copy.deepcopy(value)
        return merged
    return copy.deepcopy(override)


class PrefabManager:
    """Gestor estÃ¡tico para operaciones con Prefabs."""

    @staticmethod
    def save_prefab(entity: Entity, path: str, world: Optional[World] = None) -> bool:
        try:
            payload = PrefabManager._build_prefab_payload(entity, world)
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
            return {"root_name": entity.name, "entities": [entity_data]}

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
        return {"root_name": entities[0]["name"], "entities": entities}

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
        except Exception as exc:
            print(f"[PREFAB] Error loading prefab {path}: {exc}")
            return None

        if isinstance(raw, dict) and "entities" in raw:
            payload = copy.deepcopy(raw)
            payload.setdefault("root_name", payload.get("entities", [{}])[0].get("name", "Prefab"))
            return payload

        if isinstance(raw, dict):
            legacy = copy.deepcopy(raw)
            legacy.pop("id", None)
            legacy.pop("prefab_instance", None)
            legacy.pop("prefab_source_path", None)
            legacy.pop("prefab_root_name", None)
            return {"root_name": legacy.get("name", "Prefab"), "entities": [legacy]}
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

            merged = _deep_merge(entity_data, overrides.get(relative_path, {}))
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
        return expanded

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
