from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

from engine.assets.asset_reference import build_asset_reference, normalize_asset_path, normalize_asset_reference

CURRENT_SCENE_SCHEMA_VERSION = 2
CURRENT_PREFAB_SCHEMA_VERSION = 2
SUPPORTED_RULE_ACTIONS = {
    "set_animation",
    "set_position",
    "destroy_entity",
    "emit_event",
    "log_message",
}
COLLIDER_SHAPE_TYPES = {"box", "circle", "polygon"}
RIGIDBODY_BODY_TYPES = {"dynamic", "kinematic", "static"}
RIGIDBODY_COLLISION_MODES = {"discrete", "continuous"}
RIGIDBODY_CONSTRAINTS = {"None", "FreezePositionX", "FreezePositionY", "FreezePosition"}
UI_TEXT_ALIGNMENTS = {"left", "center", "right"}
UI_BUTTON_ACTIONS = {"emit_event", "load_scene", "load_scene_flow"}
PHYSICS_BACKENDS = {"legacy_aabb", "box2d"}
ASSET_REFERENCE_FIELD_PAIRS = {
    "Sprite": ("texture", "texture_path"),
    "Animator": ("sprite_sheet", "sprite_sheet_path"),
    "Tilemap": ("tileset", "tileset_path"),
    "AudioSource": ("asset", "asset_path"),
}


def _coerce_schema_version(raw: Any, *, kind: str) -> int:
    if raw is None:
        return 0
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"Invalid {kind} schema version: {raw!r}")
    if raw < 0:
        raise ValueError(f"Unsupported {kind} schema version: {raw}")
    return raw


def _scene_schema_version_of(raw: dict[str, Any]) -> int:
    return _coerce_schema_version(raw.get("schema_version"), kind="scene")


def _prefab_schema_version_of(raw: dict[str, Any]) -> int:
    return _coerce_schema_version(raw.get("schema_version"), kind="prefab")


def _default_scene_fields(data: dict[str, Any]) -> None:
    data.setdefault("name", "Untitled")
    data.setdefault("entities", [])
    data.setdefault("rules", [])
    data.setdefault("feature_metadata", {})


def _default_prefab_fields(data: dict[str, Any]) -> None:
    data.setdefault("entities", [])
    root_name = data.get("root_name")
    if not isinstance(root_name, str) or not root_name.strip():
        entities = data.get("entities", [])
        if isinstance(entities, list) and entities and isinstance(entities[0], dict):
            root_name = entities[0].get("name", "Prefab")
        else:
            root_name = "Prefab"
        data["root_name"] = root_name


def _migrate_entity_defaults(entity: dict[str, Any]) -> None:
    entity.setdefault("active", True)
    entity.setdefault("tag", "Untagged")
    entity.setdefault("layer", "Default")
    entity.setdefault("components", {})


def _normalize_prefab_override_map(overrides: dict[str, Any]) -> dict[str, Any]:
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


def _normalize_module_name(module_path: str) -> str:
    value = normalize_asset_path(module_path)
    if value.endswith(".py"):
        if value.startswith("scripts/"):
            value = value[len("scripts/") :]
        value = value[:-3]
    return value.strip("/").replace("/", ".")


def _canonicalize_asset_reference_pair(
    payload: dict[str, Any],
    *,
    ref_key: str,
    path_key: str,
    component_name: str,
    entity_path: str,
) -> None:
    ref_value = payload.get(ref_key)
    path_value = payload.get(path_key)

    normalized_ref = normalize_asset_reference(ref_value)
    normalized_ref_path = normalized_ref.get("path", "")
    normalized_path = normalize_asset_path(path_value) if isinstance(path_value, str) else ""

    if ref_value is not None and not isinstance(ref_value, (dict, str)):
        raise ValueError(f"Cannot migrate {entity_path}.components.{component_name}: invalid {ref_key}")
    if path_key in payload and path_value is not None and not isinstance(path_value, str):
        raise ValueError(f"Cannot migrate {entity_path}.components.{component_name}: invalid {path_key}")
    if normalized_ref_path and normalized_path and normalized_ref_path != normalized_path:
        raise ValueError(
            f"Cannot migrate {entity_path}.components.{component_name}: inconsistent {ref_key} and {path_key}"
        )

    canonical_path = normalized_path or normalized_ref_path
    if ref_key in payload or canonical_path:
        payload[ref_key] = build_asset_reference(canonical_path, normalized_ref.get("guid", ""))
    if path_key in payload or canonical_path:
        payload[path_key] = canonical_path


def _canonicalize_script_behaviour(payload: dict[str, Any], *, entity_path: str) -> None:
    script_value = payload.get("script")
    module_path_value = payload.get("module_path")
    if script_value is not None and not isinstance(script_value, (dict, str)):
        raise ValueError(f"Cannot migrate {entity_path}.components.ScriptBehaviour: invalid script")
    if module_path_value is not None and not isinstance(module_path_value, str):
        raise ValueError(f"Cannot migrate {entity_path}.components.ScriptBehaviour: invalid module_path")

    script_ref = normalize_asset_reference(script_value)
    script_path = script_ref.get("path", "")
    module_path = normalize_asset_path(module_path_value) if isinstance(module_path_value, str) else ""
    normalized_module = _normalize_module_name(script_path) if script_path else ""
    if script_path and module_path and module_path not in {script_path, normalized_module}:
        raise ValueError(
            f"Cannot migrate {entity_path}.components.ScriptBehaviour: inconsistent script and module_path"
        )

    if script_value is not None or script_path:
        payload["script"] = build_asset_reference(script_path, script_ref.get("guid", ""))
    if "module_path" in payload or script_path:
        payload["module_path"] = normalized_module or module_path


def _canonicalize_collider(payload: dict[str, Any]) -> None:
    width = payload.get("width", 32.0)
    radius = width / 2 if _is_number(width) else 16.0
    payload.setdefault("shape_type", "box")
    payload.setdefault("radius", radius)
    payload.setdefault("points", [])
    payload.setdefault("friction", 0.2)
    payload.setdefault("restitution", 0.0)
    payload.setdefault("density", 1.0)


