from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from engine.api import EngineAPI

GRID_SIZE = 64.0


def _transform(x: float, y: float) -> Dict[str, Any]:
    return {
        "enabled": True,
        "x": float(x),
        "y": float(y),
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
    }


def _collider(width: float, height: float, *, is_trigger: bool = False) -> Dict[str, Any]:
    return {
        "enabled": True,
        "width": float(width),
        "height": float(height),
        "offset_x": 0.0,
        "offset_y": 0.0,
        "is_trigger": bool(is_trigger),
        "shape_type": "box",
        "friction": 0.2,
        "restitution": 0.0,
        "density": 1.0,
    }


def _player_components(x: float, y: float) -> Dict[str, Dict[str, Any]]:
    return {
        "Transform": _transform(x, y),
        "Collider": _collider(28.0, 40.0),
        "RigidBody": {
            "enabled": True,
            "velocity_x": 0.0,
            "velocity_y": 0.0,
            "gravity_scale": 1.0,
            "is_grounded": False,
            "body_type": "dynamic",
            "simulated": True,
        },
        "InputMap": {
            "enabled": True,
            "move_left": "A,LEFT",
            "move_right": "D,RIGHT",
            "move_up": "W,UP",
            "move_down": "S,DOWN",
            "action_1": "SPACE",
            "action_2": "ENTER",
        },
        "PlayerController2D": {
            "enabled": True,
            "move_speed": 180.0,
            "jump_velocity": -320.0,
            "air_control": 0.75,
        },
    }


def _terrain_components(center_x: float, center_y: float, width: float, height: float) -> Dict[str, Dict[str, Any]]:
    return {
        "Transform": _transform(center_x, center_y),
        "Collider": _collider(width, height),
    }


def _goal_components(x: float, y: float) -> Dict[str, Dict[str, Any]]:
    return {
        "Transform": _transform(x, y),
        "Collider": _collider(48.0, 64.0, is_trigger=True),
        "Goal2D": {
            "enabled": True,
            "complete_on_touch": True,
            "next_scene": "",
            "event_name": "goal_reached",
        },
    }


def _coin_components(x: float, y: float, points: int) -> Dict[str, Dict[str, Any]]:
    return {
        "Transform": _transform(x, y),
        "Collider": _collider(24.0, 24.0, is_trigger=True),
        "Collectible2D": {
            "enabled": True,
            "points": max(0, int(points)),
            "destroy_on_collect": True,
            "event_name": "collectible_collected",
        },
    }


def _hazard_components(x: float, y: float, damage: int) -> Dict[str, Dict[str, Any]]:
    return {
        "Transform": _transform(x, y),
        "Collider": _collider(48.0, 32.0, is_trigger=True),
        "Hazard2D": {
            "enabled": True,
            "damage": max(0, int(damage)),
            "respawn_on_touch": True,
            "event_name": "hazard_touched",
        },
    }


def _respawn_components(x: float, y: float, spawn_id: str) -> Dict[str, Dict[str, Any]]:
    normalized_id = str(spawn_id or "default").strip() or "default"
    return {
        "Transform": _transform(x, y),
        "RespawnPoint2D": {
            "enabled": True,
            "spawn_id": normalized_id,
            "active": True,
        },
    }


def _safe_entity_suffix(value: str) -> str:
    suffix = "".join(ch if ch.isalnum() else "_" for ch in str(value or "").strip())
    return suffix.strip("_") or "default"


def _relative_scene_path(api: EngineAPI, scene_path: str) -> str:
    if not scene_path:
        return ""
    normalized = scene_path.replace("\\", "/")
    if api.project_service is None:
        return normalized
    return api.project_service.to_relative_path(normalized).replace("\\", "/")


def _scene_candidates(api: EngineAPI) -> list[tuple[str, str]]:
    if api.project_service is None:
        return []

    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(scene_ref: Any, source: str) -> None:
        value = str(scene_ref or "").strip()
        if not value:
            return
        key = value.replace("\\", "/")
        if key in seen:
            return
        seen.add(key)
        candidates.append((value, source))

    editor_state = api.project_service.load_editor_state()
    add(editor_state.get("active_scene"), "editor_state.active_scene")
    add(api.project_service.load_project_settings().get("startup_scene"), "settings.startup_scene")

    for scene in api.project_service.list_project_scenes():
        add(scene.get("path"), "levels.first_scene")
        break

    return candidates


