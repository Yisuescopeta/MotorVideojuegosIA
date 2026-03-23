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

from engine.config import ENGINE_VERSION


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


@dataclass(frozen=True)
class ProjectManifest:
    """Manifiesto serializable del proyecto activo."""

    CURRENT_VERSION = 2
    DEFAULT_TEMPLATE = "empty"
    DEFAULT_PATHS = {
        "assets": "assets",
        "levels": "levels",
        "prefabs": "prefabs",
        "scripts": "scripts",
        "settings": "settings",
        "meta": ".motor/meta",
    }

    name: str
    version: int
    engine_version: str
    template: str
    paths: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "engine_version": self.engine_version,
            "template": self.template,
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
        engine_version = str(data.get("engine_version", "")).strip() or ENGINE_VERSION
        template = str(data.get("template", "")).strip() or cls.DEFAULT_TEMPLATE
        paths = {
            key: str(raw_paths.get(key, default)).strip().replace("\\", "/") or default
            for key, default in cls.DEFAULT_PATHS.items()
        }
        return cls(
            name=name,
            version=version,
            engine_version=engine_version,
            template=template,
            paths=paths,
        )


class ProjectService:
    """Resuelve proyecto activo, launcher, paths y estado local del editor."""

    GLOBAL_DIR_NAME = ".motorvideojuegosia"
    RECENTS_FILE_NAME = "recent_projects.json"
    PROJECT_FILE = "project.json"
    PROJECT_STATE_DIR = ".motor"
    EDITOR_STATE_FILE = "editor_state.json"
    PROJECTS_DIR_NAME = "projects"
    PROJECT_SETTINGS_FILE = "project_settings.json"
    RECENTS_LIMIT = 32

    def __init__(
        self,
        project_root: str | os.PathLike[str] = ".",
        global_state_dir: str | os.PathLike[str] | None = None,
        auto_ensure: bool = True,
    ) -> None:
        self._editor_root = Path(project_root).resolve()
        self._project_root = self._editor_root
        self._manifest: ProjectManifest | None = None
        self._global_dir = self._resolve_global_dir(global_state_dir)
        self._recents_file = self._global_dir / self.RECENTS_FILE_NAME
        self._ensure_global_storage()
        if auto_ensure:
            self.ensure_project(self._project_root)

    @property
    def editor_root(self) -> Path:
        return self._editor_root

    @property
    def internal_projects_root(self) -> Path:
        return self._editor_root / self.PROJECTS_DIR_NAME

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
        is_new_project = not manifest_path.exists()
        if is_new_project:
            manifest = ProjectManifest(
                name=root.name or "MotorVideojuegosIA Project",
                version=ProjectManifest.CURRENT_VERSION,
                engine_version=ENGINE_VERSION,
                template=ProjectManifest.DEFAULT_TEMPLATE,
                paths=dict(ProjectManifest.DEFAULT_PATHS),
            )
            self._write_json(manifest_path, manifest.to_dict())
        manifest = self._load_manifest(manifest_path)
        self._project_root = root
        self._manifest = manifest
        self._ensure_project_layout(create_bootstrap=is_new_project)
        self.record_recent_project()
        return self.manifest

    def create_project(
        self,
        project_root: str | os.PathLike[str],
        name: str | None = None,
    ) -> ProjectManifest:
        root = Path(project_root).resolve()
        if root.exists() and any(root.iterdir()):
            raise FileExistsError(f"Project directory is not empty: {root}")
        manifest = self.ensure_project(root)
        if name is not None and name.strip():
            custom_manifest = ProjectManifest(
                name=name.strip(),
                version=ProjectManifest.CURRENT_VERSION,
                engine_version=ENGINE_VERSION,
                template=manifest.template,
                paths=dict(manifest.paths),
            )
            self._write_manifest(root, custom_manifest)
            self._manifest = custom_manifest
            manifest = custom_manifest
        self._ensure_project_layout(create_bootstrap=True)
        self.record_recent_project()
        return self.manifest

    def register_project(self, project_root: str | os.PathLike[str]) -> Dict[str, Any]:
        root = Path(project_root).expanduser().resolve()
        manifest_path = root / self.PROJECT_FILE
        if not root.exists():
            raise FileNotFoundError(f"Project path not found: {root}")
        if not manifest_path.exists():
            raise FileNotFoundError(f"project.json not found in {root}")
        manifest = self._load_manifest(manifest_path)
        migrated_manifest = self._migrate_manifest(root, manifest)
        self._ensure_project_layout_for(root, migrated_manifest, create_bootstrap=False)
        existing = self._load_registry_entries()
        entry = self._registry_entry_from_manifest(root, migrated_manifest)
        merged = [item for item in existing if self._normalize_registry_path(item.get("path")) != entry["path"]]
        merged.insert(0, entry)
        self._write_registry_entries(merged)
        return self._build_launcher_entry(root, "external_registered", entry)

    def remove_registered_project(self, project_root: str | os.PathLike[str]) -> None:
        target_path = Path(project_root).expanduser().resolve().as_posix()
        items = [
            item
            for item in self._load_registry_entries()
            if self._normalize_registry_path(item.get("path")) != target_path
        ]
        self._write_registry_entries(items)

    def clear_active_project(self) -> None:
        self._manifest = None
        self._project_root = self._editor_root

    def open_project(self, project_root: str | os.PathLike[str]) -> ProjectManifest:
        root = Path(project_root).resolve()
        manifest_path = root / self.PROJECT_FILE
        if not manifest_path.exists():
            raise FileNotFoundError(f"project.json not found in {root}")
        manifest = self._migrate_manifest(root, self._load_manifest(manifest_path))
        self._project_root = root
        self._manifest = manifest
        self._ensure_project_layout(create_bootstrap=False)
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

    def get_project_settings_path(self) -> Path:
        return self.get_project_path("settings") / self.PROJECT_SETTINGS_FILE

    def load_project_settings(self) -> Dict[str, Any]:
        path = self.get_project_settings_path()
        if not path.exists():
            return self._default_project_settings()
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return self._default_project_settings()
        return self._normalize_project_settings(data)

    def save_project_settings(self, data: Dict[str, Any]) -> None:
        self._write_json(self.get_project_settings_path(), self._normalize_project_settings(data))

    def get_project_summary(self) -> Dict[str, Any]:
        return {
            "name": self.project_name,
            "root": self.project_root.as_posix(),
            "manifest_path": self.get_manifest_path().as_posix(),
            "engine_version": self.manifest.engine_version,
            "template": self.manifest.template,
            "paths": dict(self.manifest.paths),
        }

    def get_project_path(self, key: str) -> Path:
        relative = self.manifest.paths.get(key, key)
        return (self._project_root / relative).resolve()

    def build_internal_project_path(self, project_name: str) -> Path:
        sanitized = self._sanitize_project_name(project_name)
        if not sanitized:
            raise ValueError("Project name cannot be empty")
        return self.internal_projects_root / sanitized

    def build_scene_file_path(self, scene_name: str) -> Path:
        if not self.has_project:
            raise RuntimeError("Project manifest not loaded")
        raw_name = str(scene_name or "").strip()
        if not raw_name:
            raise ValueError("Scene name cannot be empty")
        safe_stem = []
        previous_separator = False
        for char in raw_name:
            if char.isalnum():
                safe_stem.append(char.lower())
                previous_separator = False
            elif char in (" ", "-", "_") and not previous_separator:
                safe_stem.append("_")
                previous_separator = True
        stem = "".join(safe_stem).strip("_") or "new_scene"
        levels_root = self.get_project_path("levels")
        candidate = levels_root / f"{stem}.json"
        suffix = 2
        while candidate.exists():
            candidate = levels_root / f"{stem}_{suffix}.json"
            suffix += 1
        return candidate

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
        result: List[Dict[str, Any]] = []
        for item in self._load_registry_entries():
            normalized_path = self._normalize_registry_path(item.get("path"))
            if not normalized_path:
                continue
            launcher_entry = self._build_launcher_entry(Path(normalized_path), "external_registered", item)
            if launcher_entry.get("status") != "valid":
                continue
            result.append(
                {
                    "name": launcher_entry["name"],
                    "path": launcher_entry["path"],
                    "manifest_path": launcher_entry["manifest_path"],
                    "last_opened_utc": launcher_entry["last_opened_utc"],
                }
            )
        return result[: self.RECENTS_LIMIT]

    def list_launcher_projects(self) -> List[Dict[str, Any]]:
        by_path: dict[str, Dict[str, Any]] = {}

        for internal_entry in self._scan_internal_projects():
            by_path[internal_entry["path"]] = internal_entry

        for item in self._load_registry_entries():
            normalized_path = self._normalize_registry_path(item.get("path"))
            if not normalized_path:
                continue
            entry = self._build_launcher_entry(Path(normalized_path), "external_registered", item)
            if entry["path"] in by_path:
                merged = dict(by_path[entry["path"]])
                merged["last_opened_utc"] = str(item.get("last_opened_utc", "") or merged.get("last_opened_utc", ""))
                merged["activity_utc"] = merged["last_opened_utc"] or merged.get("activity_utc", "")
                by_path[entry["path"]] = merged
            else:
                by_path[entry["path"]] = entry

        result = list(by_path.values())
        result.sort(key=self._launcher_sort_key)
        return result

    def record_recent_project(self) -> None:
        if not self.has_project:
            return
        projects = self._load_registry_entries()
        entry = self._registry_entry_from_manifest(self.project_root, self.manifest)
        entry["last_opened_utc"] = _utc_now_iso()
        projects = [item for item in projects if self._normalize_registry_path(item.get("path")) != entry["path"]]
        projects.insert(0, entry)
        self._write_registry_entries(projects)

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

    def list_project_scenes(self) -> List[Dict[str, Any]]:
        if not self.has_project:
            return []
        levels_root = self.get_project_path("levels")
        if not levels_root.exists():
            return []
        result: List[Dict[str, Any]] = []
        for path in sorted(levels_root.rglob("*.json")):
            relative_path = self.to_relative_path(path)
            scene_name = path.stem.replace("_", " ").strip() or path.stem or "Scene"
            try:
                with path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    parsed_name = str(data.get("name", "")).strip()
                    if parsed_name:
                        scene_name = parsed_name
            except Exception:
                pass
            result.append(
                {
                    "name": scene_name,
                    "path": relative_path,
                    "absolute_path": path.as_posix(),
                }
            )
        return result

    def clear_recent_projects(self) -> None:
        self._write_registry_entries([])

    def _ensure_global_storage(self) -> None:
        self._global_dir.mkdir(parents=True, exist_ok=True)
        if not self._recents_file.exists():
            self._write_json(self._recents_file, {"projects": []})

    def _ensure_project_layout(self, create_bootstrap: bool) -> None:
        self._ensure_project_layout_for(self._project_root, self.manifest, create_bootstrap=create_bootstrap)

    def _ensure_project_layout_for(
        self,
        root: Path,
        manifest: ProjectManifest,
        create_bootstrap: bool,
    ) -> None:
        for key in ("assets", "levels", "prefabs", "scripts", "settings", "meta"):
            (root / manifest.paths.get(key, key)).mkdir(parents=True, exist_ok=True)

        state_path = root / self.PROJECT_STATE_DIR / self.EDITOR_STATE_FILE
        if not state_path.exists():
            self._write_json(state_path, self._default_editor_state())

        settings_path = root / manifest.paths["settings"] / self.PROJECT_SETTINGS_FILE
        settings = self._default_project_settings()
        if settings_path.exists():
            try:
                with settings_path.open("r", encoding="utf-8") as handle:
                    settings = self._normalize_project_settings(json.load(handle))
            except Exception:
                settings = self._default_project_settings()
        self._write_json(settings_path, settings)

        if create_bootstrap:
            startup_scene = root / settings["startup_scene"]
            if not startup_scene.exists():
                self._write_default_scene(startup_scene, "Main Scene")

    def _load_manifest(self, manifest_path: Path) -> ProjectManifest:
        with manifest_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return ProjectManifest.from_dict(data)

    def _migrate_manifest(self, root: Path, manifest: ProjectManifest) -> ProjectManifest:
        updated = ProjectManifest(
            name=manifest.name,
            version=max(manifest.version, ProjectManifest.CURRENT_VERSION),
            engine_version=manifest.engine_version or ENGINE_VERSION,
            template=manifest.template or ProjectManifest.DEFAULT_TEMPLATE,
            paths=dict(manifest.paths),
        )
        if updated != manifest:
            self._write_manifest(root, updated)
        return updated

    def _write_manifest(self, root: Path, manifest: ProjectManifest) -> None:
        self._write_json(root / self.PROJECT_FILE, manifest.to_dict())

    def _get_editor_state_path(self) -> Path:
        return self._project_root / self.PROJECT_STATE_DIR / self.EDITOR_STATE_FILE

    def _default_project_settings(self) -> Dict[str, Any]:
        return {
            "startup_scene": "levels/main_scene.json",
            "template": ProjectManifest.DEFAULT_TEMPLATE,
        }

    def _normalize_project_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        defaults = self._default_project_settings()
        if not isinstance(data, dict):
            return defaults
        startup_scene = str(data.get("startup_scene", defaults["startup_scene"])).strip() or defaults["startup_scene"]
        startup_scene = startup_scene.replace("\\", "/")
        template = str(data.get("template", defaults["template"])).strip() or defaults["template"]
        return {
            "startup_scene": startup_scene,
            "template": template,
        }

    def _default_editor_state(self) -> Dict[str, Any]:
        return {
            "recent_assets": {},
            "last_scene": "",
            "open_scenes": [],
            "active_scene": "",
            "scene_view_states": {},
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

        open_scenes = data.get("open_scenes", [])
        if isinstance(open_scenes, list):
            state["open_scenes"] = [str(item) for item in open_scenes if str(item).strip()]

        active_scene = data.get("active_scene", "")
        state["active_scene"] = str(active_scene) if active_scene else ""

        raw_view_states = data.get("scene_view_states", {})
        if isinstance(raw_view_states, dict):
            normalized_view_states: Dict[str, Dict[str, Any]] = {}
            for key, value in raw_view_states.items():
                if isinstance(value, dict):
                    normalized_view_states[str(key)] = dict(value)
            state["scene_view_states"] = normalized_view_states

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

    def _load_registry_entries(self) -> List[Dict[str, Any]]:
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
            if isinstance(item, dict):
                result.append(dict(item))
        return result

    def _write_registry_entries(self, entries: List[Dict[str, Any]]) -> None:
        normalized: List[Dict[str, Any]] = []
        for item in entries:
            path = self._normalize_registry_path(item.get("path"))
            if not path:
                continue
            normalized.append(
                {
                    "name": str(item.get("name", "")).strip() or Path(path).name or "Project",
                    "path": path,
                    "manifest_path": str(item.get("manifest_path", "")).strip() or (Path(path) / self.PROJECT_FILE).as_posix(),
                    "last_opened_utc": str(item.get("last_opened_utc", "")).strip(),
                    "engine_version": str(item.get("engine_version", "")).strip(),
                }
            )
        self._write_json(self._recents_file, {"projects": normalized[: self.RECENTS_LIMIT]})

    def _normalize_registry_path(self, path_value: Any) -> str:
        path_text = str(path_value or "").strip()
        if not path_text:
            return ""
        return Path(path_text).expanduser().resolve().as_posix()

    def _registry_entry_from_manifest(self, root: Path, manifest: ProjectManifest) -> Dict[str, Any]:
        return {
            "name": manifest.name,
            "path": root.resolve().as_posix(),
            "manifest_path": (root / self.PROJECT_FILE).resolve().as_posix(),
            "last_opened_utc": _utc_now_iso(),
            "engine_version": manifest.engine_version,
        }

    def _scan_internal_projects(self) -> List[Dict[str, Any]]:
        root = self.internal_projects_root
        if not root.exists():
            return []
        items: List[Dict[str, Any]] = []
        for child in root.iterdir():
            if not child.is_dir():
                continue
            items.append(self._build_launcher_entry(child, "internal_scan"))
        return items

    def _build_launcher_entry(
        self,
        root: Path,
        source: str,
        registry_item: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        root = root.expanduser()
        normalized_root = root.resolve().as_posix()
        manifest_path = root / self.PROJECT_FILE
        status = "valid"
        manifest: ProjectManifest | None = None

        if not root.exists():
            status = "missing"
        elif not manifest_path.exists():
            status = "invalid"
        else:
            try:
                manifest = self._load_manifest(manifest_path)
            except Exception:
                status = "invalid"

        name = str((registry_item or {}).get("name", "")).strip() or (manifest.name if manifest is not None else root.name or "Project")
        engine_version = str((registry_item or {}).get("engine_version", "")).strip()
        if manifest is not None:
            engine_version = manifest.engine_version
        last_opened_utc = str((registry_item or {}).get("last_opened_utc", "")).strip()

        activity_utc = last_opened_utc
        if not activity_utc and manifest_path.exists():
            try:
                activity_utc = _iso_from_timestamp(manifest_path.stat().st_mtime)
            except OSError:
                activity_utc = ""

        return {
            "name": name,
            "path": normalized_root,
            "manifest_path": manifest_path.resolve().as_posix(),
            "source": source,
            "status": status,
            "last_opened_utc": last_opened_utc,
            "activity_utc": activity_utc,
            "engine_version": engine_version or ENGINE_VERSION,
        }

    def _launcher_sort_key(self, item: Dict[str, Any]) -> tuple[int, float, str]:
        status_priority = 0 if str(item.get("status")) == "valid" else 1
        activity = str(item.get("activity_utc", "") or "")
        try:
            timestamp = datetime.fromisoformat(activity).timestamp() if activity else 0.0
        except ValueError:
            timestamp = 0.0
        return (status_priority, -timestamp, str(item.get("name", "")).lower())

    def _sanitize_project_name(self, value: str) -> str:
        safe = "".join(char for char in str(value).strip() if char not in '<>:"/\\|?*')
        return safe.strip().rstrip(".")

    def _write_default_scene(self, path: Path, scene_name: str) -> None:
        self._write_json(
            path,
            {
                "name": scene_name,
                "entities": [],
                "rules": [],
                "feature_metadata": {},
            },
        )

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4)