def _canonicalize_rigidbody(payload: dict[str, Any]) -> None:
    payload.setdefault("body_type", "dynamic")
    payload.setdefault("simulated", True)
    constraints = payload.get("constraints")
    freeze_x = bool(payload.get("freeze_x", False))
    freeze_y = bool(payload.get("freeze_y", False))
    if constraints is not None and "freeze_x" not in payload and "freeze_y" not in payload:
        values = constraints if isinstance(constraints, list) else [constraints]
        normalized = {str(value).strip() for value in values if str(value).strip()}
        if "FreezePosition" in normalized:
            freeze_x = True
            freeze_y = True
        else:
            freeze_x = "FreezePositionX" in normalized
            freeze_y = "FreezePositionY" in normalized
    payload.setdefault("freeze_x", freeze_x)
    payload.setdefault("freeze_y", freeze_y)
    payload["constraints"] = (
        ["FreezePositionX", "FreezePositionY"]
        if payload["freeze_x"] and payload["freeze_y"]
        else ["FreezePositionX"]
        if payload["freeze_x"]
        else ["FreezePositionY"]
        if payload["freeze_y"]
        else ["None"]
    )
    payload.setdefault("use_full_kinematic_contacts", False)
    payload.setdefault("collision_detection_mode", "discrete")


def _canonicalize_tilemap(payload: dict[str, Any]) -> None:
    payload.setdefault("cell_width", 16)
    payload.setdefault("cell_height", 16)
    payload.setdefault("orientation", "orthogonal")
    payload.setdefault("tileset", {})
    payload.setdefault("tileset_path", "")
    payload.setdefault("layers", [])


def _canonicalize_component_payload(component_name: str, payload: dict[str, Any], *, entity_path: str) -> None:
    if component_name in ASSET_REFERENCE_FIELD_PAIRS:
        ref_key, path_key = ASSET_REFERENCE_FIELD_PAIRS[component_name]
        _canonicalize_asset_reference_pair(
            payload,
            ref_key=ref_key,
            path_key=path_key,
            component_name=component_name,
            entity_path=entity_path,
        )
    if component_name == "ScriptBehaviour":
        _canonicalize_script_behaviour(payload, entity_path=entity_path)
    elif component_name == "Collider":
        _canonicalize_collider(payload)
    elif component_name == "RigidBody":
        _canonicalize_rigidbody(payload)
    elif component_name == "Tilemap":
        _canonicalize_tilemap(payload)
    elif component_name == "Animator":
        payload.setdefault("sprite_sheet_path", normalize_asset_reference(payload.get("sprite_sheet")).get("path", ""))


def _canonicalize_entity_payload(entity: dict[str, Any], *, entity_path: str) -> None:
    _migrate_entity_defaults(entity)
    components = entity.get("components", {})
    if not isinstance(components, dict):
        return
    for component_name, component_payload in components.items():
        if not isinstance(component_name, str) or not isinstance(component_payload, dict):
            continue
        _canonicalize_component_payload(component_name, component_payload, entity_path=entity_path)
    prefab_instance = entity.get("prefab_instance")
    if isinstance(prefab_instance, dict):
        overrides = prefab_instance.get("overrides")
        if isinstance(overrides, dict):
            prefab_instance["overrides"] = _normalize_prefab_override_map(overrides)


