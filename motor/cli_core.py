"""
motor/cli_core.py - Core CLI command implementations for MotorVideojuegosIA

This module contains all the command handler implementations for the motor CLI.
It is designed to be independent of argument parsing and can be used programmatically.
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.ai import get_default_registry
from engine.api import EngineAPI
from engine.config import ENGINE_VERSION
from engine.project.project_service import ProjectService
from engine.recipes import (
    RecipeError,
    RecipeNotFoundError,
    RecipeValidationError,
    get_recipe,
    run_recipe,
)
from motor.platformer_scaffold import (
    add_platformer_checkpoint,
    add_platformer_coin,
    add_platformer_enemy_patrol,
    add_platformer_goal,
    add_platformer_ground,
    add_platformer_hazard,
    add_platformer_killzone,
    add_platformer_moving_platform,
    add_platformer_platform,
    add_platformer_player,
    add_platformer_respawn,
    create_minimal_platformer_scene,
    set_platformer_bounds,
    set_platformer_camera_follow,
    validate_platformer_scene,
)


class EngineCLIError(Exception):
    """Base exception for CLI errors with exit codes."""
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code
        self.message = message


class ProjectNotFoundError(EngineCLIError):
    """Project directory or manifest not found."""
    def __init__(self, path: str):
        super().__init__(f"Project not found or invalid: {path}", exit_code=2)


class EngineInitError(EngineCLIError):
    """Failed to initialize engine."""
    def __init__(self, message: str):
        super().__init__(f"Engine initialization failed: {message}", exit_code=3)


def _make_response(success: bool, message: str, data: Any = None) -> Dict[str, Any]:
    """Create a standard JSON response."""
    return {
        "success": success,
        "message": message,
        "data": data if data is not None else {},
    }


def _print_json(response: Dict[str, Any]) -> None:
    """Print response as formatted JSON."""
    print(json.dumps(response, indent=2, ensure_ascii=True))


def _output(success: bool, message: str, data: Any, as_json: bool) -> int:
    """Output response in appropriate format and return exit code."""
    if as_json:
        _print_json(_make_response(success, message, data))
    else:
        print(message)
        if data:
            print(json.dumps(data, indent=2, ensure_ascii=True))
    return 0 if success else 1


def _ensure_project(project_path: Path) -> None:
    """Verify project exists and has a valid manifest."""
    manifest_path = project_path / "project.json"
    if not manifest_path.exists():
        raise ProjectNotFoundError(str(project_path))
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectNotFoundError(
            f"Invalid project.json in {project_path}: not valid JSON — {exc}"
        )
    if not isinstance(data, dict):
        raise ProjectNotFoundError(
            f"Invalid project.json in {project_path}: root must be a JSON object"
        )
    missing = []
    if "name" not in data:
        missing.append("name")
    if "version" not in data:
        missing.append("version")
    if missing:
        raise ProjectNotFoundError(
            f"Invalid project.json in {project_path}: missing required field(s) {', '.join(missing)}"
        )


def _init_engine(project_path: Path, auto_ensure_project: bool = True, read_only: bool = False) -> EngineAPI:
    """Initialize EngineAPI for the project."""
    try:
        return EngineAPI(
            project_root=str(project_path),
            sandbox_paths=False,
            auto_ensure_project=auto_ensure_project,
            read_only=read_only,
        )
    except Exception as exc:
        raise EngineInitError(str(exc))


def _auto_load_scene(api: EngineAPI) -> tuple[bool, str]:
    """Auto-load the last active scene if no scene is currently active.
    
    Uses only public EngineAPI surfaces - no direct SceneManager access.
    
    Returns:
        Tuple of (success, message)
    """
    # Check if scene is already active using public API
    if api.has_active_scene():
        scene_info = api.get_active_scene_info()
        return True, f"Scene already active: {scene_info.get('name', 'unknown')}"
    
    # Try to load the last scene from editor state
    editor_state = api.get_editor_state()
    last_scene = editor_state.get("last_scene", "")
    if last_scene:
        load_result = api.load_scene(last_scene)
        if load_result.get("success"):
            return True, f"Loaded scene: {last_scene}"
        else:
            return False, f"Failed to load last scene: {load_result.get('message')}"
    else:
        return False, "No active scene. Create or load a scene first."


def _runtime_status(api: EngineAPI) -> Dict[str, Any]:
    """Return a serializable runtime status through the public API."""
    try:
        return dict(api.get_status())
    except Exception as exc:
        return {"error": str(exc)}


def _runtime_scene_info(api: EngineAPI) -> Dict[str, Any]:
    """Return active scene info through the public API."""
    try:
        return dict(api.get_active_scene_info())
    except Exception as exc:
        return {
            "has_scene": False,
            "path": "",
            "name": "",
            "key": "",
            "dirty": False,
            "entity_count": 0,
            "error": str(exc),
        }


def _ensure_runtime_scene(api: EngineAPI, warnings: List[str]) -> tuple[bool, Dict[str, Any]]:
    """Load a scene for headless runtime verification without persisting state."""
    if api.has_active_scene():
        return True, _runtime_scene_info(api)

    warnings.append(
        "No active scene in this stateless CLI process; attempting to load a scene for headless runtime inspection."
    )
    result = api.load_scene_for_runtime_inspection()
    if not result.get("success"):
        warnings.append("No active scene could be loaded. Create or load a scene before runtime validation.")
        return False, {"has_scene": False, "load_result": result}

    warnings.append("Loaded a fallback scene for this headless runtime process only; authoring state was not saved.")
    return True, _runtime_scene_info(api)


def _runtime_response_base(command: str, headless: bool, warnings: List[str]) -> Dict[str, Any]:
    return {
        "command": command,
        "headless": bool(headless),
        "stateless": True,
        "warnings": list(warnings),
    }


_SIMULATED_INPUT_TOKENS = {
    "left",
    "right",
    "up",
    "down",
    "jump",
    "action_1",
    "action_2",
}


def _parse_runtime_input(input_spec: Optional[str], warnings: List[str]) -> tuple[Optional[Dict[str, float]], List[str], List[str]]:
    if input_spec is None or not str(input_spec).strip():
        return None, [], []

    tokens = [item.strip().lower() for item in str(input_spec).split(",") if item.strip()]
    invalid = [token for token in tokens if token not in _SIMULATED_INPUT_TOKENS]
    if invalid:
        warnings.append(f"Unsupported runtime input token(s): {', '.join(invalid)}")
        return None, tokens, invalid

    token_set = set(tokens)
    horizontal = 0.0
    if "left" in token_set:
        horizontal -= 1.0
    if "right" in token_set:
        horizontal += 1.0
    if "left" in token_set and "right" in token_set:
        warnings.append("Conflicting horizontal input left/right cancelled to 0.")

    vertical = 0.0
    if "down" in token_set:
        vertical -= 1.0
    if "up" in token_set:
        vertical += 1.0
    if "up" in token_set and "down" in token_set:
        warnings.append("Conflicting vertical input up/down cancelled to 0.")

    return {
        "horizontal": horizontal,
        "vertical": vertical,
        "action_1": 1.0 if "jump" in token_set or "action_1" in token_set else 0.0,
        "action_2": 1.0 if "action_2" in token_set else 0.0,
    }, tokens, []


def _find_runtime_input_player(api: EngineAPI) -> Optional[str]:
    try:
        player = api.get_entity("Player")
        components = player.get("components", {})
        if "InputMap" in components and "PlayerController2D" in components:
            return "Player"
    except Exception:
        pass

    for entity in api.list_entities(active=True):
        components = entity.get("components", {})
        if "InputMap" in components and "PlayerController2D" in components:
            return str(entity.get("name", "") or "")
    return None


def _player_runtime_snapshot(api: EngineAPI, entity_name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not entity_name:
        return None
    try:
        entity = api.get_entity(entity_name)
    except Exception:
        return None
    components = entity.get("components", {})
    return {
        "name": entity.get("name", entity_name),
        "tag": entity.get("tag", ""),
        "layer": entity.get("layer", ""),
        "Transform": components.get("Transform"),
        "RigidBody": components.get("RigidBody"),
        "InputMap": components.get("InputMap"),
        "PlayerController2D": components.get("PlayerController2D"),
    }


def cmd_runtime_play(project_path: Path, headless: bool, json_output: bool) -> int:
    """Start a stateless headless PLAY smoke check through EngineAPI."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        status_before = _runtime_status(api)

        data = _runtime_response_base("runtime play", True, warnings)
        data.update({
            "scene": scene,
            "status_before": status_before,
            "status_after": status_before,
            "cleanup_status": status_before,
        })
        if not scene_ready:
            return _output(False, "Runtime play failed: no active scene", data, json_output)

        api.play()
        data["status_after"] = _runtime_status(api)
        api.stop()
        data["cleanup_status"] = _runtime_status(api)
        data["warnings"] = list(warnings)
        return _output(True, "Runtime play completed in stateless headless mode", data, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Runtime play failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_runtime_step(project_path: Path, frames: int, json_output: bool, input_spec: Optional[str] = None) -> int:
    """Run PLAY -> STEP -> STOP headlessly in one stateless CLI process."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    normalized_frames = max(1, int(frames))
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        status_before = _runtime_status(api)

        input_state, input_sequence, invalid_inputs = _parse_runtime_input(input_spec, warnings)

        data = _runtime_response_base("runtime step", True, warnings)
        data.update({
            "scene": scene,
            "scene_path": str(scene.get("path", "") or ""),
            "frames_requested": normalized_frames,
            "frames_simulated": 0,
            "input_sequence": input_sequence,
            "player_before": None,
            "player_after": None,
            "events": [],
            "status_before": status_before,
            "status_after_play": status_before,
            "status_after_step": status_before,
            "status_after": status_before,
        })
        if invalid_inputs:
            return _output(False, "Runtime step failed: unsupported input token", data, json_output)
        if not scene_ready:
            return _output(False, "Runtime step failed: no active scene", data, json_output)

        api.play()
        data["status_after_play"] = _runtime_status(api)
        player_name = _find_runtime_input_player(api)
        if input_state is not None:
            if not player_name:
                warnings.append("No Player entity with InputMap and PlayerController2D found for input simulation.")
                data["warnings"] = list(warnings)
                api.stop()
                data["status_after"] = _runtime_status(api)
                return _output(False, "Runtime step failed: no input-capable player", data, json_output)
            data["player_before"] = _player_runtime_snapshot(api, player_name)
            inject_result = api.inject_input_state(player_name, input_state, frames=normalized_frames)
            if not inject_result.get("success"):
                warnings.append(str(inject_result.get("message") or "Input injection failed"))
                data["warnings"] = list(warnings)
                api.stop()
                data["status_after"] = _runtime_status(api)
                return _output(False, "Runtime step failed: input injection failed", data, json_output)
        elif player_name:
            data["player_before"] = _player_runtime_snapshot(api, player_name)

        api.step(normalized_frames)
        data["frames_simulated"] = normalized_frames
        if player_name:
            data["player_after"] = _player_runtime_snapshot(api, player_name)
        data["events"] = api.get_recent_events(50)
        data["status_after_step"] = _runtime_status(api)
        api.stop()
        data["status_after"] = _runtime_status(api)
        data["warnings"] = list(warnings)
        return _output(True, "Runtime step completed in stateless headless mode", data, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Runtime step failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_runtime_stop(project_path: Path, json_output: bool) -> int:
    """Stop runtime safely in a stateless CLI process."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = [
        "Runtime CLI is stateless; this command cannot stop a PLAY session from a previous process."
    ]
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        if not api.has_active_scene():
            warnings.append("No active scene in this stateless CLI process.")
        status_before = _runtime_status(api)
        api.stop()
        status_after = _runtime_status(api)
        data = _runtime_response_base("runtime stop", True, warnings)
        data.update({
            "scene": _runtime_scene_info(api),
            "status_before": status_before,
            "status_after": status_after,
        })
        return _output(True, "Runtime stop completed in stateless headless mode", data, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Runtime stop failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass



def cmd_runtime_status(project_path: Path, json_output: bool) -> int:
    """Return runtime status and active scene info read-only."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        status = _runtime_status(api)
        data = _runtime_response_base("runtime status", True, warnings)
        data.update({
            "status": status,
            "scene": scene,
        })
        if not scene_ready:
            return _output(False, "Runtime status: no active scene", data, json_output)
        return _output(True, "Runtime status read-only inspection completed", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Runtime status failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_runtime_entities(
    project_path: Path,
    tag: Optional[str],
    layer: Optional[str],
    active_only: bool,
    json_output: bool,
) -> int:
    """List entities in the active scene read-only."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        if not scene_ready:
            return _output(False, "Runtime entities failed: no active scene", {
                "command": "runtime entities",
                "headless": True,
                "stateless": True,
                "warnings": warnings,
                "entities": [],
                "count": 0,
            }, json_output)
        active = True if active_only else None
        entities = api.list_entities(tag=tag, layer=layer, active=active)
        data = _runtime_response_base("runtime entities", True, warnings)
        data.update({
            "scene": scene,
            "entities": entities,
            "count": len(entities),
        })
        return _output(True, f"Listed {len(entities)} entities", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Runtime entities failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_runtime_inspect(project_path: Path, entity_name: str, json_output: bool) -> int:
    """Inspect a specific entity read-only."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        if not scene_ready:
            return _output(False, "Runtime inspect failed: no active scene", {
                "command": "runtime inspect",
                "headless": True,
                "stateless": True,
                "warnings": warnings,
                "entity": None,
            }, json_output)
        entity_data = api.get_entity(entity_name)
        data = _runtime_response_base("runtime inspect", True, warnings)
        data.update({
            "scene": scene,
            "entity": entity_data,
        })
        return _output(True, f"Entity '{entity_name}' inspected", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Runtime inspect failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_runtime_events(project_path: Path, count: int, step_frames: int, json_output: bool) -> int:
    """Return recent runtime events, optionally after a stateless headless step."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    normalized_step_frames = max(0, int(step_frames))
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        if not scene_ready:
            warnings.append("No active scene in this stateless CLI process; event bus may be empty.")
        elif normalized_step_frames > 0:
            api.play()
            api.step(normalized_step_frames)
        events = api.get_recent_events(count)
        if not events:
            warnings.append("No recent events available. The event bus may be empty or the runtime has not emitted events yet.")
        data = _runtime_response_base("runtime events", True, warnings)
        data.update({
            "scene": scene,
            "events": events,
            "count": len(events),
            "requested_count": count,
            "step_frames": normalized_step_frames,
        })
        return _output(True, f"Retrieved {len(events)} recent events", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Runtime events failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.stop()
                api.shutdown()
            except Exception:
                pass


def cmd_physics_query_aabb(
    project_path: Path,
    left: float,
    top: float,
    right: float,
    bottom: float,
    json_output: bool,
) -> int:
    """Query physics AABB hits in a stateless headless runtime process."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        data = _runtime_response_base("physics query aabb", True, warnings)
        data.update({
            "scene": scene,
            "query": {
                "left": float(left),
                "top": float(top),
                "right": float(right),
                "bottom": float(bottom),
            },
            "hits": [],
            "count": 0,
            "status_after": _runtime_status(api),
        })
        if not scene_ready:
            return _output(False, "Physics AABB query failed: no active scene", data, json_output)

        api.play()
        api.step(1)
        hits = api.query_physics_aabb(float(left), float(top), float(right), float(bottom))
        api.stop()
        data["hits"] = hits
        data["count"] = len(hits)
        data["status_after"] = _runtime_status(api)
        data["warnings"] = list(warnings)
        return _output(True, f"Physics AABB query returned {len(hits)} hits", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Physics AABB query failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.stop()
                api.shutdown()
            except Exception:
                pass


# ============================================================================
# Core Command Handlers
# ============================================================================

def cmd_capabilities(json_output: bool) -> int:
    """List all engine capabilities."""
    api = None
    try:
        api = _init_engine(Path.cwd(), read_only=True)
        registry_dict = api.get_capability_registry()
        capabilities = registry_dict.get("capabilities", [])
        data = {
            "count": len(capabilities),
            "engine_version": registry_dict.get("engine", {}).get("version", ""),
            "capabilities_schema_version": registry_dict.get("schema_version", 0),
            "capabilities": capabilities,
        }
        return _output(True, f"Found {len(capabilities)} capabilities", data, json_output)
    except Exception as exc:
        return _output(False, f"Failed to load capabilities: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def _compact_workflows_from_registry() -> List[Dict[str, Any]]:
    """Build compact recommended AI workflows from implemented registry entries."""
    registry = get_default_registry()
    selected_ids = [
        "ai:start",
        "ai:compliance",
        "introspect:doctor",
        "introspect:capabilities",
        "scene:list",
        "scene:create",
        "scene:load",
        "entity:create",
        "component:add",
        "prefab:list",
        "asset:list",
        "animator:ensure",
        "animator:state:create",
        "runtime:step",
    ]
    workflows: List[Dict[str, Any]] = []
    for capability_id in selected_ids:
        cap = registry.get(capability_id)
        if cap is None or cap.status != "implemented":
            continue
        workflows.append(
            {
                "capability_id": cap.id,
                "summary": cap.summary,
                "cli_command": cap.cli_command,
                "api_methods": cap.api_methods,
                "tags": cap.tags,
            }
        )
    return workflows


def cmd_ai_start(project_path: Path, json_output: bool) -> int:
    """Return the compact AI entrypoint contract for a project."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)

        api = _init_engine(project_path, auto_ensure_project=False, read_only=True)
        manifest = api.get_project_manifest()
        editor_state = api.get_editor_state()
        scenes = api.list_project_scenes()

        active_scene = str(editor_state.get("active_scene", "") or "").strip()
        last_scene = str(editor_state.get("last_scene", "") or "").strip()
        open_scenes = [
            str(item)
            for item in editor_state.get("open_scenes", [])
            if str(item).strip()
        ]

        data = {
            "engine": {
                "name": "MotorVideojuegosIA",
                "version": ENGINE_VERSION,
            },
            "project": manifest,
            "recommended_cli": "motor",
            "recommended_api": "EngineAPI",
            "authoring_contract": (
                "Use serialized Scene and registered components; persist authoring "
                "changes through EngineAPI/SceneManager."
            ),
            "scene_context": {
                "active_scene": active_scene,
                "last_scene": last_scene,
                "open_scenes": open_scenes,
                "detected_scene_count": len(scenes),
                "detected_scenes": [
                    {
                        "name": scene.get("name", ""),
                        "path": scene.get("path", ""),
                    }
                    for scene in scenes
                ],
            },
            "initial_commands": [
                "motor ai start --project . --json",
                "motor doctor --project . --json",
                "motor capabilities --json",
                "motor scene list --project . --json",
                "motor project info --project . --json",
            ],
            "recommended_workflows": _compact_workflows_from_registry(),
            "rules": {
                "no_external_runtime": (
                    "Do not create or use an external runtime for this project; "
                    "operate through MotorVideojuegosIA."
                ),
                "no_alternate_main_loop": (
                    "Do not deliver run_game.py or any alternate main loop as the "
                    "main game; use the official motor CLI, EngineAPI and serialized scenes."
                ),
                "use_serialized_authoring": (
                    "Scene is the persistent source of truth; authoring changes must "
                    "be represented as serialized scenes/components."
                ),
            },
            "validation": {
                "command": "motor ai compliance --project . --strict --json",
                "status": "implemented",
                "next_step": True,
            },
        }

        return _output(True, "AI start contract loaded", data, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to load AI start contract: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_ai_compliance(project_path: Path, strict: bool, json_output: bool) -> int:
    """Run read-only AI-native project compliance diagnostics."""
    api = None
    try:
        api = _init_engine(project_path, read_only=True)
        data = api.run_ai_compliance(strict=strict)
        if strict and not data.get("strict_pass", False):
            return _output(False, "AI compliance strict check failed", data, json_output)
        return _output(bool(data.get("success", False)), "AI compliance diagnostics completed", data, json_output)
    except Exception as exc:
        data = {
            "success": False,
            "native_score": 0,
            "strict_pass": False,
            "external_runtime_detected": False,
            "problems": [{"code": "compliance_error", "message": str(exc)}],
            "warnings": [],
            "recommended_next_actions": ["Fix the compliance diagnostic error and rerun the command."],
        }
        return _output(False, f"AI compliance failed: {exc}", data, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


_AI_SELF_TEST_PROFILES: Dict[str, str] = {
    "platformer": "platformer-basic",
}


def _self_test_project_manifest(name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "version": 2,
        "engine_version": ENGINE_VERSION,
        "template": "empty",
        "paths": {
            "assets": "assets",
            "levels": "levels",
            "prefabs": "prefabs",
            "scripts": "scripts",
            "settings": "settings",
            "meta": ".motor/meta",
            "build": ".motor/build",
        },
    }


def _create_self_test_project(project_path: Path) -> None:
    project_path.mkdir(parents=True, exist_ok=False)
    (project_path / "project.json").write_text(
        json.dumps(_self_test_project_manifest(project_path.name), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    for dirname in ("assets", "levels", "prefabs", "scripts", "settings", ".motor"):
        (project_path / dirname).mkdir(parents=True, exist_ok=True)


def _missing_self_test_capabilities(recipe: Dict[str, Any]) -> List[Dict[str, str]]:
    registry = get_default_registry()
    missing: List[Dict[str, str]] = []
    for capability_id in recipe.get("expected_capabilities", []):
        cap = registry.get(str(capability_id))
        if cap is None:
            missing.append({"id": str(capability_id), "reason": "not_registered"})
        elif cap.status != "implemented":
            missing.append({"id": cap.id, "reason": f"status:{cap.status}"})
    return missing


def _self_test_commands(recipe_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "id": step.get("id", ""),
            "command": step.get("command", []),
            "argv": step.get("argv", []),
            "success": bool(step.get("success", False)),
            "exit_code": step.get("exit_code"),
            "message": step.get("message", ""),
        }
        for step in recipe_result.get("steps", [])
    ]


def _self_test_validations(recipe_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    validation_ids = {"validate-platformer", "ai-compliance-strict", "runtime-step", "runtime-events"}
    validations: List[Dict[str, Any]] = []
    for step in recipe_result.get("steps", []):
        if step.get("id") not in validation_ids:
            continue
        validations.append(
            {
                "id": step.get("id", ""),
                "command": step.get("command", []),
                "success": bool(step.get("success", False)),
                "exit_code": step.get("exit_code"),
                "message": step.get("message", ""),
                "data": step.get("data", {}),
            }
        )
    return validations


def _self_test_generated_scene(workspace_path: Path, recipe_result: Dict[str, Any]) -> Dict[str, Any]:
    generated: Dict[str, Any] = {}
    for step in recipe_result.get("steps", []):
        if step.get("id") == "create-level":
            generated.update(step.get("data", {}) or {})
            break

    scene_refs = [
        str(generated.get("scene_file") or ""),
        str(generated.get("scene_path") or ""),
    ]
    scene_file = next((ref for ref in scene_refs if ref and (workspace_path / ref).exists()), "")
    if not scene_file:
        scene_file = next((ref for ref in scene_refs if ref), "")
    if scene_file:
        scene_path = workspace_path / scene_file
        generated["scene_file"] = scene_file.replace("\\", "/")
        generated["exists_before_cleanup"] = scene_path.exists()
        if scene_path.exists():
            try:
                scene = json.loads(scene_path.read_text(encoding="utf-8"))
                entities = scene.get("entities", [])
                generated["scene_name"] = scene.get("name", generated.get("scene_name", ""))
                generated["entity_count"] = len(entities) if isinstance(entities, list) else 0
                generated["entity_names"] = [
                    str(entity.get("name", ""))
                    for entity in entities
                    if isinstance(entity, dict) and entity.get("name")
                ]
            except Exception as exc:
                generated["read_error"] = str(exc)
    return generated


def _self_test_events(recipe_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for step in recipe_result.get("steps", []):
        if step.get("id") not in {"runtime-step", "runtime-events"}:
            continue
        step_events = (step.get("data", {}) or {}).get("events", [])
        if isinstance(step_events, list):
            events.extend(event for event in step_events if isinstance(event, dict))
    return events


def _self_test_warnings(recipe_result: Dict[str, Any]) -> List[Any]:
    warnings: List[Any] = []
    for step in recipe_result.get("steps", []):
        step_warnings = (step.get("data", {}) or {}).get("warnings", [])
        if isinstance(step_warnings, list):
            warnings.extend(item for item in step_warnings if str(item).strip())
    return warnings


def cmd_ai_self_test(project_path: Path, profile: str, in_place: bool, json_output: bool) -> int:
    """Run a controlled AI self-test workflow in an isolated project by default."""
    normalized_profile = str(profile or "").strip().lower()
    recipe_id = _AI_SELF_TEST_PROFILES.get(normalized_profile)
    temp_project: Optional[Path] = None
    cleanup_status: Dict[str, Any] = {
        "mode": "in_place" if in_place else "temporary",
        "removed": False,
        "skipped": bool(in_place),
        "error": "",
    }
    data: Dict[str, Any] = {
        "success": False,
        "profile": normalized_profile,
        "commands_executed": [],
        "validations": [],
        "generated_scene": {},
        "events": [],
        "cleanup_status": cleanup_status,
        "warnings": [],
    }
    error_message: Optional[str] = None

    try:
        _ensure_project(project_path)
        if recipe_id is None:
            data["warnings"].append(f"Unsupported self-test profile: {profile}")
            return _output(False, "AI self-test failed: unsupported profile", data, json_output)

        recipe = get_recipe(recipe_id)
        missing_capabilities = _missing_self_test_capabilities(recipe)
        if missing_capabilities:
            data["missing_capabilities"] = missing_capabilities
            data["warnings"].append("Required capability missing or not implemented.")
            return _output(False, "AI self-test failed: missing capability", data, json_output)

        workspace_path = project_path
        if not in_place:
            tmp_root = project_path / ".motor" / "tmp"
            tmp_root.mkdir(parents=True, exist_ok=True)
            temp_project = tmp_root / f"ai-self-test-{uuid.uuid4().hex[:12]}"
            _create_self_test_project(temp_project)
            workspace_path = temp_project
            cleanup_status["temp_project"] = str(temp_project)

        recipe_result = run_recipe(recipe_id, workspace_path)
        data["commands_executed"] = _self_test_commands(recipe_result)
        data["validations"] = _self_test_validations(recipe_result)
        data["generated_scene"] = _self_test_generated_scene(workspace_path, recipe_result)
        data["events"] = _self_test_events(recipe_result)
        data["warnings"] = _self_test_warnings(recipe_result)
        if recipe_result.get("first_failure") is not None:
            data["first_failure"] = recipe_result.get("first_failure")
        data["recipe"] = {
            "id": recipe_result.get("recipe", recipe_id),
            "version": recipe_result.get("version", ""),
        }
        data["success"] = bool(recipe_result.get("success", False))

    except ProjectNotFoundError as exc:
        data["warnings"].append(exc.message)
        error_message = exc.message
    except RecipeError as exc:
        data["warnings"].append(str(exc))
        error_message = f"AI self-test failed: {exc}"
    except Exception as exc:
        data["warnings"].append(str(exc))
        error_message = f"AI self-test failed: {exc}"
    finally:
        if temp_project is not None:
            try:
                shutil.rmtree(temp_project)
                cleanup_status["removed"] = not temp_project.exists()
            except Exception as exc:
                cleanup_status["removed"] = False
                cleanup_status["error"] = str(exc)
                data["success"] = False
            try:
                tmp_root = temp_project.parent
                if tmp_root.exists() and not any(tmp_root.iterdir()):
                    tmp_root.rmdir()
            except Exception:
                pass

    if cleanup_status.get("error"):
        return _output(False, "AI self-test failed: cleanup failed", data, json_output)
    if error_message is not None:
        return _output(False, error_message, data, json_output)
    message = "AI self-test completed" if data["success"] else "AI self-test failed"
    return _output(bool(data["success"]), message, data, json_output)


def cmd_agent_session_create(
    project_path: Path,
    permission_mode: str,
    title: str,
    provider_id: str = "fake",
    model: str = "",
    temperature: float | None = None,
    max_tokens: int | None = None,
    stream: bool = False,
    json_output: bool = False,
) -> int:
    """Create an experimental agent session."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, auto_ensure_project=False)
        result = api.create_agent_session(
            permission_mode=permission_mode,
            title=title,
            provider_id=provider_id,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )
        return _output(result["success"], result["message"], result["data"], json_output)
    except Exception as exc:
        return _output(False, f"Agent session create failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_agent_session_compact(
    project_path: Path,
    session_id: str,
    json_output: bool,
) -> int:
    """Compact an experimental agent session."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, auto_ensure_project=False)
        result = api.compact_agent_session(session_id)
        return _output(result["success"], result["message"], result["data"], json_output)
    except Exception as exc:
        return _output(False, f"Agent session compact failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_agent_session_inspect(
    project_path: Path,
    session_id: str,
    json_output: bool,
) -> int:
    """Inspect an experimental agent session without mutating it."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, auto_ensure_project=False)
        data = api.inspect_agent_session(session_id)
        return _output(True, "Agent session inspected", data, json_output)
    except Exception as exc:
        return _output(False, f"Agent session inspect failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_agent_message_send(
    project_path: Path,
    session_id: str,
    message: str,
    json_output: bool,
) -> int:
    """Send a message to an experimental agent session."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, auto_ensure_project=False)
        result = api.send_agent_message(session_id, message)
        return _output(result["success"], result["message"], result["data"], json_output)
    except Exception as exc:
        return _output(False, f"Agent message failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_agent_action_approve(
    project_path: Path,
    session_id: str,
    action_id: str,
    approved: bool,
    json_output: bool,
) -> int:
    """Approve or reject an experimental agent action."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, auto_ensure_project=False)
        result = api.approve_agent_action(session_id, action_id, approved)
        return _output(result["success"], result["message"], result["data"], json_output)
    except Exception as exc:
        return _output(False, f"Agent action failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_agent_providers_list(
    project_path: Path,
    json_output: bool,
) -> int:
    """List configured experimental agent providers."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, auto_ensure_project=False)
        data = api.list_agent_providers()
        return _output(True, "Agent providers listed", data, json_output)
    except Exception as exc:
        return _output(False, f"Agent providers list failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_agent_providers_login(
    project_path: Path,
    provider_id: str,
    api_key_stdin: bool,
    codex_chatgpt: bool,
    device_auth: bool,
    base_url: str,
    model: str,
    json_output: bool,
) -> int:
    """Store provider credentials or delegate managed Codex login."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, auto_ensure_project=False)
        if codex_chatgpt or device_auth:
            result = api.login_agent_provider(
                provider_id,
                api_key="",
                base_url=base_url,
                model=model,
                credential_source="codex_chatgpt",
                device_auth=device_auth,
            )
        else:
            if not api_key_stdin:
                raise ValueError(
                    "Use --api-key-stdin to provide credentials without exposing them in shell history, or use --codex-chatgpt/--device-auth for managed Codex login."
                )
            api_key = sys.stdin.read().strip()
            result = api.login_agent_provider(provider_id, api_key=api_key, base_url=base_url, model=model)
        return _output(result["success"], result["message"], result["data"], json_output)
    except Exception as exc:
        return _output(False, f"Agent provider login failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_agent_providers_logout(
    project_path: Path,
    provider_id: str,
    json_output: bool,
) -> int:
    """Remove a user-local provider credential."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, auto_ensure_project=False)
        result = api.logout_agent_provider(provider_id)
        return _output(result["success"], result["message"], result["data"], json_output)
    except Exception as exc:
        return _output(False, f"Agent provider logout failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_agent_providers_status(
    project_path: Path,
    provider_id: str,
    json_output: bool,
) -> int:
    """Show provider auth status without revealing credentials."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, auto_ensure_project=False)
        data = api.get_agent_provider_status(provider_id)
        return _output(True, "Agent provider status loaded", data, json_output)
    except Exception as exc:
        return _output(False, f"Agent provider status failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_agent_usage(
    project_path: Path,
    session_id: str,
    json_output: bool,
) -> int:
    """Show token/cost usage for an experimental agent session."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, auto_ensure_project=False)
        data = api.get_agent_usage(session_id)
        return _output(True, "Agent usage loaded", data, json_output)
    except Exception as exc:
        return _output(False, f"Agent usage failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_doctor(project_path: Path, json_output: bool) -> int:
    """Diagnose project health with comprehensive AI-facing checks."""
    issues: List[str] = []
    warnings: List[str] = []
    checks: Dict[str, Any] = {}

    # Check 1: Project manifest exists and is valid JSON
    manifest_path = project_path / "project.json"
    checks["project_manifest_exists"] = manifest_path.exists()
    if not manifest_path.exists():
        issues.append("project.json not found")
    else:
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            checks["project_manifest_valid"] = True
            checks["project_name"] = manifest_data.get("name", "unnamed")
            checks["project_version"] = manifest_data.get("version", 0)
            required_fields = ["name", "version", "paths"]
            missing_fields = [f for f in required_fields if f not in manifest_data]
            if missing_fields:
                warnings.append(f"project.json missing fields: {missing_fields}")
        except json.JSONDecodeError as exc:
            checks["project_manifest_valid"] = False
            issues.append(f"project.json is not valid JSON: {exc}")
        except Exception as exc:
            checks["project_manifest_valid"] = False
            issues.append(f"project.json read error: {exc}")

    # Check 2: motor_ai.json exists and is valid
    motor_ai_path = project_path / "motor_ai.json"
    checks["motor_ai_exists"] = motor_ai_path.exists()
    if not motor_ai_path.exists():
        warnings.append("motor_ai.json not found (run project migration)")
    else:
        try:
            motor_ai_data = json.loads(motor_ai_path.read_text(encoding="utf-8"))
            checks["motor_ai_valid"] = True
            checks["motor_ai_schema_version"] = motor_ai_data.get("schema_version", 0)

            # Read capability counts with backward compatibility
            # Schema v3: implemented_capabilities, planned_capabilities, capability_counts
            # Schema v1/v2: capabilities.capabilities (single list)
            schema_version = motor_ai_data.get("schema_version", 0)

            if schema_version >= 3:
                # v3: Use implemented/planned separation
                implemented_caps = motor_ai_data.get("implemented_capabilities", [])
                planned_caps = motor_ai_data.get("planned_capabilities", [])
                capability_counts = motor_ai_data.get("capability_counts", {})

                checks["motor_ai_implemented_count"] = len(implemented_caps)
                checks["motor_ai_planned_count"] = len(planned_caps)
                checks["motor_ai_capabilities_count"] = capability_counts.get(
                    "total", len(implemented_caps) + len(planned_caps)
                )

                # Validate v3 structure
                if not implemented_caps and not planned_caps:
                    warnings.append("motor_ai.json v3 has no capabilities (both lists empty)")
                if "capability_counts" not in motor_ai_data:
                    warnings.append("motor_ai.json v3 missing capability_counts")
            else:
                # v1/v2: Legacy single capabilities list
                legacy_caps = motor_ai_data.get("capabilities", {}).get("capabilities", [])
                checks["motor_ai_capabilities_count"] = len(legacy_caps)
                checks["motor_ai_implemented_count"] = len(legacy_caps)
                checks["motor_ai_planned_count"] = 0

                if not legacy_caps:
                    warnings.append("motor_ai.json has empty capabilities list")

            # Common validations
            if "engine" not in motor_ai_data:
                warnings.append("motor_ai.json missing engine section")
        except json.JSONDecodeError as exc:
            checks["motor_ai_valid"] = False
            issues.append(f"motor_ai.json is not valid JSON: {exc}")
        except Exception as exc:
            checks["motor_ai_valid"] = False
            issues.append(f"motor_ai.json read error: {exc}")

    # Check 3: START_HERE_AI.md exists
    start_here_path = project_path / "START_HERE_AI.md"
    checks["start_here_exists"] = start_here_path.exists()
    if not start_here_path.exists():
        warnings.append("START_HERE_AI.md not found (run project migration)")
    else:
        try:
            content = start_here_path.read_text(encoding="utf-8")
            checks["start_here_valid"] = len(content) > 100
            checks["start_here_size"] = len(content)
        except Exception as exc:
            checks["start_here_valid"] = False
            warnings.append(f"START_HERE_AI.md read error: {exc}")

    # Check 4: Required directories
    required_dirs = ["assets", "levels", "scripts", "settings"]
    for dir_name in required_dirs:
        dir_path = project_path / dir_name
        exists = dir_path.exists()
        checks[f"dir_{dir_name}_exists"] = exists
        if not exists:
            warnings.append(f"{dir_name}/ directory missing")

    # Check 5: Entrypoints availability
    if checks.get("project_manifest_valid"):
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            paths = manifest_data.get("paths", {})
            entrypoints = {
                "settings": paths.get("settings", "settings"),
                "assets": paths.get("assets", "assets"),
                "levels": paths.get("levels", "levels"),
            }
            for name, relative_path in entrypoints.items():
                full_path = project_path / relative_path
                checks[f"entrypoint_{name}_exists"] = full_path.exists()
                if not full_path.exists():
                    warnings.append(f"Entrypoint {name} not found at {relative_path}")
        except Exception as exc:
            warnings.append(f"Could not validate entrypoints: {exc}")

    # Check 6: Try to init engine (read-only mode - no side effects)
    api: Optional[EngineAPI] = None
    try:
        api = _init_engine(project_path, auto_ensure_project=False, read_only=True)
        checks["engine_init"] = True

        # Check 7: Can list scenes
        try:
            scenes = api.list_project_scenes()
            checks["can_list_scenes"] = True
            checks["scene_count"] = len(scenes)
        except Exception as exc:
            checks["can_list_scenes"] = False
            warnings.append(f"Cannot list scenes: {exc}")

        # Check 8: Can list assets
        try:
            assets = api.list_project_assets()
            checks["can_list_assets"] = True
            checks["asset_count"] = len(assets)
        except Exception as exc:
            checks["can_list_assets"] = False
            warnings.append(f"Cannot list assets: {exc}")

        # Check 9: Capability registry consistency
        try:
            registry = get_default_registry()
            checks["capability_registry_loaded"] = True
            checks["capability_count"] = len(registry.list_all())
            cap_ids = [cap.id for cap in registry.list_all()]
            duplicates = set([cid for cid in cap_ids if cap_ids.count(cid) > 1])
            if duplicates:
                issues.append(f"Duplicate capability IDs found: {duplicates}")
        except Exception as exc:
            checks["capability_registry_loaded"] = False
            warnings.append(f"Capability registry error: {exc}")

    except Exception as exc:
        checks["engine_init"] = False
        issues.append(f"Engine initialization failed: {exc}")
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass

    # Determine overall health
    critical_checks = [
        checks.get("project_manifest_exists", False),
        checks.get("project_manifest_valid", False),
    ]
    healthy = len(issues) == 0 and all(critical_checks)
    status = "healthy" if healthy else "unhealthy" if issues else "degraded"

    data = {
        "healthy": healthy,
        "status": status,
        "project_path": str(project_path),
        "issues": issues,
        "warnings": warnings,
        "checks": checks,
        "recommendations": [],
    }

    if not checks.get("motor_ai_exists") or not checks.get("start_here_exists"):
        data["recommendations"].append("Run 'motor project bootstrap-ai --project .' to generate AI bootstrap files")
    if warnings and not issues:
        data["recommendations"].append("Project is functional but has minor configuration issues")

    message = f"Project is {status}"
    if issues:
        message += f" ({len(issues)} issues, {len(warnings)} warnings)"
    elif warnings:
        message += f" ({len(warnings)} warnings)"

    return _output(healthy, message, data, json_output)


def cmd_project_info(project_path: Path, json_output: bool) -> int:
    """Get project information."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        manifest = api.get_project_manifest()
        editor_state = api.get_editor_state()
        recent_projects = api.list_recent_projects()

        last_scene = editor_state.get("last_scene", "")
        open_scenes = editor_state.get("open_scenes", [])

        data = {
            "project": manifest,
            "editor_state": {
                "last_scene": last_scene,
                "open_scenes_count": len(open_scenes),
                "open_scenes": open_scenes,
            },
            "recent_projects_count": len(recent_projects),
        }

        return _output(True, f"Project: {manifest.get('name', 'Unknown')}", data, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to get project info: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_scene_list(project_path: Path, json_output: bool) -> int:
    """List all scenes in the project."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        scenes = api.list_project_scenes()

        data = {
            "count": len(scenes),
            "scenes": [
                {
                    "name": scene.get("name", ""),
                    "path": scene.get("path", ""),
                }
                for scene in scenes
            ],
        }

        return _output(True, f"Found {len(scenes)} scenes", data, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to list scenes: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_scene_create(project_path: Path, name: str, json_output: bool) -> int:
    """Create a new scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        result = api.create_scene(name)

        if result.get("success"):
            return _output(True, result.get("message", "Scene created"), result.get("data"), json_output)
        else:
            return _output(False, result.get("message", "Failed to create scene"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to create scene: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_create(project_path: Path, name: str, json_output: bool) -> int:
    """Create a minimal native 2D platformer scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = create_minimal_platformer_scene(api, name)
        if result.get("success"):
            return _output(True, result.get("message", "Platformer scene created"), result.get("data"), json_output)
        return _output(False, result.get("message", "Failed to create platformer scene"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to create platformer scene: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_add_player(project_path: Path, x: float, y: float, json_output: bool) -> int:
    """Ensure a platformer Player exists in the selected scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = add_platformer_player(api, x, y)
        return _output(bool(result.get("success")), result.get("message", "Platformer player update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to add platformer player: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_add_ground(
    project_path: Path,
    from_x: float,
    to_x: float,
    y: float,
    name: str | None,
    json_output: bool,
) -> int:
    """Ensure platformer ground exists in the selected scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = add_platformer_ground(api, from_x, to_x, y, name=name)
        return _output(bool(result.get("success")), result.get("message", "Platformer ground update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to add platformer ground: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_add_platform(project_path: Path, x: float, y: float, width: float, name: str | None, json_output: bool) -> int:
    """Ensure a platformer platform exists in the selected scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = add_platformer_platform(api, x, y, width, name=name)
        return _output(bool(result.get("success")), result.get("message", "Platformer platform update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to add platformer platform: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_add_goal(project_path: Path, x: float, y: float, name: str | None, json_output: bool) -> int:
    """Ensure a platformer Goal exists in the selected scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = add_platformer_goal(api, x, y, name=name)
        return _output(bool(result.get("success")), result.get("message", "Platformer goal update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to add platformer goal: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_add_coin(project_path: Path, x: float, y: float, points: int, name: str | None, json_output: bool) -> int:
    """Ensure a platformer Coin exists in the selected scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = add_platformer_coin(api, x, y, points, name=name)
        return _output(bool(result.get("success")), result.get("message", "Platformer coin update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to add platformer coin: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_add_hazard(project_path: Path, x: float, y: float, damage: int, name: str | None, json_output: bool) -> int:
    """Ensure a platformer Hazard exists in the selected scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = add_platformer_hazard(api, x, y, damage, name=name)
        return _output(bool(result.get("success")), result.get("message", "Platformer hazard update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to add platformer hazard: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_add_respawn(project_path: Path, x: float, y: float, spawn_id: str, json_output: bool) -> int:
    """Ensure a platformer RespawnPoint exists in the selected scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = add_platformer_respawn(api, x, y, spawn_id)
        return _output(bool(result.get("success")), result.get("message", "Platformer respawn update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to add platformer respawn: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_add_moving_platform(
    project_path: Path,
    name: str,
    x: float,
    y: float,
    width: float,
    height: float,
    to_x: float,
    to_y: float,
    speed: float,
    json_output: bool,
) -> int:
    """Ensure a platformer MovingPlatform2D entity exists in the selected scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = add_platformer_moving_platform(api, name, x, y, width, height, to_x, to_y, speed)
        return _output(bool(result.get("success")), result.get("message", "Platformer moving platform update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to add platformer moving platform: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_add_enemy_patrol(
    project_path: Path,
    name: str,
    x: float,
    y: float,
    points: list[str],
    damage: int,
    speed: float,
    json_output: bool,
) -> int:
    """Ensure a platformer EnemyPatrol2D entity exists in the selected scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = add_platformer_enemy_patrol(api, name, x, y, points, damage, speed)
        return _output(bool(result.get("success")), result.get("message", "Platformer enemy patrol update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to add platformer enemy patrol: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_add_checkpoint(project_path: Path, name: str, x: float, y: float, checkpoint_id: str, json_output: bool) -> int:
    """Ensure a platformer Checkpoint2D entity exists in the selected scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = add_platformer_checkpoint(api, name, x, y, checkpoint_id)
        return _output(bool(result.get("success")), result.get("message", "Platformer checkpoint update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to add platformer checkpoint: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_add_killzone(
    project_path: Path,
    name: str,
    x: float,
    y: float,
    width: float,
    height: float,
    damage: int,
    json_output: bool,
) -> int:
    """Ensure a platformer KillZone2D entity exists in the selected scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = add_platformer_killzone(api, name, x, y, width, height, damage)
        return _output(bool(result.get("success")), result.get("message", "Platformer killzone update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to add platformer killzone: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_set_camera_follow(
    project_path: Path,
    name: str,
    target: str,
    offset_x: float,
    offset_y: float,
    dead_zone_width: float,
    dead_zone_height: float,
    zoom: float,
    json_output: bool,
) -> int:
    """Configure Camera2D follow data in the selected platformer scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = set_platformer_camera_follow(api, name, target, offset_x, offset_y, dead_zone_width, dead_zone_height, zoom)
        return _output(bool(result.get("success")), result.get("message", "Platformer camera follow update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to set platformer camera follow: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_set_bounds(
    project_path: Path,
    name: str,
    left: float,
    right: float,
    top: float,
    bottom: float,
    camera: str | None,
    json_output: bool,
) -> int:
    """Configure LevelBounds2D data in the selected platformer scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = set_platformer_bounds(api, name, left, right, top, bottom, camera=camera)
        return _output(bool(result.get("success")), result.get("message", "Platformer bounds update failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to set platformer bounds: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_game_platformer_validate(project_path: Path, json_output: bool) -> int:
    """Validate the selected platformer scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, read_only=True)
        result = validate_platformer_scene(api)
        return _output(bool(result.get("success")), result.get("message", "Platformer validation failed"), result.get("data"), json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to validate platformer scene: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_scene_load(project_path: Path, path: str, json_output: bool) -> int:
    """Load a scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        result = api.load_scene(path)

        if result.get("success"):
            return _output(True, result.get("message", "Scene loaded"), result.get("data"), json_output)
        else:
            return _output(False, result.get("message", "Failed to load scene"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to load scene: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_scene_save(project_path: Path, json_output: bool) -> int:
    """Save the active scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        # Auto-load last scene if no scene is active
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        result = api.save_scene()

        if result.get("success"):
            return _output(True, result.get("message", "Scene saved"), result.get("data"), json_output)
        else:
            return _output(False, result.get("message", "Failed to save scene"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to save scene: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_entity_create(
    project_path: Path,
    name: str,
    components: Optional[Dict[str, Dict[str, Any]]],
    json_output: bool,
) -> int:
    """Create a new entity in the active scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        # Auto-load last scene if no scene is active
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        result = api.create_entity(name, components=components)

        if result.get("success"):
            # Auto-save scene after entity creation
            api.save_scene()
            return _output(True, result.get("message", "Entity created"), result.get("data"), json_output)
        else:
            return _output(False, result.get("message", "Failed to create entity"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to create entity: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_entity_list(
    project_path: Path,
    tag: Optional[str],
    layer: Optional[str],
    active_only: bool,
    json_output: bool,
) -> int:
    """List entities in the active authoring scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        active = True if active_only else None
        entities = api.list_entities(tag=tag, layer=layer, active=active)
        filters = {
            "tag": tag,
            "layer": layer,
            "active": active,
        }
        data = {
            "entities": entities,
            "count": len(entities),
            "filters": filters,
            "scene": api.get_active_scene_info(),
        }
        return _output(True, f"Listed {len(entities)} entities", data, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to list entities: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_entity_delete(
    project_path: Path,
    name: str,
    json_output: bool,
) -> int:
    """Delete an entity from the active scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        result = api.delete_entity(name)
        if result.get("success"):
            save_result = api.save_scene()
            if not save_result.get("success"):
                return _output(False, save_result.get("message", "Scene save failed"), None, json_output)
            data = dict(result.get("data") or {})
            data["scene"] = save_result.get("data", {}).get("path", "")
            return _output(True, result.get("message", "Entity removed"), data, json_output)
        return _output(False, result.get("message", "Failed to delete entity"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to delete entity: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_component_add(
    project_path: Path,
    entity_name: str,
    component_name: str,
    data: Optional[Dict[str, Any]],
    json_output: bool,
) -> int:
    """Add a component to an entity."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        # Auto-load last scene if no scene is active
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        result = api.add_component(entity_name, component_name, data)

        if result.get("success"):
            # Auto-save scene after modification
            api.save_scene()
            return _output(True, result.get("message", "Component added"), result.get("data"), json_output)
        else:
            return _output(False, result.get("message", "Failed to add component"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to add component: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_component_edit(
    project_path: Path,
    entity_name: str,
    component_name: str,
    property_name: str,
    value: Any,
    json_output: bool,
) -> int:
    """Edit a component property on an entity."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        result = api.edit_component(entity_name, component_name, property_name, value)
        if result.get("success"):
            save_result = api.save_scene()
            if not save_result.get("success"):
                return _output(False, save_result.get("message", "Scene save failed"), None, json_output)
            data = {
                "entity": entity_name,
                "component": component_name,
                "property": property_name,
                "value": value,
                "scene": save_result.get("data", {}).get("path", ""),
            }
            return _output(True, result.get("message", "Edit applied"), data, json_output)
        return _output(False, result.get("message", "Failed to edit component"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to edit component: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_component_remove(
    project_path: Path,
    entity_name: str,
    component_name: str,
    json_output: bool,
) -> int:
    """Remove a component from an entity."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        result = api.remove_component(entity_name, component_name)
        if result.get("success"):
            save_result = api.save_scene()
            if not save_result.get("success"):
                return _output(False, save_result.get("message", "Scene save failed"), None, json_output)
            data = dict(result.get("data") or {})
            data["scene"] = save_result.get("data", {}).get("path", "")
            return _output(True, result.get("message", "Component removed"), data, json_output)
        return _output(False, result.get("message", "Failed to remove component"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to remove component: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_prefab_create(
    project_path: Path,
    entity_name: str,
    prefab_path: str,
    replace_original: bool,
    instance_name: Optional[str],
    json_output: bool,
) -> int:
    """Create a prefab from an entity in the active scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        result = api.create_prefab(
            entity_name,
            prefab_path,
            replace_original=replace_original,
            instance_name=instance_name,
        )

        if result.get("success"):
            if replace_original:
                api.save_scene()
            return _output(True, result.get("message", "Prefab created"), result.get("data"), json_output)
        return _output(False, result.get("message", "Failed to create prefab"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to create prefab: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_prefab_instantiate(
    project_path: Path,
    prefab_path: str,
    name: Optional[str],
    parent: Optional[str],
    json_output: bool,
) -> int:
    """Instantiate a prefab in the active scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        result = api.instantiate_prefab(prefab_path, name=name, parent=parent)

        if result.get("success"):
            api.save_scene()
            return _output(True, result.get("message", "Prefab instantiated"), result.get("data"), json_output)
        return _output(False, result.get("message", "Failed to instantiate prefab"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to instantiate prefab: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_prefab_unpack(project_path: Path, entity_name: str, json_output: bool) -> int:
    """Unpack a prefab instance in the active scene."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        result = api.unpack_prefab(entity_name)

        if result.get("success"):
            api.save_scene()
            return _output(True, result.get("message", "Prefab unpacked"), result.get("data"), json_output)
        return _output(False, result.get("message", "Failed to unpack prefab"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to unpack prefab: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_prefab_apply(project_path: Path, entity_name: str, json_output: bool) -> int:
    """Apply prefab overrides back to the source prefab."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        result = api.apply_prefab_overrides(entity_name)

        if result.get("success"):
            api.save_scene()
            return _output(True, result.get("message", "Prefab overrides applied"), result.get("data"), json_output)
        return _output(False, result.get("message", "Failed to apply prefab overrides"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to apply prefab overrides: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_prefab_list(project_path: Path, json_output: bool) -> int:
    """List prefabs available in the project."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        prefabs = api.list_project_prefabs()
        data = {
            "count": len(prefabs),
            "prefabs": prefabs,
        }
        return _output(True, f"Found {len(prefabs)} prefabs", data, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to list prefabs: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_assets_list(project_path: Path, search: str, json_output: bool) -> int:
    """List assets in the project."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        assets = api.list_project_assets(search=search)

        data = {
            "count": len(assets),
            "search": search,
            "assets": [
                {
                    "name": asset.get("name", ""),
                    "path": asset.get("path", ""),
                    "folder": asset.get("folder", ""),
                }
                for asset in assets
            ],
        }

        msg = f"Found {len(assets)} assets"
        if search:
            msg += f' matching "{search}"'
        return _output(True, msg, data, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to list assets: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_slices_list(project_path: Path, asset_path: str, json_output: bool) -> int:
    """List slices for an asset."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        slices = api.list_asset_slices(asset_path)

        data = {
            "asset_path": asset_path,
            "count": len(slices),
            "slices": slices,
        }

        return _output(True, f"Found {len(slices)} slices for {asset_path}", data, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to list slices: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_slices_grid(
    project_path: Path,
    asset_path: str,
    cell_width: int,
    cell_height: int,
    margin: int,
    spacing: int,
    pivot_x: float,
    pivot_y: float,
    naming_prefix: Optional[str],
    json_output: bool,
) -> int:
    """Create grid-based slices for an asset."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        result = api.create_grid_slices(
            asset_path=asset_path,
            cell_width=cell_width,
            cell_height=cell_height,
            margin=margin,
            spacing=spacing,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
        )

        if result.get("success"):
            return _output(True, result.get("message", "Grid slices created"), result.get("data"), json_output)
        else:
            return _output(False, result.get("message", "Failed to create grid slices"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to create grid slices: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_slices_auto(
    project_path: Path,
    asset_path: str,
    pivot_x: float,
    pivot_y: float,
    naming_prefix: Optional[str],
    alpha_threshold: int,
    preview_only: bool,
    json_output: bool,
) -> int:
    """Create or preview auto-detected slices for an asset."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        if preview_only:
            slices = api.preview_auto_slices(
                asset_path=asset_path,
                pivot_x=pivot_x,
                pivot_y=pivot_y,
                naming_prefix=naming_prefix,
                alpha_threshold=alpha_threshold,
            )
            data = {
                "asset_path": asset_path,
                "count": len(slices),
                "slices": slices,
                "preview": True,
            }
            return _output(True, f"Preview: {len(slices)} auto-detected slices for {asset_path}", data, json_output)
        else:
            result = api.create_auto_slices(
                asset_path=asset_path,
                pivot_x=pivot_x,
                pivot_y=pivot_y,
                naming_prefix=naming_prefix,
                alpha_threshold=alpha_threshold,
            )
            if result.get("success"):
                return _output(True, result.get("message", "Auto slices created"), result.get("data"), json_output)
            else:
                return _output(False, result.get("message", "Failed to create auto slices"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to create auto slices: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_slices_manual(
    project_path: Path,
    asset_path: str,
    slices_data: list[Dict[str, Any]],
    pivot_x: float,
    pivot_y: float,
    naming_prefix: Optional[str],
    json_output: bool,
) -> int:
    """Save manually defined slices for an asset."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        result = api.save_manual_slices(
            asset_path=asset_path,
            slices=slices_data,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            naming_prefix=naming_prefix,
        )

        if result.get("success"):
            return _output(True, result.get("message", "Manual slices saved"), result.get("data"), json_output)
        else:
            return _output(False, result.get("message", "Failed to save manual slices"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to save manual slices: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_animator_info(project_path: Path, entity_name: str, json_output: bool) -> int:
    """Get animator info for an entity."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        # Auto-load last scene if no scene is active
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        info = api.get_animator_info(entity_name)

        if info.get("exists"):
            return _output(True, f"Animator info for {entity_name}", info, json_output)
        else:
            return _output(False, f"Entity '{entity_name}' has no Animator component", None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to get animator info: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_animator_set_sheet(
    project_path: Path,
    entity_name: str,
    asset_path: str,
    json_output: bool,
) -> int:
    """Set the sprite sheet for an animator."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        # Auto-load last scene if no scene is active
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        result = api.set_animator_sprite_sheet(entity_name, asset_path)

        if result.get("success"):
            # Auto-save scene after modification
            api.save_scene()
            return _output(True, result.get("message", "Sprite sheet set"), result.get("data"), json_output)
        else:
            return _output(False, result.get("message", "Failed to set sprite sheet"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to set sprite sheet: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_animator_ensure(
    project_path: Path,
    entity_name: str,
    sprite_sheet: str,
    json_output: bool,
) -> int:
    """Ensure Animator component exists on entity with optional sheet.

    Semantics:
    - If Animator does NOT exist: creates it with the provided sheet (if any).
    - If Animator ALREADY exists and no sheet provided: succeeds (idempotent).
    - If Animator ALREADY exists and sheet provided: updates the sheet.

    This provides an idempotent "ensure exists with this sheet" operation.
    """
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        # Auto-load last scene if no scene is active
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        # Check if Animator already exists
        info = api.get_animator_info(entity_name)

        if info.get("exists"):
            # Animator exists - check if we need to update the sheet
            current_sheet = info.get("sprite_sheet", "")

            if sprite_sheet and sprite_sheet != current_sheet:
                # Update the sheet
                result = api.set_animator_sprite_sheet(entity_name, sprite_sheet)
                if result.get("success"):
                    api.save_scene()
                    return _output(
                        True,
                        f"Animator on '{entity_name}' updated with new sprite sheet",
                        {"entity": entity_name, "created": False, "updated": True, "sprite_sheet": sprite_sheet},
                        json_output
                    )
                else:
                    return _output(
                        False,
                        result.get("message", f"Failed to update sprite sheet on '{entity_name}'"),
                        None,
                        json_output
                    )

            # Animator exists and no sheet update needed
            return _output(
                True,
                f"Animator already exists on '{entity_name}'",
                {"entity": entity_name, "created": False, "updated": False, "sprite_sheet": current_sheet},
                json_output
            )

        # Animator does not exist - create it
        animator_data: Dict[str, Any] = {"enabled": True, "speed": 1.0}
        if sprite_sheet:
            animator_data["sprite_sheet"] = sprite_sheet

        result = api.add_component(entity_name, "Animator", animator_data)

        if result.get("success"):
            # Auto-save scene after adding component
            api.save_scene()
            return _output(
                True,
                result.get("message", f"Animator added to '{entity_name}'"),
                {"entity": entity_name, "created": True, "updated": False, "sprite_sheet": sprite_sheet},
                json_output
            )
        else:
            return _output(False, result.get("message", "Failed to add Animator"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to ensure animator: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_animator_upsert_state(
    project_path: Path,
    entity_name: str,
    state_name: str,
    slice_names: list[str],
    fps: float,
    loop: bool,
    set_default: bool,
    auto_create: bool,
    json_output: bool,
) -> int:
    """Create or update an animator state."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        # Auto-load last scene if no scene is active
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        # Auto-create Animator if requested and missing
        if auto_create:
            info = api.get_animator_info(entity_name)
            if not info.get("exists"):
                create_result = api.add_component(entity_name, "Animator", {"enabled": True, "speed": 1.0})
                if not create_result.get("success"):
                    return _output(
                        False,
                        create_result.get("message", "Failed to auto-create Animator"),
                        None,
                        json_output
                    )

        result = api.upsert_animator_state(
            entity_name=entity_name,
            state_name=state_name,
            slice_names=slice_names,
            fps=fps,
            loop=loop,
            on_complete=None,
            set_default=set_default,
        )

        if result.get("success"):
            # Auto-save scene after modification
            api.save_scene()
            return _output(True, result.get("message", "State upserted"), result.get("data"), json_output)
        else:
            return _output(False, result.get("message", "Failed to upsert state"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to upsert state: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_animator_remove_state(
    project_path: Path,
    entity_name: str,
    state_name: str,
    json_output: bool,
) -> int:
    """Remove an animator state."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        # Auto-load last scene if no scene is active
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        result = api.remove_animator_state(entity_name, state_name)

        if result.get("success"):
            # Auto-save scene after modification
            api.save_scene()
            return _output(True, result.get("message", "State removed"), result.get("data"), json_output)
        else:
            return _output(False, result.get("message", "Failed to remove state"), None, json_output)

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to remove state: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_project_bootstrap_ai(project_path: Path, json_output: bool) -> int:
    """Generate AI bootstrap files (motor_ai.json and START_HERE_AI.md).

    Delegates to EngineAPI public surface and AI registry.
    Uses portable relative paths for commit-friendly output.
    """
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)

        from engine.ai import get_default_registry

        api = _init_engine(project_path, auto_ensure_project=False)

        motor_ai_data = api.migrate_project_bootstrap(str(project_path))

        registry = get_default_registry()

        data = {
            "motor_ai_json": str(project_path / "motor_ai.json"),
            "start_here_md": str(project_path / "START_HERE_AI.md"),
            "registry_capabilities_count": len(registry.list_all()),
        }

        return _output(
            True,
            f"AI bootstrap files generated:\n  - {data['motor_ai_json']}\n  - {data['start_here_md']}",
            data,
            json_output
        )

    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to generate AI bootstrap files: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_recipe_list(project_path: Path, json_output: bool) -> int:
    """List bundled declarative AI recipes read-only."""
    api = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, read_only=True)
        recipes = api.list_recipes()
        data = {
            "schema_version": 1,
            "count": len(recipes),
            "recipes": recipes,
        }
        return _output(True, f"Found {len(recipes)} recipes", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except RecipeError as exc:
        return _output(False, str(exc), None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to list recipes: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_recipe_show(project_path: Path, recipe_id: str, json_output: bool) -> int:
    """Show a bundled declarative AI recipe read-only."""
    api = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, read_only=True)
        recipe = api.get_recipe(recipe_id)
        data = {
            "schema_version": 1,
            "recipe": recipe,
            "read_only": True,
        }
        return _output(True, f"Recipe shown: {recipe_id}", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except RecipeNotFoundError as exc:
        return _output(False, str(exc), None, json_output)
    except RecipeValidationError as exc:
        return _output(False, str(exc), None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to show recipe: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_recipe_run(project_path: Path, recipe_id: str, json_output: bool) -> int:
    """Run a bundled declarative AI recipe through allowlisted motor commands."""
    api = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path, read_only=False)
        data = api.run_recipe(recipe_id)
        message = "Recipe run completed" if data.get("success") else "Recipe run failed"
        return _output(bool(data.get("success")), message, data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except RecipeNotFoundError as exc:
        return _output(False, str(exc), None, json_output)
    except RecipeValidationError as exc:
        return _output(False, str(exc), None, json_output)
    except Exception as exc:
        return _output(False, f"Failed to run recipe: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


# ============================================================================
# Physics Ray Query
# ============================================================================

def cmd_physics_query_ray(
    project_path: Path,
    origin_x: float,
    origin_y: float,
    direction_x: float,
    direction_y: float,
    max_distance: float,
    json_output: bool,
) -> int:
    """Query physics raycast in a stateless headless runtime process."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        data = _runtime_response_base("physics query ray", True, warnings)
        data.update({
            "scene": scene,
            "query": {
                "origin_x": float(origin_x),
                "origin_y": float(origin_y),
                "direction_x": float(direction_x),
                "direction_y": float(direction_y),
                "max_distance": float(max_distance),
            },
            "hits": [],
            "count": 0,
            "status_after": _runtime_status(api),
        })
        if not scene_ready:
            return _output(False, "Physics ray query failed: no active scene", data, json_output)

        api.play()
        api.step(1)
        hits = api.query_physics_ray(
            float(origin_x), float(origin_y),
            float(direction_x), float(direction_y),
            float(max_distance),
        )
        api.stop()
        data["hits"] = hits
        data["count"] = len(hits)
        data["status_after"] = _runtime_status(api)
        data["warnings"] = list(warnings)
        if not hits:
            return _output(True, "No hit found", data, json_output)
        return _output(True, f"Physics ray query returned {len(hits)} hits", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Physics ray query failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.stop()
                api.shutdown()
            except Exception:
                pass


def cmd_physics_backend_list(project_path: Path, json_output: bool) -> int:
    """List physics backends in a stateless headless runtime process."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        backends = api.list_physics_backends()
        selection = api.get_physics_backend_selection()
        data = _runtime_response_base("physics backend list", True, warnings)
        data.update({
            "scene": scene,
            "backends": backends,
            "count": len(backends),
            "active_backend": selection.get("effective_backend"),
            "selection": selection,
        })
        return _output(True, f"Listed {len(backends)} physics backends", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Physics backend list failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.stop()
                api.shutdown()
            except Exception:
                pass


# ============================================================================
# Signal Commands
# ============================================================================

def cmd_signal_connect(
    project_path: Path,
    signal_name: str,
    source_entity: str,
    target_entity: str,
    json_output: bool,
) -> int:
    """Connect a signal declaratively between entities."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)

        import hashlib
        raw_id = f"{source_entity}:{signal_name}->{target_entity}"
        connection_id = hashlib.md5(raw_id.encode()).hexdigest()[:12]

        connection_data = {
            "id": connection_id,
            "signal": signal_name,
            "source": {"kind": "entity", "name": source_entity},
            "target": {"kind": "entity", "name": target_entity},
        }
        result = api.add_signal_connection(connection_data)
        if result.get("success"):
            api.save_scene()
            return _output(True, f"Signal connected: {signal_name}", result.get("data"), json_output)
        return _output(False, result.get("message", "Signal connect failed"), None, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Signal connect failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_signal_emit(
    project_path: Path,
    signal_name: str,
    entity_id: Optional[str],
    json_output: bool,
) -> int:
    """Emit a signal from an entity at runtime."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    source = entity_id or "engine"
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        if not scene_ready:
            data = _runtime_response_base("signal emit", True, warnings)
            data["scene"] = scene
            return _output(False, "Signal emit failed: no active scene", data, json_output)
        api.play()
        count = api.emit_signal(source, signal_name)
        api.stop()
        data = _runtime_response_base("signal emit", True, warnings)
        data.update({
            "scene": scene,
            "signal_name": signal_name,
            "source_entity": source,
            "connections_executed": count,
        })
        return _output(True, f"Signal '{signal_name}' emitted to {count} connections", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Signal emit failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.stop()
                api.shutdown()
            except Exception:
                pass


def cmd_signal_disconnect(
    project_path: Path,
    signal_name: str,
    source_entity: str,
    target_entity: str,
    json_output: bool,
) -> int:
    """Disconnect a signal by matching name, source, and target."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)
        connections = api.list_signal_connections_declarative()
        found_id: Optional[str] = None
        for conn in connections:
            src = conn.get("source", {})
            tgt = conn.get("target", {}) if conn.get("target") else {}
            src_name = src.get("name", "") if isinstance(src, dict) else ""
            tgt_name = tgt.get("name", "") if isinstance(tgt, dict) else ""
            if conn.get("signal") == signal_name and src_name == source_entity and tgt_name == target_entity:
                found_id = conn.get("id")
                break
        if not found_id:
            return _output(False, f"No signal connection found for {signal_name}: {source_entity} -> {target_entity}", None, json_output)
        result = api.remove_signal_connection(found_id)
        if result.get("success"):
            api.save_scene()
        return _output(
            bool(result.get("success")),
            result.get("message", "Signal disconnect failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Signal disconnect failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_signal_list(project_path: Path, json_output: bool) -> int:
    """List signal connections."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)
        declarative = api.list_signal_connections_declarative()
        data = {
            "connections": declarative,
            "count": len(declarative),
        }
        return _output(True, f"Listed {len(declarative)} signal connections", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Signal list failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


# ============================================================================
# Entity Group Commands
# ============================================================================

def cmd_entity_group_add(
    project_path: Path,
    entity_name: str,
    group_name: str,
    json_output: bool,
) -> int:
    """Add entity to a group."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)
        result = api.add_entity_to_group(entity_name, group_name)
        if result.get("success"):
            api.save_scene()
        return _output(
            bool(result.get("success")),
            result.get("message", "Group operation failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Entity group add failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_entity_group_remove(
    project_path: Path,
    entity_name: str,
    group_name: str,
    json_output: bool,
) -> int:
    """Remove entity from a group."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)
        result = api.remove_entity_from_group(entity_name, group_name)
        if result.get("success"):
            api.save_scene()
        return _output(
            bool(result.get("success")),
            result.get("message", "Group operation failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Entity group remove failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_entity_group_list(
    project_path: Path,
    group_name: Optional[str],
    json_output: bool,
) -> int:
    """List entities in a group, or list all groups."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)
        if group_name:
            entities = api.get_entities_in_group(group_name)
            data = {
                "group_name": group_name,
                "entities": entities,
                "count": len(entities),
            }
            return _output(True, f"Group '{group_name}' has {len(entities)} entities", data, json_output)
        else:
            entities = api.list_entities()
            groups: dict[str, list[str]] = {}
            for e in entities:
                for g in e.get("groups", ()):
                    if isinstance(g, str):
                        groups.setdefault(g, []).append(e.get("name", ""))
            data = {
                "groups": groups,
                "group_count": len(groups),
            }
            return _output(True, f"Found {len(groups)} groups", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Entity group list failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


# ============================================================================
# UI Commands
# ============================================================================

def cmd_ui_create_canvas(
    project_path: Path,
    name: str,
    width: int,
    height: int,
    json_output: bool,
) -> int:
    """Create a UI canvas entity."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)
        result = api.create_canvas(name=name, reference_width=width, reference_height=height)
        if result.get("success"):
            api.save_scene()
        return _output(
            bool(result.get("success")),
            result.get("message", "Canvas creation failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"UI canvas creation failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_ui_create_text(
    project_path: Path,
    text: str,
    parent: str,
    font_size: int,
    color: str,
    json_output: bool,
) -> int:
    """Create a UI text element."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)
        name = f"UIText_{uuid.uuid4().hex[:8]}"
        result = api.create_ui_text(
            name=name,
            text=text,
            parent=parent,
            font_size=font_size,
            alignment="center",
        )
        if result.get("success") and color:
            r, g, b = _parse_hex_color(color)
            api.edit_component(name, "UIText", "color", [r, g, b, 255])
        if result.get("success"):
            api.save_scene()
        return _output(
            bool(result.get("success")),
            result.get("message", "UIText creation failed"),
            result.get("data", {"entity": name}),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"UIText creation failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def _parse_hex_color(hex_str: str) -> tuple[int, int, int]:
    """Parse hex color string to (r, g, b)."""
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) >= 6:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 255, 255, 255


def cmd_ui_create_button(
    project_path: Path,
    text: str,
    parent: str,
    json_output: bool,
) -> int:
    """Create a UI button element."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)
        name = f"UIButton_{uuid.uuid4().hex[:8]}"
        result = api.create_ui_button(name=name, label=text, parent=parent)
        if result.get("success"):
            api.save_scene()
        return _output(
            bool(result.get("success")),
            result.get("message", "UIButton creation failed"),
            result.get("data", {"entity": name}),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"UIButton creation failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_ui_create_image(
    project_path: Path,
    asset_path: str,
    parent: str,
    json_output: bool,
) -> int:
    """Create a UI image element."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)
        name = f"UIImage_{uuid.uuid4().hex[:8]}"
        result = api.create_ui_image(name=name, parent=parent, sprite=asset_path)
        if result.get("success"):
            api.save_scene()
        return _output(
            bool(result.get("success")),
            result.get("message", "UIImage creation failed"),
            result.get("data", {"entity": name}),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"UIImage creation failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


# ============================================================================
# Scene Flow Commands
# ============================================================================

def cmd_scene_flow_next(project_path: Path, json_output: bool) -> int:
    """Load the next scene in the flow."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = api.load_next_scene()
        return _output(
            bool(result.get("success")),
            result.get("message", "Scene flow next failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Scene flow next failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_scene_flow_menu(project_path: Path, json_output: bool) -> int:
    """Load the menu scene in the flow."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = api.load_menu_scene()
        return _output(
            bool(result.get("success")),
            result.get("message", "Scene flow menu failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Scene flow menu failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_scene_flow_set_link(
    project_path: Path,
    source_scene: str,
    target_scene: str,
    entity_id: Optional[str],
    json_output: bool,
) -> int:
    """Set a scene link from source to target."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)
        if entity_id:
            result = api.set_scene_link(entity_id, target_scene, flow_key=source_scene)
        else:
            result = api.set_scene_connection(source_scene, target_scene)
        if result.get("success"):
            api.save_scene()
        return _output(
            bool(result.get("success")),
            result.get("message", "Scene link set"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Scene flow set-link failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


# ============================================================================
# Runtime Undo/Redo
# ============================================================================

def cmd_runtime_undo(project_path: Path, json_output: bool) -> int:
    """Undo last action."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = api.undo()
        return _output(
            bool(result.get("success")),
            result.get("message", "Undo failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Undo failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_runtime_redo(project_path: Path, json_output: bool) -> int:
    """Redo last undone action."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = api.redo()
        return _output(
            bool(result.get("success")),
            result.get("message", "Redo failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Redo failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


# ============================================================================
# Entity Parent/Child
# ============================================================================

def cmd_entity_set_parent(
    project_path: Path,
    entity_name: str,
    parent_name: str,
    json_output: bool,
) -> int:
    """Set parent for an entity."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)
        result = api.set_entity_parent(entity_name, parent_name)
        if result.get("success"):
            api.save_scene()
        return _output(
            bool(result.get("success")),
            result.get("message", "Set parent failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Set parent failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_entity_create_child(
    project_path: Path,
    parent_name: str,
    name: str,
    json_output: bool,
) -> int:
    """Create a child entity under a parent."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        success, message = _auto_load_scene(api)
        if not success:
            return _output(False, message, None, json_output)
        result = api.create_child_entity(parent_name, name)
        if result.get("success"):
            api.save_scene()
        return _output(
            bool(result.get("success")),
            result.get("message", "Child entity creation failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Child entity creation failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


# ============================================================================
# Debug Commands
# ============================================================================

def cmd_debug_profiler_reset(project_path: Path, json_output: bool) -> int:
    """Reset the profiler."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = api.reset_profiler()
        return _output(
            bool(result.get("success")),
            result.get("message", "Profiler reset failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Profiler reset failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_debug_profiler_report(project_path: Path, json_output: bool) -> int:
    """Get the profiler report."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        report = api.get_profiler_report()
        return _output(True, "Profiler report retrieved", report, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Profiler report failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_debug_overlay(
    project_path: Path,
    enabled: bool,
    json_output: bool,
) -> int:
    """Enable or disable the debug overlay."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = api.configure_debug_overlay(draw_colliders=enabled, draw_labels=enabled)
        return _output(
            bool(result.get("success")),
            result.get("message", "Debug overlay config failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Debug overlay failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


# ============================================================================
# Service Commands
# ============================================================================

def cmd_service_register(
    project_path: Path,
    name: str,
    component_name: str,
    json_output: bool,
) -> int:
    """Register a runtime service."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        result = api.register_service_runtime(name, component_name)
        return _output(
            bool(result.get("success")),
            result.get("message", "Service registration failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Service registration failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_service_get(
    project_path: Path,
    name: str,
    json_output: bool,
) -> int:
    """Get a registered runtime service."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        service = api.get_service(name)
        if service is not None:
            data = {"name": name, "available": True, "type": type(service).__name__}
            return _output(True, f"Service '{name}' found", data, json_output)
        return _output(False, f"Service '{name}' not found", {"name": name, "available": False}, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Service get failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


def cmd_service_has(
    project_path: Path,
    name: str,
    json_output: bool,
) -> int:
    """Check if a runtime service is registered."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        available = api.has_service(name)
        data = {"name": name, "available": available}
        return _output(True, f"Service '{name}': {'available' if available else 'unavailable'}", data, json_output)
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Service has failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.shutdown()
            except Exception:
                pass


# ============================================================================
# Runtime Audio Commands
# ============================================================================

def cmd_runtime_audio_play(
    project_path: Path,
    source_id: str,
    json_output: bool,
) -> int:
    """Play audio from a source entity."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        if not scene_ready:
            return _output(False, "Audio play failed: no active scene", None, json_output)
        api.play()
        result = api.play_audio(source_id)
        api.stop()
        return _output(
            bool(result.get("success")),
            result.get("message", "Audio play failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Audio play failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.stop()
                api.shutdown()
            except Exception:
                pass


def cmd_runtime_audio_stop(
    project_path: Path,
    source_id: str,
    json_output: bool,
) -> int:
    """Stop audio from a source entity."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        if not scene_ready:
            return _output(False, "Audio stop failed: no active scene", None, json_output)
        api.play()
        result = api.stop_audio(source_id)
        api.stop()
        return _output(
            bool(result.get("success")),
            result.get("message", "Audio stop failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Audio stop failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.stop()
                api.shutdown()
            except Exception:
                pass


def cmd_runtime_audio_pause(
    project_path: Path,
    source_id: str,
    json_output: bool,
) -> int:
    """Pause audio from a source entity."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        if not scene_ready:
            return _output(False, "Audio pause failed: no active scene", None, json_output)
        api.play()
        result = api.pause_audio(source_id)
        api.stop()
        return _output(
            bool(result.get("success")),
            result.get("message", "Audio pause failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Audio pause failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.stop()
                api.shutdown()
            except Exception:
                pass


def cmd_runtime_audio_resume(
    project_path: Path,
    source_id: str,
    json_output: bool,
) -> int:
    """Resume audio from a source entity."""
    api: Optional[EngineAPI] = None
    warnings: List[str] = []
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)
        scene_ready, scene = _ensure_runtime_scene(api, warnings)
        if not scene_ready:
            return _output(False, "Audio resume failed: no active scene", None, json_output)
        api.play()
        result = api.resume_audio(source_id)
        api.stop()
        return _output(
            bool(result.get("success")),
            result.get("message", "Audio resume failed"),
            result.get("data"),
            json_output,
        )
    except ProjectNotFoundError as exc:
        return _output(False, exc.message, None, json_output)
    except Exception as exc:
        return _output(False, f"Audio resume failed: {exc}", None, json_output)
    finally:
        if api is not None:
            try:
                api.stop()
                api.shutdown()
            except Exception:
                pass
