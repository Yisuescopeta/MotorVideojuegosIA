from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from engine.ai import get_default_registry
from engine.api import EngineAPI
from engine.project.project_service import ProjectService
from tools.ai_workflow_cli_helpers import (
    EXIT_RUNTIME_ERROR,
    load_json_file,
    parse_verification_scenario,
    render_context_summary,
    render_validation_summary,
    render_verification_summary,
    render_workflow_summary,
    run_context_pack,
    run_validation,
    run_verification,
    run_workflow,
    write_json_output,
)
from tools.schema_cli import migrate_path, validate_path


def _validate_assets(search: str = "") -> int:
    from engine.assets.asset_service import AssetService

    service = AssetService(ProjectService(os.getcwd()))
    service.refresh_catalog()
    assets = service.list_assets(search=search)
    missing = [item["path"] for item in assets if not service.resolve_asset_path(item["path"]).exists()]
    if missing:
        for path in missing:
            print(f"[ERROR] missing asset: {path}")
        return 1
    print(f"[OK] assets validated: {len(assets)}")
    return 0


def _build_assets() -> int:
    from engine.assets.asset_service import AssetService

    service = AssetService(ProjectService(os.getcwd()))
    report = service.build_asset_artifacts()
    print(f"[OK] artifacts built: {report['artifact_count']}")
    return 0


def _run_headless(level: str, frames: int, seed: int | None, debug_dump: str = "") -> int:
    from cli.runner import CLIRunner

    args = SimpleNamespace(
        level=level,
        frames=frames,
        seed=seed,
        script="",
        golden_output="",
        golden_compare="",
        capture_every=1,
        debug_colliders=False,
        debug_labels=False,
        debug_tile_chunks=False,
        debug_camera=False,
        debug_dump=debug_dump,
    )
    CLIRunner().run(args)
    return 0


