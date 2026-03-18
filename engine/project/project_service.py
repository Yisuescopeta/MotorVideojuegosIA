"""
engine/project/project_service.py - Gestion serializable de proyectos
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProjectManifest:
    """Manifiesto serializable del proyecto activo."""

    DEFAULT_PATHS = {
        "assets": "assets",
        "levels": "levels",
        "prefabs": "prefabs",
        "scripts": "scripts",
        "meta": ".motor/meta",
    }

    name: str
    version: int
    paths: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "paths": dict(self.paths),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectManifest":
        if not isinstance(data, dict):
            raise ValueError("Project manifest must be a JSON object")

        raw_paths = data.get("paths", {})
        if raw_paths is None:
            raw_paths = {}
        if not isinstance(raw_paths, dict):
            raise ValueError("Project manifest paths must be an object")

        try:
            version = int(data.get("version", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("Project manifest version must be an integer") from exc

        name = str(data.get("name", "")).strip() or "Untitled Project"
        paths = {
            key: str(raw_paths.get(key, default)).strip().replace("\\", "/") or default
            for key, default in cls.DEFAULT_PATHS.items()
        }
        return cls(name=name, version=version, paths=paths)


class ProjectService:
    """Resuelve proyecto activo, paths, recientes y estado local del editor."""

    GLOBAL_DIR_NAME = ".motorvideojuegosia"
    RECENTS_FILE_NAME = "recent_projects.json"
    PROJECT_FILE = "project.json"
    PROJECT_STATE_DIR = ".motor"
    EDITOR_STATE_FILE = "editor_state.json"
    RECENTS_LIMIT = 10

    def __init__(
        self,
        project_root: str | os.PathLike[str] = ".",
        global_state_dir: str | os.PathLike[str] | None = None,
        auto_ensure: bool = True,
    ) -> None:
        self._project_root = Path(project_root).resolve()
        self._manifest: ProjectManifest | None = None
        self._global_dir = self._resolve_global_dir(global_state_dir)
        self._recents_file = self._global_dir / self.RECENTS_FILE_NAME
        self._ensure_global_storage()
        if auto_ensure:
            self.ensure_project(self._project_root)

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def manifest(self) -> ProjectManifest:
        if self._manifest is None:
            raise RuntimeError("Project manifest not loaded")
        return self._manifest

    @property
    def has_project(self) -> bool:
        return self._manifest is not None

    @property
    def project_name(self) -> str:
        return self.manifest.name

    @property
    def global_state_dir(self) -> Path:
        return self._global_dir

    def ensure_project(self, project_root: str | os.PathLike[str] | None = None) -> ProjectManifest:
        root = Path(project_root).resolve() if project_root is not None else self._project_root
        root.mkdir(parents=True, exist_ok=True)
        manifest_path = root / self.PROJECT_FILE
        if not manifest_path.exists():
            manifest = ProjectManifest(
                name=root.name or "MotorVideojuegosIA Project",
                version=1,
                paths=dict(ProjectManifest.DEFAULT_PATHS),
            )
            self._write_json(manifest_path, manifest.to_dict())
        manifest = self._load_manifest(manifest_path)
        self._project_root = root
        self._manifest = manifest
        self._ensure_project_layout()
        self.record_recent_project()
        return manifest

    def create_project(
        self,
        project_root: str | os.PathLike[str],
        name: str | None = None,
    ) -> ProjectManifest:
        root = Path(project_root).resolve()
        manifest = self.ensure_project(root)
        if name is not None and name.strip():
            custom_manifest = ProjectManifest(
                name=name.strip(),
                version=manifest.version,
                paths=dict(manifest.paths),
            )
            self._write_json(root / self.PROJECT_FILE, custom_manifest.to_dict())
            self._manifest = custom_manifest
            manifest = custom_manifest
            self.record_recent_project()
        return manifest

    def clear_active_project(self) -> None:
        self._manifest = None

    def open_project(self, project_root: str | os.PathLike[str]) -> ProjectManifest:
        root = Path(project_root).resolve()
        manifest_path = root / self.PROJECT_FILE
        if not manifest_path.exists():
            raise FileNotFoundError(f"project.json not found in {root}")
        manifest = self._load_manifest(manifest_path)
        self._project_root = root
        self._manifest = manifest
        self._ensure_project_layout()
        self.record_recent_project()
        return manifest

    def validate_project(self, project_root: str | os.PathLike[str]) -> bool:
        try:
            manifest_path = Path(project_root).resolve() / self.PROJECT_FILE
            if not manifest_path.exists():
                return False
            self._load_manifest(manifest_path)
            return True
        except Exception:
            return False

    def get_manifest_path(self) -> Path:
        return self._project_root / self.PROJECT_FILE

    def get_recent_projects_path(self) -> Path:
        return self._recents_file

    def get_editor_state_path(self) -> Path:
        return self._get_editor_state_path()

    def get_project_summary(self) -> Dict[str, Any]:
        return {
            "name": self.project_name,
            "root": self.project_root.as_posix(),
            "manifest_path": self.get_manifest_path().as_posix(),
            "paths": dict(self.manifest.paths),
        }

    def get_project_path(self, key: str) -> Path:
        relative = self.manifest.paths.get(key, key)
        return (self._project_root / relative).resolve()

    def resolve_path(self, path: str | os.PathLike[str]) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return (self._project_root / candidate).resolve()

    def to_relative_path(self, path: str | os.PathLike[str]) -> str:
        if not path:
            return ""
        candidate = self.resolve_path(path)
        try:
            return candidate.relative_to(self._project_root).as_posix()
        except ValueError:
            return candidate.as_posix()

    def load_editor_state(self) -> Dict[str, Any]:
        state_path = self._get_editor_state_path()
        if not state_path.exists():
            return self._default_editor_state()
        try:
            with state_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return self._default_editor_state()
        return self._normalize_editor_state(data)

    def save_editor_state(self, data: Dict[str, Any]) -> None:
        state_path = self._get_editor_state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json(state_path, self._normalize_editor_state(data))

    def set_last_scene(self, path: str) -> None:
        state = self.load_editor_state()
        state["last_scene"] = self.to_relative_path(path) if path else ""
        self.save_editor_state(state)

    def get_last_scene(self) -> str:
        return str(self.load_editor_state().get("last_scene", ""))

    def set_preference(self, key: str, value: Any) -> None:
        state = self.load_editor_state()
        preferences = state.setdefault("preferences", {})
        preferences[str(key)] = value
        self.save_editor_state(state)

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self.load_editor_state().get("preferences", {}).get(key, default)

    def push_recent_asset(self, category: str, asset_path: str, limit: int = 8) -> None:
        if not asset_path:
            return
        state = self.load_editor_state()
        rel_path = self.to_relative_path(asset_path)
        recent_assets = state.setdefault("recent_assets", {})
        items = [item for item in recent_assets.get(category, []) if item != rel_path]
        items.insert(0, rel_path)
        recent_assets[category] = items[:limit]
        self.save_editor_state(state)

    def get_recent_assets(self, category: str) -> List[str]:
        state = self.load_editor_state()
        return list(state.get("recent_assets", {}).get(category, []))

    def list_recent_projects(self) -> List[Dict[str, Any]]:
        if not self._recents_file.exists():
            return []
        try:
            with self._recents_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return []

        items = data.get("projects", [])
        if not isinstance(items, list):
            return []

        result: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            path_value = str(item.get("path", "")).strip()
            if not path_value:
                continue
            root = Path(path_value).expanduser()
            manifest_path = root / self.PROJECT_FILE
            if not root.exists() or not manifest_path.exists():
                continue
            try:
                manifest = self._load_manifest(manifest_path)
            except Exception:
                continue
            result.append(
                {
                    "name": str(item.get("name", "")).strip() or manifest.name,
                    "path": root.resolve().as_posix(),
                    "manifest_path": manifest_path.resolve().as_posix(),
                    "last_opened_utc": str(item.get("last_opened_utc", "")),
                }
            )
        return result[: self.RECENTS_LIMIT]

    def record_recent_project(self) -> None:
        projects = self.list_recent_projects()
        entry = {
            "name": self.project_name,
            "path": self.project_root.as_posix(),
            "manifest_path": self.get_manifest_path().as_posix(),
            "last_opened_utc": datetime.now(timezone.utc).isoformat(),
        }
        projects = [item for item in projects if item.get("path") != entry["path"]]
        projects.insert(0, entry)
        self._write_json(self._recents_file, {"projects": projects[: self.RECENTS_LIMIT]})

    def list_assets(
        self,
        search: str = "",
        extensions: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        assets_root = self.get_project_path("assets")
        if not assets_root.exists():
            return []
        search_value = search.lower().strip()
        allowed = {ext.lower() for ext in extensions or [".png", ".jpg", ".jpeg", ".bmp"]}
        result: List[Dict[str, Any]] = []
        for path in assets_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in allowed:
                continue
            rel = path.relative_to(self._project_root).as_posix()
            if search_value and search_value not in rel.lower():
                continue
            result.append(
                {
                    "name": path.name,
                    "path": rel,
                    "absolute_path": path.as_posix(),
                    "folder": path.parent.relative_to(self._project_root).as_posix(),
                }
            )
        result.sort(key=lambda item: item["path"])
        return result

    def clear_recent_projects(self) -> None:
        self._write_json(self._recents_file, {"projects": []})

    def _ensure_global_storage(self) -> None:
        self._global_dir.mkdir(parents=True, exist_ok=True)
        if not self._recents_file.exists():
            self._write_json(self._recents_file, {"projects": []})

    def _ensure_project_layout(self) -> None:
        for key in ("assets", "levels", "prefabs", "scripts", "meta"):
            self.get_project_path(key).mkdir(parents=True, exist_ok=True)
        state_path = self._get_editor_state_path()
        if not state_path.exists():
            self.save_editor_state(self._default_editor_state())

    def _load_manifest(self, manifest_path: Path) -> ProjectManifest:
        with manifest_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return ProjectManifest.from_dict(data)

    def _get_editor_state_path(self) -> Path:
        return self._project_root / self.PROJECT_STATE_DIR / self.EDITOR_STATE_FILE

    def _default_editor_state(self) -> Dict[str, Any]:
        return {
            "recent_assets": {},
            "last_scene": "",
            "active_ai_session_id": "",
            "preferences": {},
        }

    def _normalize_editor_state(self, data: Dict[str, Any]) -> Dict[str, Any]:
        state = self._default_editor_state()
        if not isinstance(data, dict):
            return state

        raw_recent_assets = data.get("recent_assets", {})
        if isinstance(raw_recent_assets, dict):
            normalized_assets: Dict[str, List[str]] = {}
            for category, items in raw_recent_assets.items():
                if isinstance(items, list):
                    normalized_assets[str(category)] = [str(item) for item in items if str(item).strip()]
            state["recent_assets"] = normalized_assets

        last_scene = data.get("last_scene", "")
        state["last_scene"] = str(last_scene) if last_scene else ""

        active_ai_session_id = data.get("active_ai_session_id", "")
        state["active_ai_session_id"] = str(active_ai_session_id) if active_ai_session_id else ""

        preferences = data.get("preferences", {})
        if isinstance(preferences, dict):
            state["preferences"] = dict(preferences)

        return state

    def _resolve_global_dir(self, global_state_dir: str | os.PathLike[str] | None) -> Path:
        if global_state_dir is not None:
            return Path(global_state_dir).expanduser().resolve()
        env_override = os.environ.get("MOTORVIDEOJUEGOSIA_HOME", "").strip()
        if env_override:
            return Path(env_override).expanduser().resolve()
        return (Path.home() / self.GLOBAL_DIR_NAME).resolve()

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4)
