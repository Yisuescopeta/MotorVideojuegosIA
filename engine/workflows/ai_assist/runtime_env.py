from __future__ import annotations

import json
from pathlib import Path

from engine.api import EngineAPI
from engine.project.project_service import ProjectManifest, ProjectService


AI_ASSIST_STATE_DIR = ".motor/ai_assist_state"


def ai_assist_state_dir(project_root: str | Path) -> Path:
    return Path(project_root).expanduser().resolve() / AI_ASSIST_STATE_DIR


def create_isolated_project_service(
    project_root: str | Path,
    *,
    auto_ensure: bool = True,
) -> ProjectService:
    root = Path(project_root).expanduser().resolve()
    return ProjectService(
        root.as_posix(),
        global_state_dir=ai_assist_state_dir(root).as_posix(),
        auto_ensure=auto_ensure,
    )


def open_isolated_project_service(project_root: str | Path) -> ProjectService:
    root = Path(project_root).expanduser().resolve()
    service = create_isolated_project_service(root, auto_ensure=False)
    service.open_project(root)
    return service


def create_isolated_engine_api(project_root: str | Path) -> EngineAPI:
    root = Path(project_root).expanduser().resolve()
    return EngineAPI(
        project_root=root.as_posix(),
        global_state_dir=ai_assist_state_dir(root).as_posix(),
        sandbox_paths=True,
    )


def validate_project_manifest(project_root: str | Path) -> bool:
    root = Path(project_root).expanduser().resolve()
    manifest_path = root / ProjectService.PROJECT_FILE
    if not manifest_path.exists():
        return False
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            ProjectManifest.from_dict(json.load(handle))
    except Exception:
        return False
    return True
