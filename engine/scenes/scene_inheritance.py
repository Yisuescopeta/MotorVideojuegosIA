"""
engine/scenes/scene_inheritance.py — Scene inheritance (Godot "inherited scene" pattern).
A child scene inherits entities from a base scene and can override or add entities.
"""
from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.serialization.schema import CURRENT_SCENE_SCHEMA_VERSION


@dataclass
class SceneInheritanceData:
    """Per-entity inheritance metadata (runtime-only, not serialized)."""
    inherited: bool = False
    base_scene_path: str = ""
    base_entity_name: str = ""
    overrides: Dict[str, Any] = field(default_factory=dict)


def _load_scene_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve_base_path(child_scene_path: str, inherits_from: str) -> str:
    """Resolve inherits_from relative to the child scene's directory."""
    if os.path.isabs(inherits_from):
        return os.path.normpath(inherits_from)
    child_dir = os.path.dirname(os.path.abspath(child_scene_path)) if child_scene_path else os.getcwd()
    return os.path.normpath(os.path.join(child_dir, inherits_from))


def _detect_circular(chain: List[str], next_path: str) -> bool:
    return next_path in chain


def resolve_inherited_scene(
    child_scene_path: str,
    child_data: dict[str, Any],
    *,
    visited_paths: Optional[List[str]] = None,
) -> dict[str, Any]:
    """Resolve scene inheritance chain, merging base entities with child overrides.

    Args:
        child_scene_path: Absolute path to the child scene file (for resolving relative paths).
        child_data: The child scene payload (already loaded from JSON).
        visited_paths: Internal recursion guard for circular inheritance detection.

    Returns:
        Fully resolved scene dict with all base entities merged and child overrides applied.
    """
    inherits_from: str = str(child_data.get("inherits_from", "") or "").strip()
    if not inherits_from:
        return copy.deepcopy(child_data)

    base_path = _resolve_base_path(child_scene_path, inherits_from)

    visited = list(visited_paths or [])
    if _detect_circular(visited, base_path):
        raise ValueError(f"Circular scene inheritance detected: {' -> '.join(visited + [base_path])}")

    visited.append(base_path)
    base_data = _load_scene_json(base_path)

    # Recursively resolve the base (supports multi-level inheritance)
    resolved_base = resolve_inherited_scene(base_path, base_data, visited_paths=visited)

    # Merge: start with resolved base
    merged: dict[str, Any] = copy.deepcopy(resolved_base)

    # Build index of base entities by name
    base_entities: dict[str, dict[str, Any]] = {}
    for entity in merged.get("entities", []):
        if isinstance(entity, dict):
            name = str(entity.get("name", "") or "")
            if name:
                base_entities[name] = entity

    # Merge child entities: override existing, add new
    child_entities: list[dict[str, Any]] = []
    for entity in child_data.get("entities", []):
        if not isinstance(entity, dict):
            child_entities.append(copy.deepcopy(entity))
            continue
        entity_name = str(entity.get("name", "") or "")
        if entity_name and entity_name in base_entities:
            # Override: merge child components over base
            base_entity = base_entities[entity_name]
            child_components = entity.get("components", {})
            if isinstance(child_components, dict):
                base_components = base_entity.setdefault("components", {})
                for comp_name, comp_data in child_components.items():
                    if comp_name in base_components and isinstance(base_components[comp_name], dict) and isinstance(comp_data, dict):
                        base_components[comp_name].update(copy.deepcopy(comp_data))
                    else:
                        base_components[comp_name] = copy.deepcopy(comp_data)
            # Override entity-level properties
            for key in ("active", "tag", "layer", "parent", "groups"):
                if key in entity:
                    base_entity[key] = copy.deepcopy(entity[key])
        else:
            # New entity: add to merged result
            child_entities.append(copy.deepcopy(entity))

    merged["entities"].extend(child_entities)

    # Child's name takes precedence
    child_name = child_data.get("name", "")
    if child_name:
        merged["name"] = child_name

    # Child's feature_metadata merges over base
    child_metadata = child_data.get("feature_metadata", {})
    if isinstance(child_metadata, dict) and child_metadata:
        base_metadata = merged.setdefault("feature_metadata", {})
        base_metadata.update(copy.deepcopy(child_metadata))

    # Child's rules merge over base
    child_rules = child_data.get("rules", [])
    if isinstance(child_rules, list) and child_rules:
        merged["rules"] = copy.deepcopy(child_rules)

    # Strip inherits_from from resolved output (runtime-only field)
    merged.pop("inherits_from", None)

    # Ensure schema_version stays current
    merged["schema_version"] = CURRENT_SCENE_SCHEMA_VERSION

    return merged


def create_child_scene_payload(
    child_name: str,
    base_scene_path: str,
) -> dict[str, Any]:
    """Create a minimal child scene payload that inherits from base_scene_path.

    Args:
        child_name: Name for the child scene.
        base_scene_path: Path to the base scene (relative or absolute).

    Returns:
        Minimal scene dict with inherits_from pointing to the base.
    """
    return {
        "name": child_name,
        "inherits_from": base_scene_path,
        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
        "entities": [],
        "rules": [],
        "feature_metadata": {},
    }
