from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

CURRENT_SCENE_SCHEMA_VERSION = 1
CURRENT_PREFAB_SCHEMA_VERSION = 1
SUPPORTED_RULE_ACTIONS = {
    "set_animation",
    "set_position",
    "destroy_entity",
    "emit_event",
    "log_message",
}


def migrate_scene_data(data: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(data)
    migrated.setdefault("schema_version", CURRENT_SCENE_SCHEMA_VERSION)
    migrated.setdefault("name", "Untitled")
    migrated.setdefault("entities", [])
    migrated.setdefault("rules", [])
    migrated.setdefault("feature_metadata", {})
    for entity in migrated["entities"]:
        if not isinstance(entity, dict):
            continue
        entity.setdefault("active", True)
        entity.setdefault("tag", "Untagged")
        entity.setdefault("layer", "Default")
        entity.setdefault("components", {})
        tilemap = entity.get("components", {}).get("Tilemap")
        if isinstance(tilemap, dict):
            tilemap.setdefault("cell_width", 16)
            tilemap.setdefault("cell_height", 16)
            tilemap.setdefault("orientation", "orthogonal")
            tilemap.setdefault("tileset", {})
            tilemap.setdefault("tileset_path", "")
            tilemap.setdefault("layers", [])
    return migrated


def migrate_prefab_data(data: dict[str, Any]) -> dict[str, Any]:
    if "entities" not in data:
        legacy = copy.deepcopy(data)
        legacy.pop("id", None)
        legacy.pop("prefab_instance", None)
        legacy.pop("prefab_source_path", None)
        legacy.pop("prefab_root_name", None)
        data = {"root_name": legacy.get("name", "Prefab"), "entities": [legacy]}
    migrated = copy.deepcopy(data)
    migrated.setdefault("schema_version", CURRENT_PREFAB_SCHEMA_VERSION)
    migrated.setdefault("root_name", migrated.get("entities", [{}])[0].get("name", "Prefab"))
    migrated.setdefault("entities", [])
    for entity in migrated["entities"]:
        if not isinstance(entity, dict):
            continue
        entity.setdefault("active", True)
        entity.setdefault("tag", "Untagged")
        entity.setdefault("layer", "Default")
        entity.setdefault("components", {})
    return migrated


def _validate_entity(entity: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(entity, dict):
        return [f"{path}: expected object"]
    if not str(entity.get("name", "")).strip():
        errors.append(f"{path}.name: expected non-empty string")
    components = entity.get("components", {})
    if not isinstance(components, dict):
        errors.append(f"{path}.components: expected object")
    elif "Tilemap" in components:
        errors.extend(_validate_tilemap(components.get("Tilemap"), path=f"{path}.components.Tilemap"))
    return errors


def _validate_tilemap(tilemap: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(tilemap, dict):
        return [f"{path}: expected object"]
    if int(tilemap.get("cell_width", 0)) <= 0:
        errors.append(f"{path}.cell_width: expected positive integer")
    if int(tilemap.get("cell_height", 0)) <= 0:
        errors.append(f"{path}.cell_height: expected positive integer")
    if str(tilemap.get("orientation", "")).strip() not in {"orthogonal"}:
        errors.append(f"{path}.orientation: expected orthogonal")
    layers = tilemap.get("layers", [])
    if not isinstance(layers, list):
        errors.append(f"{path}.layers: expected array")
        return errors
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            errors.append(f"{path}.layers[{index}]: expected object")
            continue
        if not str(layer.get("name", "")).strip():
            errors.append(f"{path}.layers[{index}].name: expected non-empty string")
        if not isinstance(layer.get("tiles", []), list):
            errors.append(f"{path}.layers[{index}].tiles: expected array")
    return errors


def _is_json_serializable(value: Any) -> bool:
    try:
        json.dumps(value, ensure_ascii=True)
        return True
    except (TypeError, ValueError):
        return False


def _validate_rule_action(action: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(action, dict):
        return [f"{path}: expected object"]
    action_name = str(action.get("action", "")).strip()
    if not action_name:
        errors.append(f"{path}.action: expected non-empty string")
        return errors
    if action_name not in SUPPORTED_RULE_ACTIONS:
        errors.append(f"{path}.action: unsupported action '{action_name}'")
        return errors
    if action_name == "set_animation":
        if not str(action.get("entity", "")).strip():
            errors.append(f"{path}.entity: expected non-empty string")
        if not str(action.get("state", "")).strip():
            errors.append(f"{path}.state: expected non-empty string")
    elif action_name == "set_position":
        if not str(action.get("entity", "")).strip():
            errors.append(f"{path}.entity: expected non-empty string")
        if action.get("x") is None and action.get("y") is None:
            errors.append(f"{path}: expected x or y")
    elif action_name == "destroy_entity":
        if not str(action.get("entity", "")).strip():
            errors.append(f"{path}.entity: expected non-empty string")
    elif action_name == "emit_event":
        if not str(action.get("event", "")).strip():
            errors.append(f"{path}.event: expected non-empty string")
        if "data" in action and not _is_json_serializable(action.get("data")):
            errors.append(f"{path}.data: expected JSON-serializable value")
    elif action_name == "log_message":
        if not str(action.get("message", "")).strip():
            errors.append(f"{path}.message: expected non-empty string")
    return errors


def _validate_rule(rule: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(rule, dict):
        return [f"{path}: expected object"]
    if not str(rule.get("event", "")).strip():
        errors.append(f"{path}.event: expected non-empty string")
    when = rule.get("when", {})
    if when is not None and not isinstance(when, dict):
        errors.append(f"{path}.when: expected object")
    actions = rule.get("do")
    if not isinstance(actions, list):
        errors.append(f"{path}.do: expected non-empty array")
        return errors
    if not actions:
        errors.append(f"{path}.do: expected non-empty array")
        return errors
    for index, action in enumerate(actions):
        errors.extend(_validate_rule_action(action, path=f"{path}.do[{index}]"))
    return errors


def validate_scene_data(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["$: expected object"]
    if data.get("schema_version") != CURRENT_SCENE_SCHEMA_VERSION:
        errors.append(
            f"$.schema_version: expected {CURRENT_SCENE_SCHEMA_VERSION}, got {data.get('schema_version')}"
        )
    if not str(data.get("name", "")).strip():
        errors.append("$.name: expected non-empty string")
    entities = data.get("entities")
    if not isinstance(entities, list):
        errors.append("$.entities: expected array")
    else:
        for index, entity in enumerate(entities):
            errors.extend(_validate_entity(entity, path=f"$.entities[{index}]"))
    rules = data.get("rules")
    if not isinstance(rules, list):
        errors.append("$.rules: expected array")
    else:
        for index, rule in enumerate(rules):
            errors.extend(_validate_rule(rule, path=f"$.rules[{index}]"))
    feature_metadata = data.get("feature_metadata")
    if not isinstance(feature_metadata, dict):
        errors.append("$.feature_metadata: expected object")
    return errors


def validate_prefab_data(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["$: expected object"]
    if data.get("schema_version") != CURRENT_PREFAB_SCHEMA_VERSION:
        errors.append(
            f"$.schema_version: expected {CURRENT_PREFAB_SCHEMA_VERSION}, got {data.get('schema_version')}"
        )
    if not str(data.get("root_name", "")).strip():
        errors.append("$.root_name: expected non-empty string")
    entities = data.get("entities")
    if not isinstance(entities, list) or not entities:
        errors.append("$.entities: expected non-empty array")
    elif isinstance(entities, list):
        for index, entity in enumerate(entities):
            errors.extend(_validate_entity(entity, path=f"$.entities[{index}]"))
    return errors


def detect_payload_kind(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".prefab":
        return "prefab"
    return "scene"