def _migrate_scene_v0_to_v1(data: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(data)
    migrated["schema_version"] = 1
    _default_scene_fields(migrated)
    entities = migrated.get("entities", [])
    if isinstance(entities, list):
        for entity in entities:
            if isinstance(entity, dict):
                _migrate_entity_defaults(entity)
                tilemap = entity.get("components", {}).get("Tilemap")
                if isinstance(tilemap, dict):
                    _canonicalize_tilemap(tilemap)
    return migrated


def _migrate_scene_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(data)
    migrated["schema_version"] = 2
    _default_scene_fields(migrated)
    entities = migrated.get("entities", [])
    if isinstance(entities, list):
        for index, entity in enumerate(entities):
            if isinstance(entity, dict):
                _canonicalize_entity_payload(entity, entity_path=f"$.entities[{index}]")
    return migrated


def _canonicalize_scene_v2(data: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(data)
    migrated["schema_version"] = CURRENT_SCENE_SCHEMA_VERSION
    _default_scene_fields(migrated)
    entities = migrated.get("entities", [])
    if isinstance(entities, list):
        for index, entity in enumerate(entities):
            if isinstance(entity, dict):
                _canonicalize_entity_payload(entity, entity_path=f"$.entities[{index}]")
    return migrated


def _migrate_prefab_v0_to_v1(data: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(data)
    if "entities" not in migrated:
        legacy = copy.deepcopy(migrated)
        legacy.pop("id", None)
        legacy.pop("prefab_instance", None)
        legacy.pop("prefab_source_path", None)
        legacy.pop("prefab_root_name", None)
        migrated = {"root_name": legacy.get("name", "Prefab"), "entities": [legacy]}
    migrated["schema_version"] = 1
    _default_prefab_fields(migrated)
    entities = migrated.get("entities", [])
    if isinstance(entities, list):
        for entity in entities:
            if isinstance(entity, dict):
                _migrate_entity_defaults(entity)
    return migrated


def _migrate_prefab_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(data)
    migrated["schema_version"] = 2
    _default_prefab_fields(migrated)
    entities = migrated.get("entities", [])
    if isinstance(entities, list):
        for index, entity in enumerate(entities):
            if isinstance(entity, dict):
                _canonicalize_entity_payload(entity, entity_path=f"$.entities[{index}]")
    return migrated


def _canonicalize_prefab_v2(data: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(data)
    migrated["schema_version"] = CURRENT_PREFAB_SCHEMA_VERSION
    _default_prefab_fields(migrated)
    entities = migrated.get("entities", [])
    if isinstance(entities, list):
        for index, entity in enumerate(entities):
            if isinstance(entity, dict):
                _canonicalize_entity_payload(entity, entity_path=f"$.entities[{index}]")
    return migrated


def migrate_scene_data(data: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(data)
    version = _scene_schema_version_of(migrated)
    if version == 0:
        migrated = _migrate_scene_v0_to_v1(migrated)
        version = 1
    if version == 1:
        migrated = _migrate_scene_v1_to_v2(migrated)
        version = 2
    if version != CURRENT_SCENE_SCHEMA_VERSION:
        raise ValueError(f"Unsupported scene schema version: {version}")
    return _canonicalize_scene_v2(migrated)


def migrate_prefab_data(data: dict[str, Any]) -> dict[str, Any]:
    migrated = copy.deepcopy(data)
    version = _prefab_schema_version_of(migrated)
    if version == 0:
        migrated = _migrate_prefab_v0_to_v1(migrated)
        version = 1
    if version == 1:
        migrated = _migrate_prefab_v1_to_v2(migrated)
        version = 2
    if version != CURRENT_PREFAB_SCHEMA_VERSION:
        raise ValueError(f"Unsupported prefab schema version: {version}")
    return _canonicalize_prefab_v2(migrated)


def build_canonical_scene_payload(
    scene_name: str,
    world_snapshot: dict[str, Any],
    rules_data: list[Any],
    feature_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
        "name": str(scene_name or "Untitled"),
        "entities": copy.deepcopy(world_snapshot.get("entities", [])),
        "rules": copy.deepcopy(rules_data),
        "feature_metadata": copy.deepcopy(
            feature_metadata
            if feature_metadata is not None
            else world_snapshot.get("feature_metadata", {})
        ),
    }
    return migrate_scene_data(payload)


def _is_json_serializable(value: Any) -> bool:
    try:
        json.dumps(value, ensure_ascii=True)
        return True
    except (TypeError, ValueError):
        return False


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _expect_object(value: Any, *, path: str, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected object")
        return None
    return value


def _expect_string(value: Any, *, path: str, errors: list[str], non_empty: bool = False) -> str | None:
    if not isinstance(value, str):
        errors.append(f"{path}: expected string")
        return None
    if non_empty and not value.strip():
        errors.append(f"{path}: expected non-empty string")
    return value


def _expect_bool(value: Any, *, path: str, errors: list[str]) -> None:
    if not isinstance(value, bool):
        errors.append(f"{path}: expected boolean")


def _expect_number(
    value: Any,
    *,
    path: str,
    errors: list[str],
    minimum: float | None = None,
    maximum: float | None = None,
    exclusive_minimum: float | None = None,
) -> None:
    if not _is_number(value):
        errors.append(f"{path}: expected number")
        return
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        errors.append(f"{path}: expected >= {minimum}")
    if maximum is not None and numeric > maximum:
        errors.append(f"{path}: expected <= {maximum}")
    if exclusive_minimum is not None and numeric <= exclusive_minimum:
        errors.append(f"{path}: expected > {exclusive_minimum}")


def _expect_int(
    value: Any,
    *,
    path: str,
    errors: list[str],
    minimum: int | None = None,
) -> None:
    if not _is_int(value):
        errors.append(f"{path}: expected integer")
        return
    if minimum is not None and int(value) < minimum:
        errors.append(f"{path}: expected >= {minimum}")


def _expect_string_list(
    value: Any,
    *,
    path: str,
    errors: list[str],
    non_empty_items: bool = True,
) -> None:
    if not isinstance(value, list):
        errors.append(f"{path}: expected array")
        return
    for index, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"{path}[{index}]: expected string")
            continue
        if non_empty_items and not item.strip():
            errors.append(f"{path}[{index}]: expected non-empty string")


def _expect_json_serializable(value: Any, *, path: str, errors: list[str]) -> None:
    if not _is_json_serializable(value):
        errors.append(f"{path}: expected JSON-serializable value")


def _validate_rgba(value: Any, *, path: str, errors: list[str]) -> None:
    if not isinstance(value, list) or len(value) != 4:
        errors.append(f"{path}: expected RGBA array of length 4")
        return
    for index, item in enumerate(value):
        if not _is_int(item):
            errors.append(f"{path}[{index}]: expected integer")
            continue
        if int(item) < 0 or int(item) > 255:
            errors.append(f"{path}[{index}]: expected value between 0 and 255")


def _validate_asset_reference_consistency(
    data: dict[str, Any],
    *,
    ref_key: str,
    path_key: str,
    path: str,
    errors: list[str],
) -> None:
    normalized_ref_path = ""
    if ref_key in data:
        ref_value = data.get(ref_key)
        if ref_value is not None and not isinstance(ref_value, (dict, str)):
            errors.append(f"{path}.{ref_key}: expected asset reference")
        else:
            ref = normalize_asset_reference(ref_value)
            normalized_ref_path = ref.get("path", "")
            if isinstance(ref_value, dict):
                for field_name in ("guid", "path"):
                    if field_name in ref_value and not isinstance(ref_value.get(field_name), str):
                        errors.append(f"{path}.{ref_key}.{field_name}: expected string")
    if path_key in data:
        path_value = data.get(path_key)
        if not isinstance(path_value, str):
            errors.append(f"{path}.{path_key}: expected string")
        else:
            normalized_path = normalize_asset_path(path_value)
            if normalized_ref_path and normalized_path and normalized_ref_path != normalized_path:
                errors.append(f"{path}.{path_key}: inconsistent with {path}.{ref_key}.path")


def _validate_transform(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    for key in ("x", "y", "rotation", "scale_x", "scale_y"):
        if key in data:
            _expect_number(data[key], path=f"{path}.{key}", errors=errors)
    return errors


def _validate_rect_transform(data: dict[str, Any], *, path: str) -> list[str]:
    errors = _validate_transform(data, path=path)
    for key in ("anchor_min_x", "anchor_min_y", "anchor_max_x", "anchor_max_y", "pivot_x", "pivot_y"):
        if key in data:
            _expect_number(data[key], path=f"{path}.{key}", errors=errors, minimum=0.0, maximum=1.0)
    for key in ("anchored_x", "anchored_y"):
        if key in data:
            _expect_number(data[key], path=f"{path}.{key}", errors=errors)
    for key in ("width", "height"):
        if key in data:
            _expect_number(data[key], path=f"{path}.{key}", errors=errors, minimum=0.0)
    return errors


def _validate_sprite(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    _validate_asset_reference_consistency(data, ref_key="texture", path_key="texture_path", path=path, errors=errors)
    for key in ("width", "height"):
        if key in data:
            _expect_number(data[key], path=f"{path}.{key}", errors=errors, minimum=0.0)
    for key in ("origin_x", "origin_y"):
        if key in data:
            _expect_number(data[key], path=f"{path}.{key}", errors=errors)
    for key in ("flip_x", "flip_y"):
        if key in data:
            _expect_bool(data[key], path=f"{path}.{key}", errors=errors)
    if "tint" in data:
        _validate_rgba(data["tint"], path=f"{path}.tint", errors=errors)
    return errors


def _validate_collider(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    for key in ("width", "height", "radius", "offset_x", "offset_y", "friction", "restitution", "density"):
        if key in data:
            minimum = 0.0 if key in {"width", "height", "radius", "friction", "restitution", "density"} else None
            _expect_number(data[key], path=f"{path}.{key}", errors=errors, minimum=minimum)
    if "is_trigger" in data:
        _expect_bool(data["is_trigger"], path=f"{path}.is_trigger", errors=errors)
    if "shape_type" in data:
        shape_type = _expect_string(data["shape_type"], path=f"{path}.shape_type", errors=errors, non_empty=True)
        if isinstance(shape_type, str) and shape_type.strip() not in COLLIDER_SHAPE_TYPES:
            errors.append(f"{path}.shape_type: expected one of {sorted(COLLIDER_SHAPE_TYPES)}")
    if "points" in data:
        points = data["points"]
        if not isinstance(points, list):
            errors.append(f"{path}.points: expected array")
        else:
            for index, point in enumerate(points):
                if not isinstance(point, list) or len(point) != 2:
                    errors.append(f"{path}.points[{index}]: expected [x, y]")
                    continue
                for axis, value in enumerate(point):
                    _expect_number(value, path=f"{path}.points[{index}][{axis}]", errors=errors)
    return errors


def _validate_rigidbody(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    for key in ("velocity_x", "velocity_y", "gravity_scale"):
        if key in data:
            _expect_number(data[key], path=f"{path}.{key}", errors=errors)
    for key in ("is_grounded", "simulated", "freeze_x", "freeze_y", "use_full_kinematic_contacts"):
        if key in data:
            _expect_bool(data[key], path=f"{path}.{key}", errors=errors)
    if "body_type" in data:
        body_type = _expect_string(data["body_type"], path=f"{path}.body_type", errors=errors, non_empty=True)
        if isinstance(body_type, str) and body_type.strip() not in RIGIDBODY_BODY_TYPES:
            errors.append(f"{path}.body_type: expected one of {sorted(RIGIDBODY_BODY_TYPES)}")
    if "collision_detection_mode" in data:
        mode = _expect_string(
            data["collision_detection_mode"],
            path=f"{path}.collision_detection_mode",
            errors=errors,
            non_empty=True,
        )
        if isinstance(mode, str) and mode.strip() not in RIGIDBODY_COLLISION_MODES:
            errors.append(
                f"{path}.collision_detection_mode: expected one of {sorted(RIGIDBODY_COLLISION_MODES)}"
            )
    if "constraints" in data:
        constraints = data["constraints"]
        if not isinstance(constraints, list):
            errors.append(f"{path}.constraints: expected array")
        else:
            for index, item in enumerate(constraints):
                if not isinstance(item, str):
                    errors.append(f"{path}.constraints[{index}]: expected string")
                    continue
                if item not in RIGIDBODY_CONSTRAINTS:
                    errors.append(f"{path}.constraints[{index}]: expected one of {sorted(RIGIDBODY_CONSTRAINTS)}")
    return errors


def _validate_animation_data(data: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    animation = _expect_object(data, path=path, errors=errors)
    if animation is None:
        return errors
    if "frames" in animation:
        frames = animation["frames"]
        if not isinstance(frames, list):
            errors.append(f"{path}.frames: expected array")
        else:
            for index, frame in enumerate(frames):
                _expect_int(frame, path=f"{path}.frames[{index}]", errors=errors, minimum=0)
    if "slice_names" in animation:
        _expect_string_list(animation["slice_names"], path=f"{path}.slice_names", errors=errors)
    if "fps" in animation:
        _expect_number(animation["fps"], path=f"{path}.fps", errors=errors, exclusive_minimum=0.0)
    if "loop" in animation:
        _expect_bool(animation["loop"], path=f"{path}.loop", errors=errors)
    if "on_complete" in animation and animation["on_complete"] is not None:
        _expect_string(animation["on_complete"], path=f"{path}.on_complete", errors=errors, non_empty=True)
    return errors


def _validate_animator(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    _validate_asset_reference_consistency(
        data, ref_key="sprite_sheet", path_key="sprite_sheet_path", path=path, errors=errors
    )
    for key in ("frame_width", "frame_height"):
        if key in data:
            _expect_int(data[key], path=f"{path}.{key}", errors=errors, minimum=1)
    for key in ("default_state", "current_state"):
        if key in data:
            _expect_string(data[key], path=f"{path}.{key}", errors=errors, non_empty=True)
    if "flip_x" in data:
        _expect_bool(data["flip_x"], path=f"{path}.flip_x", errors=errors)
    if "current_frame" in data:
        _expect_int(data["current_frame"], path=f"{path}.current_frame", errors=errors, minimum=0)
    if "is_finished" in data:
        _expect_bool(data["is_finished"], path=f"{path}.is_finished", errors=errors)
    if "animations" in data:
        animations = data["animations"]
        if not isinstance(animations, dict):
            errors.append(f"{path}.animations: expected object")
        else:
            for state_name, anim_data in animations.items():
                if not isinstance(state_name, str) or not state_name.strip():
                    errors.append(f"{path}.animations: expected non-empty string keys")
                    continue
                errors.extend(_validate_animation_data(anim_data, path=f"{path}.animations.{state_name}"))
    return errors


def _validate_tile_entry(tile: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    tile_payload = _expect_object(tile, path=path, errors=errors)
    if tile_payload is None:
        return errors
    if "x" in tile_payload:
        _expect_int(tile_payload["x"], path=f"{path}.x", errors=errors)
    if "y" in tile_payload:
        _expect_int(tile_payload["y"], path=f"{path}.y", errors=errors)
    if "tile_id" in tile_payload:
        _expect_string(tile_payload["tile_id"], path=f"{path}.tile_id", errors=errors, non_empty=True)
    if "source" in tile_payload and tile_payload["source"] is not None and not isinstance(
        tile_payload["source"], (dict, str)
    ):
        errors.append(f"{path}.source: expected asset reference")
    elif "source" in tile_payload and isinstance(tile_payload["source"], dict):
        for field_name in ("guid", "path"):
            if field_name in tile_payload["source"] and not isinstance(tile_payload["source"].get(field_name), str):
                errors.append(f"{path}.source.{field_name}: expected string")
    if "flags" in tile_payload:
        _expect_string_list(tile_payload["flags"], path=f"{path}.flags", errors=errors)
    if "tags" in tile_payload:
        _expect_string_list(tile_payload["tags"], path=f"{path}.tags", errors=errors)
    if "custom" in tile_payload:
        custom = _expect_object(tile_payload["custom"], path=f"{path}.custom", errors=errors)
        if custom is not None:
            _expect_json_serializable(custom, path=f"{path}.custom", errors=errors)
    return errors


def _validate_tile_layer(layer: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    layer_payload = _expect_object(layer, path=path, errors=errors)
    if layer_payload is None:
        return errors
    if "name" in layer_payload:
        _expect_string(layer_payload["name"], path=f"{path}.name", errors=errors, non_empty=True)
    if "visible" in layer_payload:
        _expect_bool(layer_payload["visible"], path=f"{path}.visible", errors=errors)
    if "opacity" in layer_payload:
        _expect_number(layer_payload["opacity"], path=f"{path}.opacity", errors=errors, minimum=0.0, maximum=1.0)
    if "metadata" in layer_payload:
        metadata = _expect_object(layer_payload["metadata"], path=f"{path}.metadata", errors=errors)
        if metadata is not None:
            _expect_json_serializable(metadata, path=f"{path}.metadata", errors=errors)
    if "tiles" in layer_payload:
        tiles = layer_payload["tiles"]
        if isinstance(tiles, list):
            for index, tile in enumerate(tiles):
                errors.extend(_validate_tile_entry(tile, path=f"{path}.tiles[{index}]"))
        elif isinstance(tiles, dict):
            for key, tile in tiles.items():
                if not isinstance(key, str) or "," not in key:
                    errors.append(f"{path}.tiles: expected coordinates like 'x,y'")
                    continue
                errors.extend(_validate_tile_entry(tile, path=f"{path}.tiles.{key}"))
        else:
            errors.append(f"{path}.tiles: expected array or object")
    return errors


def _validate_tilemap(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    if "cell_width" in data:
        _expect_int(data["cell_width"], path=f"{path}.cell_width", errors=errors, minimum=1)
    if "cell_height" in data:
        _expect_int(data["cell_height"], path=f"{path}.cell_height", errors=errors, minimum=1)
    if "orientation" in data:
        orientation = _expect_string(data["orientation"], path=f"{path}.orientation", errors=errors, non_empty=True)
        if isinstance(orientation, str) and orientation.strip() != "orthogonal":
            errors.append(f"{path}.orientation: expected orthogonal")
    _validate_asset_reference_consistency(data, ref_key="tileset", path_key="tileset_path", path=path, errors=errors)
    if "layers" in data:
        layers = data["layers"]
        if not isinstance(layers, list):
            errors.append(f"{path}.layers: expected array")
        else:
            for index, layer in enumerate(layers):
                errors.extend(_validate_tile_layer(layer, path=f"{path}.layers[{index}]"))
    return errors


def _validate_camera2d(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    for key in ("offset_x", "offset_y", "rotation", "dead_zone_width", "dead_zone_height"):
        if key in data:
            minimum = 0.0 if key in {"dead_zone_width", "dead_zone_height"} else None
            _expect_number(data[key], path=f"{path}.{key}", errors=errors, minimum=minimum)
    if "zoom" in data:
        _expect_number(data["zoom"], path=f"{path}.zoom", errors=errors, exclusive_minimum=0.0)
    for key in ("is_primary", "recenter_on_play"):
        if key in data:
            _expect_bool(data[key], path=f"{path}.{key}", errors=errors)
    if "follow_entity" in data:
        _expect_string(data["follow_entity"], path=f"{path}.follow_entity", errors=errors)
    if "framing_mode" in data:
        _expect_string(data["framing_mode"], path=f"{path}.framing_mode", errors=errors, non_empty=True)
    for key in ("clamp_left", "clamp_right", "clamp_top", "clamp_bottom"):
        if key in data and data[key] is not None:
            _expect_number(data[key], path=f"{path}.{key}", errors=errors)
    return errors


def _validate_input_map(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    for key in ("move_left", "move_right", "move_up", "move_down", "action_1", "action_2"):
        if key in data:
            _expect_string(data[key], path=f"{path}.{key}", errors=errors)
    return errors


def _validate_audio_source(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    _validate_asset_reference_consistency(data, ref_key="asset", path_key="asset_path", path=path, errors=errors)
    for key in ("volume", "pitch"):
        if key in data:
            _expect_number(data[key], path=f"{path}.{key}", errors=errors)
    if "spatial_blend" in data:
        _expect_number(data["spatial_blend"], path=f"{path}.spatial_blend", errors=errors, minimum=0.0, maximum=1.0)
    for key in ("loop", "play_on_awake", "is_playing"):
        if key in data:
            _expect_bool(data[key], path=f"{path}.{key}", errors=errors)
    return errors


def _normalize_module_name(module_path: str) -> str:
    value = normalize_asset_path(module_path)
    if value.endswith(".py"):
        if value.startswith("scripts/"):
            value = value[len("scripts/") :]
        value = value[:-3]
    return value.strip("/").replace("/", ".")


def _validate_script_behaviour(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    if "script" in data:
        script_value = data.get("script")
        if script_value is not None and not isinstance(script_value, (dict, str)):
            errors.append(f"{path}.script: expected asset reference")
        elif isinstance(script_value, dict):
            for field_name in ("guid", "path"):
                if field_name in script_value and not isinstance(script_value.get(field_name), str):
                    errors.append(f"{path}.script.{field_name}: expected string")
    script_value = data.get("script")
    module_path = data.get("module_path")
    if isinstance(script_value, (dict, str)) and isinstance(module_path, str) and module_path.strip():
        script_ref = normalize_asset_reference(script_value)
        script_path = script_ref.get("path", "")
        if script_path:
            normalized_module = _normalize_module_name(script_path)
            if module_path != script_path and module_path != normalized_module:
                errors.append(f"{path}.module_path: inconsistent with {path}.script.path")
    if "module_path" in data:
        _expect_string(data["module_path"], path=f"{path}.module_path", errors=errors)
    if "run_in_edit_mode" in data:
        _expect_bool(data["run_in_edit_mode"], path=f"{path}.run_in_edit_mode", errors=errors)
    if "public_data" in data:
        public_data = _expect_object(data["public_data"], path=f"{path}.public_data", errors=errors)
        if public_data is not None:
            _expect_json_serializable(public_data, path=f"{path}.public_data", errors=errors)
    return errors


def _validate_canvas(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    for key in ("render_mode", "match_mode"):
        if key in data:
            _expect_string(data[key], path=f"{path}.{key}", errors=errors, non_empty=True)
    for key in ("reference_width", "reference_height"):
        if key in data:
            _expect_int(data[key], path=f"{path}.{key}", errors=errors, minimum=1)
    if "sort_order" in data:
        _expect_int(data["sort_order"], path=f"{path}.sort_order", errors=errors)
    return errors


def _validate_ui_text(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    if "text" in data:
        _expect_string(data["text"], path=f"{path}.text", errors=errors)
    if "font_size" in data:
        _expect_int(data["font_size"], path=f"{path}.font_size", errors=errors, minimum=1)
    if "color" in data:
        _validate_rgba(data["color"], path=f"{path}.color", errors=errors)
    if "alignment" in data:
        alignment = _expect_string(data["alignment"], path=f"{path}.alignment", errors=errors, non_empty=True)
        if isinstance(alignment, str) and alignment.strip() not in UI_TEXT_ALIGNMENTS:
            errors.append(f"{path}.alignment: expected one of {sorted(UI_TEXT_ALIGNMENTS)}")
    if "wrap" in data:
        _expect_bool(data["wrap"], path=f"{path}.wrap", errors=errors)
    return errors


def _validate_button_on_click(value: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    payload = _expect_object(value, path=path, errors=errors)
    if payload is None:
        return errors
    if not payload:
        return errors
    action_type = _expect_string(payload.get("type"), path=f"{path}.type", errors=errors, non_empty=True)
    if not isinstance(action_type, str) or not action_type.strip():
        return errors
    normalized_type = action_type.strip()
    if normalized_type not in UI_BUTTON_ACTIONS:
        errors.append(f"{path}.type: expected one of {sorted(UI_BUTTON_ACTIONS)}")
        return errors
    required_key = "name"
    if normalized_type == "load_scene":
        required_key = "path"
    elif normalized_type == "load_scene_flow":
        required_key = "target"
    if required_key not in payload:
        errors.append(f"{path}.{required_key}: expected non-empty string")
    else:
        _expect_string(payload.get(required_key), path=f"{path}.{required_key}", errors=errors, non_empty=True)
    for key, item in payload.items():
        if key not in {"type", "name", "path", "target"}:
            _expect_json_serializable(item, path=f"{path}.{key}", errors=errors)
    return errors


def _validate_ui_button(data: dict[str, Any], *, path: str) -> list[str]:
    errors: list[str] = []
    if "enabled" in data:
        _expect_bool(data["enabled"], path=f"{path}.enabled", errors=errors)
    if "interactable" in data:
        _expect_bool(data["interactable"], path=f"{path}.interactable", errors=errors)
    if "label" in data:
        _expect_string(data["label"], path=f"{path}.label", errors=errors)
    for key in ("normal_color", "hover_color", "pressed_color", "disabled_color"):
        if key in data:
            _validate_rgba(data[key], path=f"{path}.{key}", errors=errors)
    if "transition_scale_pressed" in data:
        _expect_number(data["transition_scale_pressed"], path=f"{path}.transition_scale_pressed", errors=errors, exclusive_minimum=0.0)
    if "on_click" in data:
        errors.extend(_validate_button_on_click(data["on_click"], path=f"{path}.on_click"))
    return errors


CORE_COMPONENT_VALIDATORS: dict[str, Callable[[dict[str, Any], str], list[str]]] = {
    "Transform": lambda data, path: _validate_transform(data, path=path),
    "RectTransform": lambda data, path: _validate_rect_transform(data, path=path),
    "Sprite": lambda data, path: _validate_sprite(data, path=path),
    "Collider": lambda data, path: _validate_collider(data, path=path),
    "RigidBody": lambda data, path: _validate_rigidbody(data, path=path),
    "Animator": lambda data, path: _validate_animator(data, path=path),
    "Tilemap": lambda data, path: _validate_tilemap(data, path=path),
    "Camera2D": lambda data, path: _validate_camera2d(data, path=path),
    "InputMap": lambda data, path: _validate_input_map(data, path=path),
    "AudioSource": lambda data, path: _validate_audio_source(data, path=path),
    "ScriptBehaviour": lambda data, path: _validate_script_behaviour(data, path=path),
    "Canvas": lambda data, path: _validate_canvas(data, path=path),
    "UIText": lambda data, path: _validate_ui_text(data, path=path),
    "UIButton": lambda data, path: _validate_ui_button(data, path=path),
}


def _validate_prefab_instance(prefab_instance: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    payload = _expect_object(prefab_instance, path=path, errors=errors)
    if payload is None:
        return errors
    if "prefab_path" in payload:
        _expect_string(payload["prefab_path"], path=f"{path}.prefab_path", errors=errors, non_empty=True)
    if "root_name" in payload:
        _expect_string(payload["root_name"], path=f"{path}.root_name", errors=errors, non_empty=True)
    if "overrides" in payload and not isinstance(payload["overrides"], dict):
        errors.append(f"{path}.overrides: expected object")
    return errors


def _validate_entity(entity: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    payload = _expect_object(entity, path=path, errors=errors)
    if payload is None:
        return errors
    if "name" not in payload:
        errors.append(f"{path}.name: expected non-empty string")
    else:
        _expect_string(payload.get("name"), path=f"{path}.name", errors=errors, non_empty=True)
    components = payload.get("components", {})
    if not isinstance(components, dict):
        errors.append(f"{path}.components: expected object")
    else:
        for component_name, component_data in components.items():
            if not isinstance(component_name, str) or not component_name.strip():
                errors.append(f"{path}.components: expected non-empty string keys")
                continue
            if not isinstance(component_data, dict):
                errors.append(f"{path}.components.{component_name}: expected object")
                continue
            validator = CORE_COMPONENT_VALIDATORS.get(component_name)
            if validator is not None:
                errors.extend(validator(component_data, f"{path}.components.{component_name}"))
    if "component_metadata" in payload and not isinstance(payload.get("component_metadata"), dict):
        errors.append(f"{path}.component_metadata: expected object")
    if "prefab_instance" in payload:
        errors.extend(_validate_prefab_instance(payload.get("prefab_instance"), path=f"{path}.prefab_instance"))
    return errors


def _validate_entity_graph(
    entities: list[Any],
    *,
    path: str,
    root_parent_values: set[Any],
    counted_root_values: set[Any] | None = None,
) -> tuple[list[str], int]:
    errors: list[str] = []
    names_to_indexes: dict[str, int] = {}
    parents_by_name: dict[str, Any] = {}
    roots = 0
    counted_root_values = counted_root_values if counted_root_values is not None else root_parent_values
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            continue
        name = str(entity.get("name", "")).strip()
        if not name:
            continue
        if name in names_to_indexes:
            errors.append(f"{path}[{index}].name: duplicate entity name '{name}'")
        else:
            names_to_indexes[name] = index
        parent = entity.get("parent")
        parents_by_name[name] = parent
        if parent in counted_root_values:
            roots += 1
    for name, index in names_to_indexes.items():
        parent = parents_by_name.get(name)
        if parent in root_parent_values:
            continue
        if not isinstance(parent, str) or not parent.strip():
            errors.append(f"{path}[{index}].parent: expected non-empty string or null")
            continue
        if parent == name:
            errors.append(f"{path}[{index}].parent: entity cannot be its own parent")
            continue
        if parent not in names_to_indexes:
            errors.append(f"{path}[{index}].parent: unknown parent '{parent}'")
    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(name: str) -> None:
        if name in visited or name in visiting:
            return
        visiting.add(name)
        parent = parents_by_name.get(name)
        if isinstance(parent, str) and parent.strip() and parent in names_to_indexes:
            if parent in visiting:
                cycle_path = f"{path}[{names_to_indexes[name]}].parent"
                errors.append(f"{cycle_path}: cycle detected involving '{parent}'")
            else:
                walk(parent)
        visiting.discard(name)
        visited.add(name)

    for entity_name in names_to_indexes:
        walk(entity_name)
    return errors, roots


def _validate_rule_action(action: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    payload = _expect_object(action, path=path, errors=errors)
    if payload is None:
        return errors
    action_name = str(payload.get("action", "")).strip()
    if not action_name:
        errors.append(f"{path}.action: expected non-empty string")
        return errors
    if action_name not in SUPPORTED_RULE_ACTIONS:
        errors.append(f"{path}.action: unsupported action '{action_name}'")
        return errors
    if action_name == "set_animation":
        if not str(payload.get("entity", "")).strip():
            errors.append(f"{path}.entity: expected non-empty string")
        if not str(payload.get("state", "")).strip():
            errors.append(f"{path}.state: expected non-empty string")
    elif action_name == "set_position":
        if not str(payload.get("entity", "")).strip():
            errors.append(f"{path}.entity: expected non-empty string")
        if payload.get("x") is None and payload.get("y") is None:
            errors.append(f"{path}: expected x or y")
        if "x" in payload and payload.get("x") is not None:
            _expect_number(payload.get("x"), path=f"{path}.x", errors=errors)
        if "y" in payload and payload.get("y") is not None:
            _expect_number(payload.get("y"), path=f"{path}.y", errors=errors)
    elif action_name == "destroy_entity":
        if not str(payload.get("entity", "")).strip():
            errors.append(f"{path}.entity: expected non-empty string")
    elif action_name == "emit_event":
        if not str(payload.get("event", "")).strip():
            errors.append(f"{path}.event: expected non-empty string")
        if "data" in payload and not _is_json_serializable(payload.get("data")):
            errors.append(f"{path}.data: expected JSON-serializable value")
    elif action_name == "log_message":
        if not str(payload.get("message", "")).strip():
            errors.append(f"{path}.message: expected non-empty string")
    return errors


def _validate_rule(rule: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    payload = _expect_object(rule, path=path, errors=errors)
    if payload is None:
        return errors
    if not str(payload.get("event", "")).strip():
        errors.append(f"{path}.event: expected non-empty string")
    when = payload.get("when", {})
    if when is not None and not isinstance(when, dict):
        errors.append(f"{path}.when: expected object")
    actions = payload.get("do")
    if not isinstance(actions, list) or not actions:
        errors.append(f"{path}.do: expected non-empty array")
        return errors
    for index, action in enumerate(actions):
        errors.extend(_validate_rule_action(action, path=f"{path}.do[{index}]"))
    return errors


def _validate_scene_flow_metadata(value: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    payload = _expect_object(value, path=path, errors=errors)
    if payload is None:
        return errors
    if not payload:
        errors.append(f"{path}: expected non-empty object")
        return errors
    for key, item in payload.items():
        if not isinstance(key, str) or not key.strip():
            errors.append(f"{path}: expected non-empty string keys")
            continue
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{path}.{key}: expected non-empty string")
    return errors


def _validate_render_2d_metadata(value: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    payload = _expect_object(value, path=path, errors=errors)
    if payload is None:
        return errors
    if "sorting_layers" in payload:
        layers = payload["sorting_layers"]
        if not isinstance(layers, list):
            errors.append(f"{path}.sorting_layers: expected array")
        else:
            seen: set[str] = set()
            for index, item in enumerate(layers):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"{path}.sorting_layers[{index}]: expected non-empty string")
                    continue
                if item in seen:
                    errors.append(f"{path}.sorting_layers[{index}]: duplicate layer '{item}'")
                seen.add(item)
    if "minimap" in payload:
        minimap = _expect_object(payload["minimap"], path=f"{path}.minimap", errors=errors)
        if minimap is not None:
            if "enabled" in minimap:
                _expect_bool(minimap["enabled"], path=f"{path}.minimap.enabled", errors=errors)
            if "width" in minimap:
                _expect_int(minimap["width"], path=f"{path}.minimap.width", errors=errors, minimum=64)
            if "height" in minimap:
                _expect_int(minimap["height"], path=f"{path}.minimap.height", errors=errors, minimum=64)
            if "margin" in minimap:
                _expect_int(minimap["margin"], path=f"{path}.minimap.margin", errors=errors, minimum=0)
            for key, item in minimap.items():
                if key not in {"enabled", "width", "height", "margin"}:
                    _expect_json_serializable(item, path=f"{path}.minimap.{key}", errors=errors)
    for key, item in payload.items():
        if key not in {"sorting_layers", "minimap"}:
            _expect_json_serializable(item, path=f"{path}.{key}", errors=errors)
    return errors


def _validate_physics_2d_metadata(value: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    payload = _expect_object(value, path=path, errors=errors)
    if payload is None:
        return errors
    if "backend" in payload:
        backend = _expect_string(payload["backend"], path=f"{path}.backend", errors=errors, non_empty=True)
        if isinstance(backend, str) and backend.strip() not in PHYSICS_BACKENDS:
            errors.append(f"{path}.backend: expected one of {sorted(PHYSICS_BACKENDS)}")
    if "layer_matrix" in payload:
        matrix = _expect_object(payload["layer_matrix"], path=f"{path}.layer_matrix", errors=errors)
        if matrix is not None:
            for key, item in matrix.items():
                if not isinstance(key, str) or not key.strip():
                    errors.append(f"{path}.layer_matrix: expected non-empty string keys")
                    continue
                _expect_bool(item, path=f"{path}.layer_matrix.{key}", errors=errors)
    for key, item in payload.items():
        if key not in {"backend", "layer_matrix"}:
            _expect_json_serializable(item, path=f"{path}.{key}", errors=errors)
    return errors


def _validate_feature_metadata(value: Any, *, path: str) -> list[str]:
    errors: list[str] = []
    payload = _expect_object(value, path=path, errors=errors)
    if payload is None:
        return errors
    for key, item in payload.items():
        if key == "scene_flow":
            errors.extend(_validate_scene_flow_metadata(item, path=f"{path}.scene_flow"))
        elif key == "render_2d":
            errors.extend(_validate_render_2d_metadata(item, path=f"{path}.render_2d"))
        elif key == "physics_2d":
            errors.extend(_validate_physics_2d_metadata(item, path=f"{path}.physics_2d"))
        else:
            _expect_json_serializable(item, path=f"{path}.{key}", errors=errors)
    return errors


def validate_scene_data(data: Any) -> list[str]:
    errors: list[str] = []
    payload = _expect_object(data, path="$", errors=errors)
    if payload is None:
        return errors
    if payload.get("schema_version") != CURRENT_SCENE_SCHEMA_VERSION:
        errors.append(f"$.schema_version: expected {CURRENT_SCENE_SCHEMA_VERSION}, got {payload.get('schema_version')}")
    if not str(payload.get("name", "")).strip():
        errors.append("$.name: expected non-empty string")
    entities = payload.get("entities")
    if not isinstance(entities, list):
        errors.append("$.entities: expected array")
    else:
        for index, entity in enumerate(entities):
            errors.extend(_validate_entity(entity, path=f"$.entities[{index}]"))
        graph_errors, _ = _validate_entity_graph(
            entities,
            path="$.entities",
            root_parent_values={None},
            counted_root_values={None},
        )
        errors.extend(graph_errors)
    rules = payload.get("rules")
    if not isinstance(rules, list):
        errors.append("$.rules: expected array")
    else:
        for index, rule in enumerate(rules):
            errors.extend(_validate_rule(rule, path=f"$.rules[{index}]"))
    errors.extend(_validate_feature_metadata(payload.get("feature_metadata"), path="$.feature_metadata"))
    return errors


def validate_prefab_data(data: Any) -> list[str]:
    errors: list[str] = []
    payload = _expect_object(data, path="$", errors=errors)
    if payload is None:
        return errors
    if payload.get("schema_version") != CURRENT_PREFAB_SCHEMA_VERSION:
        errors.append(f"$.schema_version: expected {CURRENT_PREFAB_SCHEMA_VERSION}, got {payload.get('schema_version')}")
    if not str(payload.get("root_name", "")).strip():
        errors.append("$.root_name: expected non-empty string")
    entities = payload.get("entities")
    if not isinstance(entities, list) or not entities:
        errors.append("$.entities: expected non-empty array")
    elif isinstance(entities, list):
        for index, entity in enumerate(entities):
            errors.extend(_validate_entity(entity, path=f"$.entities[{index}]"))
        graph_errors, roots = _validate_entity_graph(
            entities,
            path="$.entities",
            root_parent_values={None, ""},
            counted_root_values={None},
        )
        errors.extend(graph_errors)
        if roots != 1:
            errors.append(f"$.entities: expected exactly one root entity, got {roots}")
    return errors


def detect_payload_kind(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".prefab":
        return "prefab"
    return "scene"
