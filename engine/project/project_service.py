"""
engine/project/project_service.py - Gestion serializable de proyectos
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ProjectManifest:
    """Manifiesto serializable del proyecto activo."""

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
        return cls(
            name=str(data.get("name", "Untitled Project")),
            version=int(data.get("version", 1)),
            paths={
                "assets": str(data.get("paths", {}).get("assets", "assets")),
                "levels": str(data.get("paths", {}).get("levels", "levels")),
                "scripts": str(data.get("paths", {}).get("scripts", "scripts")),
                "meta": str(data.get("paths", {}).get("meta", ".motor/meta")),
            },
        )


class ProjectService:
    """Resuelve proyecto activo, paths, recientes y estado local del editor."""

    GLOBAL_DIR = Path.home() / ".motorvideojuegosia"
    RECENTS_FILE = GLOBAL_DIR / "recent_projects.json"
    PROJECT_FILE = "project.json"
    PROJECT_STATE_DIR = ".motor"
    EDITOR_STATE_FILE = "editor_state.json"

    def __init__(self, project_root: str | os.PathLike[str] = ".") -> None:
        self._project_root = Path(project_root).resolve()
        self._manifest: ProjectManifest | None = None
        self._ensure_global_storage()
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
    def project_name(self) -> str:
        return self.manifest.name

    def ensure_project(self, project_root: str | os.PathLike[str] | None = None) -> ProjectManifest:
        root = Path(project_root).resolve() if project_root is not None else self._project_root
        root.mkdir(parents=True, exist_ok=True)
        manifest_path = root / self.PROJECT_FILE
        if not manifest_path.exists():
            manifest = ProjectManifest(
                name=root.name or "MotorVideojuegosIA Project",
                version=1,
                paths={
                    "assets": "assets",
                    "levels": "levels",
                    "scripts": "scripts",
                    "meta": ".motor/meta",
                },
            )
            self._write_json(manifest_path, manifest.to_dict())
        manifest = self._load_manifest(manifest_path)
        self._project_root = root
        self._manifest = manifest
        self._ensure_project_layout()
        self.record_recent_project()
        return manifest

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
            self._load_manifest(Path(project_root).resolve() / self.PROJECT_FILE)
            return True
        except Exception:
            return False

    def get_manifest_path(self) -> Path:
        return self._project_root / self.PROJECT_FILE

    def get_project_path(self, key: str) -> Path:
        relative = self.manifest.paths.get(key, key)
        return (self._project_root / relative).resolve()

    def resolve_path(self, path: str | os.PathLike[str]) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return (self._project_root / candidate).resolve()

    def to_relative_path(self, path: str | os.PathLike[str]) -> str:
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
        data.setdefault("recent_assets", {})
        data.setdefault("last_scene", "")
        data.setdefault("preferences", {})
        return data

    def save_editor_state(self, data: Dict[str, Any]) -> None:
        state_path = self._get_editor_state_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._default_editor_state()
        payload.update(data)
        self._write_json(state_path, payload)

    def set_last_scene(self, path: str) -> None:
        state = self.load_editor_state()
        state["last_scene"] = self.to_relative_path(path)
        self.save_editor_state(state)

    def get_last_scene(self) -> str:
        return str(self.load_editor_state().get("last_scene", ""))

    def push_recent_asset(self, category: str, asset_path: str, limit: int = 8) -> None:
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
        if not self.RECENTS_FILE.exists():
            return []
        try:
            with self.RECENTS_FILE.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return []
        projects = data.get("projects", [])
        result: List[Dict[str, Any]] = []
        for item in projects:
            path = Path(item.get("path", ""))
            if path.exists():
                result.append(item)
        return result

    def record_recent_project(self) -> None:
        projects = self.list_recent_projects()
        entry = {
            "name": self.project_name,
            "path": self.project_root.as_posix(),
        }
        projects = [item for item in projects if item.get("path") != entry["path"]]
        projects.insert(0, entry)
        self._write_json(self.RECENTS_FILE, {"projects": projects[:10]})

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
        self._write_json(self.RECENTS_FILE, {"projects": []})

    def _ensure_global_storage(self) -> None:
        self.GLOBAL_DIR.mkdir(parents=True, exist_ok=True)
        if not self.RECENTS_FILE.exists():
            self._write_json(self.RECENTS_FILE, {"projects": []})

    def _ensure_project_layout(self) -> None:
        for key in ("assets", "levels", "scripts", "meta"):
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
            "preferences": {},
        }

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4)