def _profile_run(scene: str, frames: int, out: str, seed: int | None, mode: str) -> int:
    from engine.api import EngineAPI

    api = EngineAPI(project_root=os.getcwd())
    api.load_level(scene)
    if seed is not None:
        api.set_seed(seed)
    api.reset_profiler(run_label=f"profile:{Path(scene).name}:{mode}")
    if mode == "play":
        api.play()
    api.step(frames=max(1, int(frames)))
    output = Path(out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(api.get_profiler_report(), indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"[OK] profile written: {output.as_posix()}")
    return 0


def _smoke(level: str, frames: int, seed: int | None, out_dir: str) -> int:
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    result = validate_path(level)
    if result != 0:
        return result
    result = _validate_assets()
    if result != 0:
        return result
    migrated_scene = out_root / "smoke_migrated_scene.json"
    result = migrate_path(level, migrated_scene.as_posix())
    if result != 0:
        return result
    result = _build_assets()
    if result != 0:
        return result
    result = _run_headless(level=level, frames=frames, seed=seed, debug_dump=(out_root / "smoke_debug_dump.json").as_posix())
    if result != 0:
        return result
    return _profile_run(
        scene=level,
        frames=frames,
        out=(out_root / "smoke_profile.json").as_posix(),
        seed=seed,
        mode="play",
    )


def _project_root(value: str) -> str:
    return Path(value or os.getcwd()).expanduser().resolve().as_posix()


def _print_or_emit(payload: dict, *, as_json: bool, out_path: str, lines: list[str]) -> None:
    rendered = write_json_output(payload, out_path)
    if as_json:
        print(rendered)
        return
    for line in lines:
        print(line)
    if out_path:
        print(f"[OK] json report written: {Path(out_path).as_posix()}")


def _emit_setup_error(*, message: str, as_json: bool, out_path: str, code: str) -> None:
    payload = {
        "status": "failed",
        "error": {
            "code": code,
            "message": message,
        },
        "exit_code": EXIT_RUNTIME_ERROR,
    }
    rendered = write_json_output(payload, out_path)
    if as_json:
        print(rendered)
        return
    print(f"[ERROR] {message}")
    if out_path:
        print(f"[OK] json report written: {Path(out_path).as_posix()}")


def _flush_buffered_stdout(buffered_stdout: io.StringIO) -> None:
    noise = buffered_stdout.getvalue()
    if noise:
        sys.stderr.write(noise)


# Standard JSON response format for new AI-facing commands
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


def _print_text(message: str, data: Any = None) -> None:
    """Print response as human-readable text."""
    print(message)
    if data:
        print(json.dumps(data, indent=2, ensure_ascii=True))


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


def _output(success: bool, message: str, data: Any, as_json: bool) -> int:
    """Output response in appropriate format and return exit code."""
    if as_json:
        _print_json(_make_response(success, message, data))
    else:
        _print_text(message, data if data else None)
    return 0 if success else 1


def _ensure_project(project_path: Path) -> None:
    """Verify project exists and is valid."""
    manifest_path = project_path / "project.json"
    if not manifest_path.exists():
        raise ProjectNotFoundError(str(project_path))


def _init_engine(project_path: Path) -> EngineAPI:
    """Initialize EngineAPI for the project."""
    try:
        return EngineAPI(
            project_root=str(project_path),
            sandbox_paths=False,
        )
    except Exception as exc:
        raise EngineInitError(str(exc))


def cmd_capabilities(json_output: bool) -> int:
    """List all engine capabilities."""
    try:
        registry = get_default_registry()
        capabilities = [
            {
                "id": cap.id,
                "summary": cap.summary,
                "mode": cap.mode,
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
            # Check required fields
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
            # Validate minimal structure
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
            checks["start_here_valid"] = len(content) > 100  # Basic sanity check
            checks["start_here_size"] = len(content)
        except Exception as exc:
            checks["start_here_valid"] = False
            warnings.append(f"START_HERE_AI.md read error: {exc}")

    # Check 4: Required directories (canonical project structure)
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

    # Check 6: Try to init engine
    api: Optional[EngineAPI] = None
    try:
        api = _init_engine(project_path)
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
            from engine.ai import get_default_registry
            registry = get_default_registry()
            checks["capability_registry_loaded"] = True
            checks["capability_count"] = len(registry.list_all())
            # Validate no duplicate IDs
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

    # Add recommendations based on findings
    if not checks.get("motor_ai_exists"):
        data["recommendations"].append("Run 'motor migrate' to generate AI bootstrap files")
    if not checks.get("start_here_exists"):
        data["recommendations"].append("Generate START_HERE_AI.md for AI assistants")
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

        # Get last scene info
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

        result = api.create_entity(name, components=components)

        if result.get("success"):
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

        result = api.add_component(entity_name, component_name, data)

        if result.get("success"):
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


def cmd_animator_info(project_path: Path, entity_name: str, json_output: bool) -> int:
    """Get animator info for an entity."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

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

        result = api.set_animator_sprite_sheet(entity_name, asset_path)

        if result.get("success"):
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


def cmd_animator_upsert_state(
    project_path: Path,
    entity_name: str,
    state_name: str,
    slice_names: list[str],
    fps: float,
    loop: bool,
    set_default: bool,
    json_output: bool,
) -> int:
    """Create or update an animator state."""
    api: Optional[EngineAPI] = None
    try:
        _ensure_project(project_path)
        api = _init_engine(project_path)

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

        result = api.remove_animator_state(entity_name, state_name)

        if result.get("success"):
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified local CLI for validation, migration, assets, headless runs, profiling, and AI discovery.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
New AI-facing commands:
  capabilities          List all engine capabilities
  doctor                Diagnose project health
  project info          Get project information
  scene list            List all scenes in project
  assets list           List assets in project

Examples:
  python -m tools.engine_cli capabilities --json
  python -m tools.engine_cli doctor --project ./my_game
  python -m tools.engine_cli project info --project . --json
  python -m tools.engine_cli scene list --project . --json
  python -m tools.engine_cli assets list --project . --search player --json
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # AI-facing discovery commands
    cap_parser = subparsers.add_parser("capabilities", help="List all engine capabilities")
    cap_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    doctor_parser = subparsers.add_parser("doctor", help="Diagnose project health")
    doctor_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    doctor_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    project_parser = subparsers.add_parser("project", help="Project operations")
    project_subparsers = project_parser.add_subparsers(dest="project_subcommand", required=True)
    proj_info_parser = project_subparsers.add_parser("info", help="Get project information")
    proj_info_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    proj_info_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    scene_parser = subparsers.add_parser("scene", help="Scene operations")
    scene_subparsers = scene_parser.add_subparsers(dest="scene_subcommand", required=True)
    scene_list_parser = scene_subparsers.add_parser("list", help="List all scenes")
    scene_list_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    scene_list_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # scene create
    scene_create_parser = scene_subparsers.add_parser("create", help="Create a new scene")
    scene_create_parser.add_argument("name", help="Scene name")
    scene_create_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    scene_create_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # entity commands
    entity_parser = subparsers.add_parser("entity", help="Entity operations")
    entity_subparsers = entity_parser.add_subparsers(dest="entity_subcommand", required=True)

    # entity create
    entity_create_parser = entity_subparsers.add_parser("create", help="Create a new entity")
    entity_create_parser.add_argument("name", help="Entity name")
    entity_create_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    entity_create_parser.add_argument("--components", default=None, help="Components JSON (e.g., '{Transform:{x:100}}')")
    entity_create_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # component commands
    component_parser = subparsers.add_parser("component", help="Component operations")
    component_subparsers = component_parser.add_subparsers(dest="component_subcommand", required=True)

    # component add
    component_add_parser = component_subparsers.add_parser("add", help="Add a component to an entity")
    component_add_parser.add_argument("entity", help="Entity name")
    component_add_parser.add_argument("component", help="Component name")
    component_add_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    component_add_parser.add_argument("--data", default=None, help="Component data JSON")
    component_add_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # animator commands
    animator_parser = subparsers.add_parser("animator", help="Animator operations")
    animator_subparsers = animator_parser.add_subparsers(dest="animator_subcommand", required=True)

    # animator info
    animator_info_parser = animator_subparsers.add_parser("info", help="Get animator info for an entity")
    animator_info_parser.add_argument("entity", help="Entity name")
    animator_info_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    animator_info_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # animator set-sheet
    animator_sheet_parser = animator_subparsers.add_parser("set-sheet", help="Set sprite sheet for animator")
    animator_sheet_parser.add_argument("entity", help="Entity name")
    animator_sheet_parser.add_argument("asset", help="Asset path")
    animator_sheet_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    animator_sheet_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # animator upsert-state
    animator_upsert_parser = animator_subparsers.add_parser("upsert-state", help="Create or update an animator state")
    animator_upsert_parser.add_argument("entity", help="Entity name")
    animator_upsert_parser.add_argument("state", help="State name")
    animator_upsert_parser.add_argument("--slices", required=True, help="Comma-separated slice names")
    animator_upsert_parser.add_argument("--fps", type=float, default=8.0, help="Frames per second")
    animator_upsert_parser.add_argument("--loop", action="store_true", default=True, help="Loop animation")
    animator_upsert_parser.add_argument("--set-default", action="store_true", help="Set as default state")
    animator_upsert_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    animator_upsert_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # animator remove-state
    animator_remove_parser = animator_subparsers.add_parser("remove-state", help="Remove an animator state")
    animator_remove_parser.add_argument("entity", help="Entity name")
    animator_remove_parser.add_argument("state", help="State name")
    animator_remove_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    animator_remove_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    assets_parser = subparsers.add_parser("assets", help="Asset operations")
    assets_subparsers = assets_parser.add_subparsers(dest="assets_subcommand", required=True)

    assets_list_parser = assets_subparsers.add_parser("list", help="List assets")
    assets_list_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    assets_list_parser.add_argument("--search", default="", help="Search filter for asset names")
    assets_list_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # assets slices subcommands
    assets_slices_parser = assets_subparsers.add_parser("slices", help="Slice operations")
    assets_slices_subparsers = assets_slices_parser.add_subparsers(dest="slices_subcommand", required=True)

    # slices list
    slices_list_parser = assets_slices_subparsers.add_parser("list", help="List slices for an asset")
    slices_list_parser.add_argument("asset", help="Asset path")
    slices_list_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    slices_list_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # slices grid
    slices_grid_parser = assets_slices_subparsers.add_parser("grid", help="Create grid-based slices")
    slices_grid_parser.add_argument("asset", help="Asset path")
    slices_grid_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    slices_grid_parser.add_argument("--cell-width", type=int, required=True, help="Cell width in pixels")
    slices_grid_parser.add_argument("--cell-height", type=int, required=True, help="Cell height in pixels")
    slices_grid_parser.add_argument("--margin", type=int, default=0, help="Margin in pixels")
    slices_grid_parser.add_argument("--spacing", type=int, default=0, help="Spacing between cells")
    slices_grid_parser.add_argument("--pivot-x", type=float, default=0.5, help="Pivot X (0-1)")
    slices_grid_parser.add_argument("--pivot-y", type=float, default=0.5, help="Pivot Y (0-1)")
    slices_grid_parser.add_argument("--naming-prefix", default=None, help="Naming prefix for slices")
    slices_grid_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # slices auto
    slices_auto_parser = assets_slices_subparsers.add_parser("auto", help="Auto-detect and create slices")
    slices_auto_parser.add_argument("asset", help="Asset path")
    slices_auto_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    slices_auto_parser.add_argument("--pivot-x", type=float, default=0.5, help="Pivot X (0-1)")
    slices_auto_parser.add_argument("--pivot-y", type=float, default=0.5, help="Pivot Y (0-1)")
    slices_auto_parser.add_argument("--naming-prefix", default=None, help="Naming prefix for slices")
    slices_auto_parser.add_argument("--alpha-threshold", type=int, default=1, help="Alpha threshold (0-255)")
    slices_auto_parser.add_argument("--preview", action="store_true", help="Preview only, don't save")
    slices_auto_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # slices manual
    slices_manual_parser = assets_slices_subparsers.add_parser("manual", help="Save manual slices")
    slices_manual_parser.add_argument("asset", help="Asset path")
    slices_manual_parser.add_argument("--project", dest="project_root", default=".", help="Path to project directory")
    slices_manual_parser.add_argument("--slices", required=True, help="Slices JSON string or path to JSON file")
    slices_manual_parser.add_argument("--pivot-x", type=float, default=0.5, help="Pivot X (0-1)")
    slices_manual_parser.add_argument("--pivot-y", type=float, default=0.5, help="Pivot Y (0-1)")
    slices_manual_parser.add_argument("--naming-prefix", default=None, help="Naming prefix for slices")
    slices_manual_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    validate_parser = subparsers.add_parser("validate", help="Validate scenes, assets, or both")
    validate_parser.add_argument("--target", choices=("scene", "assets", "all"), default="all")
    validate_parser.add_argument("--path", default="levels/demo_level.json")
    validate_parser.add_argument("--search", default="")

    migrate_parser = subparsers.add_parser("migrate", help="Migrate a scene or prefab payload")
    migrate_parser.add_argument("path")
    migrate_parser.add_argument("--output", required=True)

    build_assets_parser = subparsers.add_parser("build-assets", help="Build deterministic asset artifacts")
    build_assets_parser.add_argument("--bundle", action="store_true", help="Also create a content bundle")

    run_parser = subparsers.add_parser("run-headless", help="Execute a scene headlessly for N frames")
    run_parser.add_argument("scene")
    run_parser.add_argument("--frames", type=int, default=60)
    run_parser.add_argument("--seed", type=int, default=None)
    run_parser.add_argument("--debug-dump", default="")

    profile_parser = subparsers.add_parser("profile-run", help="Run a scene and export a versioned profiler report")
    profile_parser.add_argument("scene")
    profile_parser.add_argument("--frames", type=int, default=600)
    profile_parser.add_argument("--out", required=True)
    profile_parser.add_argument("--seed", type=int, default=None)
    profile_parser.add_argument("--mode", choices=("play", "edit"), default="play")

    smoke_parser = subparsers.add_parser("smoke", help="Run validate, migrate, build-assets, run-headless, and profile-run in order")
    smoke_parser.add_argument("--scene", default="levels/demo_level.json")
    smoke_parser.add_argument("--frames", type=int, default=5)
    smoke_parser.add_argument("--seed", type=int, default=123)
    smoke_parser.add_argument("--out-dir", default="artifacts/cli_smoke")

    ai_context_parser = subparsers.add_parser("ai-context", help="Generate the AI-assisted context pack")
    ai_context_parser.add_argument("--project-root", default="")
    ai_context_parser.add_argument("--json", action="store_true")

    ai_validate_parser = subparsers.add_parser("ai-validate", help="Run structured validation for AI-assisted workflows")
    ai_validate_parser.add_argument(
        "--target",
        choices=("active-scene", "scene-file", "prefab-file", "scene-transitions", "project"),
        required=True,
    )
    ai_validate_parser.add_argument("--path", default="")
    ai_validate_parser.add_argument("--project-root", default="")
    ai_validate_parser.add_argument("--json", action="store_true")

    ai_verify_parser = subparsers.add_parser("ai-verify", help="Run structured headless verification")
    ai_verify_parser.add_argument("--scenario", required=True)
    ai_verify_parser.add_argument("--project-root", default="")
    ai_verify_parser.add_argument("--json", action="store_true")
    ai_verify_parser.add_argument("--out", default="")

    ai_workflow_parser = subparsers.add_parser("ai-workflow", help="Run a thin AI-assisted workflow sequence")
    ai_workflow_parser.add_argument("--spec", required=True)
    ai_workflow_parser.add_argument("--project-root", default="")
    ai_workflow_parser.add_argument("--json", action="store_true")
    ai_workflow_parser.add_argument("--out", default="")

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Handle new AI-facing discovery commands
    if args.command == "capabilities":
        return cmd_capabilities(json_output=args.json)

    if args.command == "doctor":
        return cmd_doctor(
            project_path=Path(args.project_root).resolve(),
            json_output=args.json,
        )

    if args.command == "project":
        if args.project_subcommand == "info":
            return cmd_project_info(
                project_path=Path(args.project_root).resolve(),
                json_output=args.json,
            )
        return 1

    if args.command == "scene":
        if args.scene_subcommand == "list":
            return cmd_scene_list(
                project_path=Path(args.project_root).resolve(),
                json_output=args.json,
            )
        if args.scene_subcommand == "create":
            return cmd_scene_create(
                project_path=Path(args.project_root).resolve(),
                name=args.name,
                json_output=args.json,
            )
        return 1

    if args.command == "entity":
        if args.entity_subcommand == "create":
            components = None
            if args.components:
                components = json.loads(args.components)
            return cmd_entity_create(
                project_path=Path(args.project_root).resolve(),
                name=args.name,
                components=components,
                json_output=args.json,
            )
        return 1

    if args.command == "component":
        if args.component_subcommand == "add":
            data = None
            if args.data:
                data = json.loads(args.data)
            return cmd_component_add(
                project_path=Path(args.project_root).resolve(),
                entity_name=args.entity,
                component_name=args.component,
                data=data,
                json_output=args.json,
            )
        return 1

    if args.command == "animator":
        if args.animator_subcommand == "info":
            return cmd_animator_info(
                project_path=Path(args.project_root).resolve(),
                entity_name=args.entity,
                json_output=args.json,
            )
        if args.animator_subcommand == "set-sheet":
            return cmd_animator_set_sheet(
                project_path=Path(args.project_root).resolve(),
                entity_name=args.entity,
                asset_path=args.asset,
                json_output=args.json,
            )
        if args.animator_subcommand == "upsert-state":
            slice_names = [s.strip() for s in args.slices.split(",") if s.strip()]
            return cmd_animator_upsert_state(
                project_path=Path(args.project_root).resolve(),
                entity_name=args.entity,
                state_name=args.state,
                slice_names=slice_names,
                fps=args.fps,
                loop=args.loop,
                set_default=args.set_default,
                json_output=args.json,
            )
        if args.animator_subcommand == "remove-state":
            return cmd_animator_remove_state(
                project_path=Path(args.project_root).resolve(),
                entity_name=args.entity,
                state_name=args.state,
                json_output=args.json,
            )
        return 1

    if args.command == "assets":
        if args.assets_subcommand == "list":
            return cmd_assets_list(
                project_path=Path(args.project_root).resolve(),
                search=args.search,
                json_output=args.json,
            )
        if args.assets_subcommand == "slices":
            if args.slices_subcommand == "list":
                return cmd_slices_list(
                    project_path=Path(args.project_root).resolve(),
                    asset_path=args.asset,
                    json_output=args.json,
                )
            if args.slices_subcommand == "grid":
                return cmd_slices_grid(
                    project_path=Path(args.project_root).resolve(),
                    asset_path=args.asset,
                    cell_width=args.cell_width,
                    cell_height=args.cell_height,
                    margin=args.margin,
                    spacing=args.spacing,
                    pivot_x=args.pivot_x,
                    pivot_y=args.pivot_y,
                    naming_prefix=args.naming_prefix,
                    json_output=args.json,
                )
            if args.slices_subcommand == "auto":
                return cmd_slices_auto(
                    project_path=Path(args.project_root).resolve(),
                    asset_path=args.asset,
                    pivot_x=args.pivot_x,
                    pivot_y=args.pivot_y,
                    naming_prefix=args.naming_prefix,
                    alpha_threshold=args.alpha_threshold,
                    preview_only=args.preview,
                    json_output=args.json,
                )
            if args.slices_subcommand == "manual":
                # Parse slices from JSON string or file
                slices_input = args.slices
                if slices_input.startswith("[") or slices_input.startswith("{"):
                    slices_data = json.loads(slices_input)
                else:
                    # Assume it's a file path
                    slices_file = Path(slices_input)
                    if not slices_file.exists():
                        # Try relative to project root
                        slices_file = Path(args.project_root) / slices_input
                    slices_data = json.loads(slices_file.read_text(encoding="utf-8"))
                
                # Handle both {slices: [...]} and [...] formats
                if isinstance(slices_data, dict) and "slices" in slices_data:
                    slices_data = slices_data["slices"]
                
                return cmd_slices_manual(
                    project_path=Path(args.project_root).resolve(),
                    asset_path=args.asset,
                    slices_data=slices_data,
                    pivot_x=args.pivot_x,
                    pivot_y=args.pivot_y,
                    naming_prefix=args.naming_prefix,
                    json_output=args.json,
                )
            return 1
        return 1

    if args.command == "validate":
        if args.target == "scene":
            return validate_path(args.path)
        if args.target == "assets":
            return _validate_assets(args.search)
        scene_result = validate_path(args.path)
        if scene_result != 0:
            return scene_result
        return _validate_assets(args.search)
    if args.command == "migrate":
        return migrate_path(args.path, args.output)
    if args.command == "build-assets":
        result = _build_assets()
        if result != 0 or not args.bundle:
            return result
        from engine.assets.asset_service import AssetService

        service = AssetService(ProjectService(os.getcwd()))
        report = service.create_bundle()
        print(f"[OK] bundle created: {report['bundle_path']}")
        return 0
    if args.command == "run-headless":
        return _run_headless(args.scene, args.frames, args.seed, args.debug_dump)
    if args.command == "profile-run":
        return _profile_run(args.scene, args.frames, args.out, args.seed, args.mode)
    if args.command == "smoke":
        return _smoke(args.scene, args.frames, args.seed, args.out_dir)
    if args.command == "ai-context":
        if not args.json:
            try:
                payload = run_context_pack(_project_root(args.project_root))
                _print_or_emit(payload, as_json=False, out_path="", lines=render_context_summary(payload))
                return 0
            except Exception as exc:
                _emit_setup_error(
                    message=f"context generation failed: {exc}",
                    as_json=False,
                    out_path="",
                    code="context.setup_failed",
                )
                return EXIT_RUNTIME_ERROR

        buffered_stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffered_stdout):
                payload = run_context_pack(_project_root(args.project_root))
            _flush_buffered_stdout(buffered_stdout)
            _print_or_emit(payload, as_json=True, out_path="", lines=render_context_summary(payload))
            return 0
        except Exception as exc:
            _flush_buffered_stdout(buffered_stdout)
            _emit_setup_error(
                message=f"context generation failed: {exc}",
                as_json=True,
                out_path="",
                code="context.setup_failed",
            )
            return EXIT_RUNTIME_ERROR
    if args.command == "ai-validate":
        if not args.json:
            try:
                exit_code, payload = run_validation(
                    project_root=_project_root(args.project_root),
                    target=args.target,
                    path=args.path,
                )
                _print_or_emit(payload, as_json=False, out_path="", lines=render_validation_summary(payload))
                return exit_code
            except Exception as exc:
                _emit_setup_error(
                    message=f"validation setup failed: {exc}",
                    as_json=False,
                    out_path="",
                    code="validation.setup_failed",
                )
                return EXIT_RUNTIME_ERROR

        buffered_stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffered_stdout):
                exit_code, payload = run_validation(
                    project_root=_project_root(args.project_root),
                    target=args.target,
                    path=args.path,
                )
            _flush_buffered_stdout(buffered_stdout)
            _print_or_emit(payload, as_json=True, out_path="", lines=render_validation_summary(payload))
            return exit_code
        except Exception as exc:
            _flush_buffered_stdout(buffered_stdout)
            _emit_setup_error(
                message=f"validation setup failed: {exc}",
                as_json=True,
                out_path="",
                code="validation.setup_failed",
            )
            return EXIT_RUNTIME_ERROR
    if args.command == "ai-verify":
        if not args.json:
            try:
                scenario_data = load_json_file(args.scenario)
                scenario = parse_verification_scenario(
                    scenario_data,
                    default_project_root=_project_root(args.project_root),
                )
                exit_code, payload = run_verification(scenario)
                _print_or_emit(payload, as_json=False, out_path=args.out, lines=render_verification_summary(payload))
                return exit_code
            except Exception as exc:
                _emit_setup_error(
                    message=f"verification setup failed: {exc}",
                    as_json=False,
                    out_path=args.out,
                    code="verification.setup_failed",
                )
                return EXIT_RUNTIME_ERROR

        buffered_stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffered_stdout):
                scenario_data = load_json_file(args.scenario)
                scenario = parse_verification_scenario(
                    scenario_data,
                    default_project_root=_project_root(args.project_root),
                )
                exit_code, payload = run_verification(scenario)
            _flush_buffered_stdout(buffered_stdout)
            _print_or_emit(payload, as_json=True, out_path=args.out, lines=render_verification_summary(payload))
            return exit_code
        except Exception as exc:
            _flush_buffered_stdout(buffered_stdout)
            _emit_setup_error(
                message=f"verification setup failed: {exc}",
                as_json=True,
                out_path=args.out,
                code="verification.setup_failed",
            )
            return EXIT_RUNTIME_ERROR
    if args.command == "ai-workflow":
        if not args.json:
            try:
                spec = load_json_file(args.spec)
                project_root = _project_root(args.project_root or str(spec.get("project_root", "") or os.getcwd()))
                exit_code, payload = run_workflow(spec, project_root=project_root)
                _print_or_emit(payload, as_json=False, out_path=args.out, lines=render_workflow_summary(payload))
                return exit_code
            except Exception as exc:
                _emit_setup_error(
                    message=f"workflow setup failed: {exc}",
                    as_json=False,
                    out_path=args.out,
                    code="workflow.setup_failed",
                )
                return EXIT_RUNTIME_ERROR

        buffered_stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffered_stdout):
                spec = load_json_file(args.spec)
                project_root = _project_root(args.project_root or str(spec.get("project_root", "") or os.getcwd()))
                exit_code, payload = run_workflow(spec, project_root=project_root)
            _flush_buffered_stdout(buffered_stdout)
            _print_or_emit(payload, as_json=True, out_path=args.out, lines=render_workflow_summary(payload))
            return exit_code
        except Exception as exc:
            _flush_buffered_stdout(buffered_stdout)
            _emit_setup_error(
                message=f"workflow setup failed: {exc}",
                as_json=True,
                out_path=args.out,
                code="workflow.setup_failed",
            )
            return EXIT_RUNTIME_ERROR
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