def _load_platformer_authoring_scene(api: EngineAPI) -> Dict[str, Any]:
    warnings: list[str] = []
    if api.has_active_scene():
        scene = api.get_active_scene_info()
        return {
            "success": True,
            "scene_path": _relative_scene_path(api, str(scene.get("path", ""))),
            "warnings": warnings,
        }

    if api.project_service is None:
        return {"success": False, "message": "Project service not ready", "warnings": warnings}

    for scene_ref, source in _scene_candidates(api):
        resolved = api.project_service.resolve_path(scene_ref)
        if not resolved.exists() or not resolved.is_file():
            warnings.append(f"Scene candidate from {source} is missing: {scene_ref}")
            continue
        result = api.load_scene(scene_ref)
        if result.get("success"):
            warnings.append(f"Loaded scene from {source}: {_relative_scene_path(api, resolved.as_posix())}")
            return {
                "success": True,
                "scene_path": _relative_scene_path(api, resolved.as_posix()),
                "warnings": warnings,
            }
        warnings.append(f"Scene candidate from {source} did not load: {scene_ref}")

    return {
        "success": False,
        "message": "No active, startup or fallback scene is loadable",
        "warnings": warnings,
    }


def _select_platformer_scene_path(api: EngineAPI) -> Dict[str, Any]:
    warnings: list[str] = []
    if api.has_active_scene():
        scene = api.get_active_scene_info()
        scene_path = str(scene.get("path", "") or "")
        return {
            "success": bool(scene_path),
            "path": scene_path,
            "scene_path": scene_path.replace("\\", "/"),
            "source": "active_scene",
            "warnings": warnings,
        }

    if api.project_service is None:
        return {"success": False, "message": "Project service not ready", "warnings": warnings}

    for scene_ref, source in _scene_candidates(api):
        resolved = api.project_service.resolve_path(scene_ref)
        if resolved.exists() and resolved.is_file():
            return {
                "success": True,
                "path": resolved.as_posix(),
                "scene_path": _relative_scene_path(api, resolved.as_posix()),
                "source": source,
                "warnings": warnings,
            }
        warnings.append(f"Scene candidate from {source} is missing: {scene_ref}")

    return {
        "success": False,
        "message": "No active, startup or fallback scene is loadable",
        "warnings": warnings,
    }


def _entity_payload(api: EngineAPI, entity_name: str) -> Dict[str, Any] | None:
    try:
        return api.get_entity(entity_name)
    except Exception:
        return None


