"""
motor/cli_core.py - Core CLI command implementations for MotorVideojuegosIA

This module contains all the command handler implementations for the motor CLI.
It is designed to be independent of argument parsing and can be used programmatically.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.ai import get_default_registry
from engine.api import EngineAPI
from engine.project.project_service import ProjectService


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
    """Verify project exists and is valid."""
    manifest_path = project_path / "project.json"
    if not manifest_path.exists():
        raise ProjectNotFoundError(str(project_path))


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



# ============================================================================
# Core Command Handlers
# ============================================================================

def cmd_capabilities(json_output: bool) -> int:
    """List all engine capabilities."""
    try:
        registry = get_default_registry()
        capabilities = [
            {
                "id": cap.id,
                "summary": cap.summary,
                "mode": cap.mode,
                "status": cap.status,
                "api_methods": cap.api_methods,
                "cli_command": cap.cli_command,
                "tags": cap.tags,
            }
            for cap in registry.list_all()
        ]

        data = {
            "count": len(capabilities),
            "engine_version": registry.engine_version,
            "capabilities_schema_version": registry.schema_version,
            "capabilities": capabilities,
        }
        return _output(True, f"Found {len(capabilities)} capabilities", data, json_output)
    except Exception as exc:
        return _output(False, f"Failed to load capabilities: {exc}", None, json_output)


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
            checks["motor_ai_capabilities_count"] = len(
                motor_ai_data.get("capabilities", {}).get("capabilities", [])
            )
            if "capabilities" not in motor_ai_data:
                warnings.append("motor_ai.json missing capabilities section")
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
            scenes = api.project_service.list_project_scenes() if api.project_service else []
            checks["can_list_scenes"] = True
            checks["scene_count"] = len(scenes)
        except Exception as exc:
            checks["can_list_scenes"] = False
            warnings.append(f"Cannot list scenes: {exc}")

        # Check 8: Can list assets
        try:
            assets = api.asset_service.list_assets() if api.asset_service else []
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

        scenes = api.project_service.list_project_scenes() if api.project_service else []

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


def cmd_assets_list(project_path: Path, search: str, json_output: bool) -> int:
    """List assets in the project."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

        assets = api.asset_service.list_assets(search=search) if api.asset_service else []

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

        slices = api.list_asset_slices(asset_path) if api.asset_service else []

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

    Delegates to ProjectService for single source of truth.
    Uses portable relative paths for commit-friendly output.
    """
    try:
        _ensure_project(project_path)

        from engine.ai import get_default_registry
        from engine.project.project_service import ProjectService

        # Initialize ProjectService (without auto_ensure to avoid side effects)
        project_service = ProjectService(project_root=project_path, auto_ensure=False)

        # Delegate to the service layer - single source of truth for bootstrap structure
        # migrate_project_bootstrap loads the manifest and calls generate_ai_bootstrap
        motor_ai_data = project_service.migrate_project_bootstrap(project_path)

        # Get registry for capability count
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