def _ensure_component(api: EngineAPI, entity_name: str, component_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    entity = _entity_payload(api, entity_name)
    if entity is None:
        return {"success": False, "message": f"Entity not found: {entity_name}"}
    components = entity.get("components", {})
    if component_name in components:
        authoring = api.scene_authoring
        if authoring is None:
            return {"success": False, "message": "SceneManager not ready"}
        success = authoring.replace_component_data(entity_name, component_name, payload)
        return {"success": success, "message": "Component replaced" if success else "Component replace failed"}
    return api.add_component(entity_name, component_name, payload)


def _upsert_platformer_entity(
    api: EngineAPI,
    entity_name: str,
    components: Dict[str, Dict[str, Any]],
    *,
    tag: str,
    layer: str = "Gameplay",
) -> Dict[str, Any]:
    warnings: list[str] = []
    created_entities: list[str] = []
    if _entity_payload(api, entity_name) is None:
        result = api.create_entity(entity_name, components=components)
        if not result.get("success"):
            return {"success": False, "message": result.get("message", f"Failed to create {entity_name}")}
        created_entities.append(entity_name)
    else:
        warnings.append(f"Entity '{entity_name}' already exists; updating components.")
        for component_name, payload in components.items():
            result = _ensure_component(api, entity_name, component_name, payload)
            if not result.get("success"):
                return {"success": False, "message": result.get("message", f"Failed to update {component_name}")}

    tag_result = api.set_entity_tag(entity_name, tag)
    if not tag_result.get("success"):
        return {"success": False, "message": tag_result.get("message", "Failed to set entity tag")}
    layer_result = api.set_entity_layer(entity_name, layer)
    if not layer_result.get("success"):
        return {"success": False, "message": layer_result.get("message", "Failed to set entity layer")}

    return {"success": True, "entities_created": created_entities, "warnings": warnings}


def _save_platformer_result(
    api: EngineAPI,
    message: str,
    scene_path: str,
    created_entities: list[str],
    warnings: list[str],
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    save_result = api.save_scene()
    if not save_result.get("success"):
        return save_result
    data = {
        "scene_path": scene_path,
        "entities_created": created_entities,
        "warnings": warnings,
    }
    if extra:
        data.update(extra)
    return {"success": True, "message": message, "data": data}


def add_platformer_player(api: EngineAPI, x: float, y: float) -> Dict[str, Any]:
    scene = _load_platformer_authoring_scene(api)
    if not scene.get("success"):
        return scene
    upsert = _upsert_platformer_entity(api, "Player", _player_components(x, y), tag="Player")
    if not upsert.get("success"):
        return upsert
    warnings = [*scene.get("warnings", []), *upsert.get("warnings", [])]
    return _save_platformer_result(
        api,
        "Platformer player ensured",
        str(scene.get("scene_path", "")),
        list(upsert.get("entities_created", [])),
        warnings,
    )


def add_platformer_ground(api: EngineAPI, from_x: float, to_x: float, y: float) -> Dict[str, Any]:
    scene = _load_platformer_authoring_scene(api)
    if not scene.get("success"):
        return scene
    start = float(from_x)
    end = float(to_x)
    if end <= start:
        return {"success": False, "message": "--to-x must be greater than --from-x"}
    width = (end - start) * GRID_SIZE
    center_x = (start + (end - start) / 2.0) * GRID_SIZE
    center_y = float(y) * GRID_SIZE
    upsert = _upsert_platformer_entity(
        api,
        "Ground",
        _terrain_components(center_x, center_y, width, 48.0),
        tag="Ground",
    )
    if not upsert.get("success"):
        return upsert
    warnings = [*scene.get("warnings", []), *upsert.get("warnings", [])]
    return _save_platformer_result(
        api,
        "Platformer ground ensured",
        str(scene.get("scene_path", "")),
        list(upsert.get("entities_created", [])),
        warnings,
        {"grid_size": GRID_SIZE, "from_x": start, "to_x": end, "y": float(y)},
    )


def add_platformer_platform(api: EngineAPI, x: float, y: float, width: float) -> Dict[str, Any]:
    scene = _load_platformer_authoring_scene(api)
    if not scene.get("success"):
        return scene
    platform_width = float(width)
    if platform_width <= 0:
        return {"success": False, "message": "--width must be greater than zero"}
    center_x = (float(x) + platform_width / 2.0) * GRID_SIZE
    center_y = float(y) * GRID_SIZE
    upsert = _upsert_platformer_entity(
        api,
        "Platform",
        _terrain_components(center_x, center_y, platform_width * GRID_SIZE, 32.0),
        tag="Platform",
    )
    if not upsert.get("success"):
        return upsert
    warnings = [*scene.get("warnings", []), *upsert.get("warnings", [])]
    return _save_platformer_result(
        api,
        "Platformer platform ensured",
        str(scene.get("scene_path", "")),
        list(upsert.get("entities_created", [])),
        warnings,
        {"grid_size": GRID_SIZE, "x": float(x), "y": float(y), "width": platform_width},
    )


def add_platformer_goal(api: EngineAPI, x: float, y: float) -> Dict[str, Any]:
    scene = _load_platformer_authoring_scene(api)
    if not scene.get("success"):
        return scene
    upsert = _upsert_platformer_entity(api, "Goal", _goal_components(x, y), tag="Goal")
    if not upsert.get("success"):
        return upsert
    warnings = [*scene.get("warnings", []), *upsert.get("warnings", [])]
    return _save_platformer_result(
        api,
        "Platformer goal ensured",
        str(scene.get("scene_path", "")),
        list(upsert.get("entities_created", [])),
        warnings,
    )


def add_platformer_coin(api: EngineAPI, x: float, y: float, points: int) -> Dict[str, Any]:
    scene = _load_platformer_authoring_scene(api)
    if not scene.get("success"):
        return scene
    upsert = _upsert_platformer_entity(
        api,
        "Coin",
        _coin_components(x, y, points),
        tag="Collectible",
    )
    if not upsert.get("success"):
        return upsert
    warnings = [*scene.get("warnings", []), *upsert.get("warnings", [])]
    return _save_platformer_result(
        api,
        "Platformer coin ensured",
        str(scene.get("scene_path", "")),
        list(upsert.get("entities_created", [])),
        warnings,
        {"points": max(0, int(points))},
    )


def add_platformer_hazard(api: EngineAPI, x: float, y: float, damage: int) -> Dict[str, Any]:
    scene = _load_platformer_authoring_scene(api)
    if not scene.get("success"):
        return scene
    upsert = _upsert_platformer_entity(
        api,
        "Hazard",
        _hazard_components(x, y, damage),
        tag="Hazard",
    )
    if not upsert.get("success"):
        return upsert
    warnings = [*scene.get("warnings", []), *upsert.get("warnings", [])]
    return _save_platformer_result(
        api,
        "Platformer hazard ensured",
        str(scene.get("scene_path", "")),
        list(upsert.get("entities_created", [])),
        warnings,
        {"damage": max(0, int(damage))},
    )


def add_platformer_respawn(api: EngineAPI, x: float, y: float, spawn_id: str) -> Dict[str, Any]:
    scene = _load_platformer_authoring_scene(api)
    if not scene.get("success"):
        return scene
    normalized_id = str(spawn_id or "default").strip() or "default"
    entity_name = f"Respawn_{_safe_entity_suffix(normalized_id)}"
    upsert = _upsert_platformer_entity(
        api,
        entity_name,
        _respawn_components(x, y, normalized_id),
        tag="Respawn",
    )
    if not upsert.get("success"):
        return upsert
    warnings = [*scene.get("warnings", []), *upsert.get("warnings", [])]
    return _save_platformer_result(
        api,
        "Platformer respawn point ensured",
        str(scene.get("scene_path", "")),
        list(upsert.get("entities_created", [])),
        warnings,
        {"spawn_id": normalized_id, "entity": entity_name},
    )


def validate_platformer_scene(api: EngineAPI) -> Dict[str, Any]:
    scene_selection = _select_platformer_scene_path(api)
    warnings = list(scene_selection.get("warnings", []))
    validation: Dict[str, Any] = {
        "scene_exists": False,
        "scene_loads": False,
        "player_exists": False,
        "player_minimal_components": False,
        "terrain_exists": False,
        "goal_exists": False,
        "goal_minimal_components": False,
        "strict_compliance_passes": False,
        "external_runtime_clean": False,
    }
    if not scene_selection.get("success"):
        return {
            "success": False,
            "message": scene_selection.get("message", "No scene selected"),
            "data": {
                "scene_path": "",
                "entities_created": [],
                "warnings": warnings,
                "validation": validation,
            },
        }

    scene_path = str(scene_selection.get("path", ""))
    validation["scene_exists"] = bool(scene_path and Path(scene_path).exists())
    try:
        if api.scene_manager is None or api.runtime is None:
            raise RuntimeError("Engine not initialized")
        world = api.scene_manager.load_scene_from_file(scene_path, activate=True)
        if world is None:
            raise RuntimeError("SceneManager returned no world")
        api.runtime.set_world(world)
        validation["scene_loads"] = True
    except Exception as exc:
        warnings.append(f"Scene load failed: {exc}")

    entities = api.list_entities() if validation["scene_loads"] else []
    by_name = {entity.get("name"): entity for entity in entities}
    player = by_name.get("Player")
    validation["player_exists"] = player is not None
    required_player = {"Transform", "Collider", "RigidBody", "InputMap", "PlayerController2D"}
    if player is not None:
        validation["player_minimal_components"] = required_player.issubset(set(player.get("components", {}).keys()))

    for entity in entities:
        name_or_tag = {str(entity.get("name", "")), str(entity.get("tag", ""))}
        collider = entity.get("components", {}).get("Collider")
        if name_or_tag.intersection({"Ground", "Platform"}) and isinstance(collider, dict) and not collider.get("is_trigger", False):
            validation["terrain_exists"] = True
            break

    goal = by_name.get("Goal")
    validation["goal_exists"] = goal is not None
    if goal is not None:
        components = goal.get("components", {})
        collider = components.get("Collider")
        validation["goal_minimal_components"] = (
            "Transform" in components
            and "Goal2D" in components
            and isinstance(collider, dict)
            and bool(collider.get("is_trigger", False))
        )

    semantic_entities = {
        "collectibles": [
            entity.get("name", "")
            for entity in entities
            if "Collectible2D" in (entity.get("components", {}) or {})
        ],
        "hazards": [
            entity.get("name", "")
            for entity in entities
            if "Hazard2D" in (entity.get("components", {}) or {})
        ],
        "goals": [
            entity.get("name", "")
            for entity in entities
            if "Goal2D" in (entity.get("components", {}) or {})
        ],
        "respawns": [
            entity.get("name", "")
            for entity in entities
            if "RespawnPoint2D" in (entity.get("components", {}) or {})
        ],
    }

    if api.project_service is not None:
        from engine.ai.compliance import run_ai_compliance

        compliance = run_ai_compliance(api.project_service.project_root, strict=True)
        validation["strict_compliance_passes"] = bool(compliance.get("strict_pass"))
        validation["external_runtime_clean"] = not bool(compliance.get("external_runtime_blocking"))
        if not compliance.get("strict_pass"):
            warnings.append("Strict AI compliance did not pass.")

    success = all(bool(value) for value in validation.values())
    return {
        "success": success,
        "message": "Platformer scene validation passed" if success else "Platformer scene validation failed",
        "data": {
            "scene_path": str(scene_selection.get("scene_path", "")),
            "entities_created": [],
            "warnings": warnings,
            "validation": validation,
            "semantic_entities": semantic_entities,
        },
    }


def create_minimal_platformer_scene(api: EngineAPI, scene_name: str) -> Dict[str, Any]:
    """Create a minimal native 2D platformer scene using public EngineAPI surfaces."""
    result = api.create_scene(scene_name)
    if not result.get("success"):
        return result

    scene_info = api.get_active_scene_info()
    scene_path = str(scene_info.get("path", "") or result.get("data", {}).get("path", "") or "")
    created_entities: list[str] = []

    player = api.create_entity("Player", components=_player_components(160.0, 460.0))
    if not player.get("success"):
        return player
    created_entities.append("Player")
    api.set_entity_tag("Player", "Player")
    api.set_entity_layer("Player", "Gameplay")

    ground = api.create_entity(
        "Ground",
        components=_terrain_components(320.0, 520.0, 640.0, 48.0),
    )
    if not ground.get("success"):
        return ground
    created_entities.append("Ground")
    api.set_entity_tag("Ground", "Ground")
    api.set_entity_layer("Ground", "Gameplay")

    camera = api.create_camera2d(
        "MainCamera",
        transform={"x": 320.0, "y": 180.0},
        camera={
            "offset_x": 320.0,
            "offset_y": 180.0,
            "zoom": 1.0,
            "is_primary": True,
            "follow_entity": "Player",
            "framing_mode": "platformer",
            "dead_zone_width": 120.0,
            "dead_zone_height": 80.0,
            "recenter_on_play": True,
        },
    )
    if not camera.get("success"):
        return camera
    created_entities.append("MainCamera")
    api.set_entity_tag("MainCamera", "Camera")
    api.set_entity_layer("MainCamera", "System")

    save_result = api.save_scene()
    if not save_result.get("success"):
        return save_result

    if api.project_service is not None and scene_path:
        settings = api.project_service.load_project_settings()
        settings["startup_scene"] = api.project_service.to_relative_path(scene_path)
        api.project_service.save_project_settings(settings)

    startup_scene = ""
    if api.project_service is not None:
        startup_scene = str(api.project_service.load_project_settings().get("startup_scene", "") or "")

    return {
        "success": True,
        "message": "Minimal platformer scene created",
        "data": {
            "scene_name": scene_name,
            "scene_path": _relative_scene_path(api, scene_path),
            "startup_scene": startup_scene,
            "entities_created": created_entities,
            "entity_count": len(created_entities),
            "scene_file": Path(scene_path).name if scene_path else "",
            "warnings": [],
        },
    }
