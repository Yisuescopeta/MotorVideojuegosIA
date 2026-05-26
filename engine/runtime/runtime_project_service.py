"""Minimal project service for exported runtime — resolves file paths without asset database."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import weakref
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from engine.assets.asset_reference import normalize_asset_path, normalize_asset_reference


class RuntimeProjectService:
    """Lightweight project service for export runtime.

    Provides resolve_path() so RenderSystem can find texture files on disk.
    Does NOT require asset database, editor config, or any project.json.
    """

    def __init__(self, base_path: Path | str) -> None:
        self._base_path = Path(base_path).resolve()
        self._script_extract_root: Path | None = None
        self._script_cleanup: weakref.finalize | None = None
        self._pak_entries: set[str] | None = None
        self._asset_extract_cache: dict[str, Path | None] = {}
        self._manifest_cache: dict[str, Any] | None = None
        self._manifest_entries_by_path: dict[str, dict[str, Any]] | None = None
        self._manifest_entries_by_guid: dict[str, dict[str, Any]] | None = None
        self._runtime_entry_payload_cache: dict[str, dict[str, Any]] = {}
        self.read_only = True
        self.auto_ensure = False

    def cleanup(self) -> None:
        """Release temporary runtime files owned by this service."""
        if self._script_cleanup is not None and self._script_cleanup.alive:
            self._script_cleanup()
        self._script_cleanup = None
        self._script_extract_root = None

    @property
    def project_root(self) -> Path:
        return self._base_path

    def get_project_path(self, key: str) -> Path:
        """Return a runtime-safe project subpath for services shared with editor code."""
        return (self._base_path / str(key)).resolve()

    def resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path against the runtime base directory."""
        candidate = Path(relative_path)
        if candidate.is_absolute():
            return candidate.expanduser().resolve()
        normalized = candidate.as_posix()
        candidate = self._base_path / candidate
        # Try content/ prefix first (common for directory-mode exports)
        if not candidate.exists():
            alt = self._base_path / "content" / normalized
            if alt.exists():
                return alt.resolve()
            packed = self._extract_packed_asset(normalized, alt)
            if packed is not None:
                return packed
        return candidate.resolve()

    def resolve_asset_entry(self, locator: Any) -> dict[str, Any] | None:
        """Resolve an exported asset/script entry from game.manifest.json."""
        by_path, by_guid = self._manifest_entry_indexes()
        if not by_path and not by_guid:
            return None

        ref = normalize_asset_reference(locator)
        guid = str(ref.get("guid", "") or "").strip()
        path = normalize_asset_path(ref.get("path", ""))
        if isinstance(locator, str) and locator.startswith("guid_"):
            guid = locator.strip()

        entry = by_guid.get(guid) if guid else None
        if entry is None and path:
            entry = by_path.get(path)
        if entry is None:
            return None
        return self._runtime_entry_payload(entry)

    def get_slice_rect(self, locator: Any, slice_name: str) -> dict[str, Any] | None:
        """Runtime manifests do not currently ship sprite slice metadata."""
        return None

    def extract_packed_scripts(self, destination: Path | str | None = None) -> Path | None:
        """Extract Python scripts from game.pak and return import root."""
        if destination is None and self._script_extract_root is not None:
            scripts_root = self._script_extract_root / "scripts"
            return scripts_root.resolve() if scripts_root.exists() else None

        pak_path = self._base_path / "game.pak"
        if not pak_path.exists():
            return None

        cleanup: weakref.finalize | None = None
        if destination is not None:
            extract_root = Path(destination).resolve()
        else:
            extract_root = Path(tempfile.mkdtemp(prefix="motor_export_scripts_")).resolve()
            cleanup = weakref.finalize(self, shutil.rmtree, extract_root, ignore_errors=True)
        scripts_root = extract_root / "scripts"
        scripts_root_resolved = scripts_root.resolve()
        extracted = False

        try:
            with zipfile.ZipFile(pak_path, "r") as pak:
                for entry_name in pak.namelist():
                    rel_script = self._script_entry_relative_path(entry_name)
                    if rel_script is None:
                        continue
                    target = (scripts_root / rel_script).resolve()
                    try:
                        target.relative_to(scripts_root_resolved)
                    except ValueError:
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(pak.read(entry_name))
                    extracted = True
        except (OSError, zipfile.BadZipFile, KeyError):
            if cleanup is not None:
                cleanup()
            return None

        if not extracted:
            if cleanup is not None:
                cleanup()
            return None

        if destination is None:
            self._script_extract_root = extract_root
            self._script_cleanup = cleanup
        return scripts_root.resolve()

    def to_relative_path(self, path: str | os.PathLike[str]) -> str:
        """Return a portable path relative to the runtime base when possible."""
        if not path:
            return ""
        candidate = self.resolve_path(str(path))
        try:
            return candidate.relative_to(self._base_path).as_posix()
        except ValueError:
            return candidate.as_posix()

    def _extract_packed_asset(self, relative_path: str, destination: Path) -> Path | None:
        if relative_path in self._asset_extract_cache:
            return self._asset_extract_cache[relative_path]
        pak_path = self._base_path / "game.pak"
        if not pak_path.exists():
            self._asset_extract_cache[relative_path] = None
            return None
        entries = self._get_pak_entries()
        if relative_path not in entries:
            self._asset_extract_cache[relative_path] = None
            return None
        try:
            with zipfile.ZipFile(pak_path, "r") as pak:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(pak.read(relative_path))
                resolved = destination.resolve()
                self._asset_extract_cache[relative_path] = resolved
                return resolved
        except (OSError, zipfile.BadZipFile, KeyError):
            self._asset_extract_cache[relative_path] = None
            return None

    def _runtime_entry_payload(self, entry: dict[str, Any]) -> dict[str, Any]:
        path = normalize_asset_path(entry.get("path", ""))
        cached = self._runtime_entry_payload_cache.get(path)
        if cached is not None:
            return dict(cached)
        guid = str(entry.get("guid", "") or "").strip()
        payload = dict(entry)
        payload["path"] = path
        payload["guid"] = guid
        payload["absolute_path"] = self.resolve_path(path).as_posix() if path else ""
        payload["reference"] = {"path": path, "guid": guid}
        payload.setdefault("dependencies", list(entry.get("dependencies", []) or []))
        self._runtime_entry_payload_cache[path] = dict(payload)
        return dict(payload)

    def _manifest_entry_indexes(self) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        if self._manifest_entries_by_path is not None and self._manifest_entries_by_guid is not None:
            return self._manifest_entries_by_path, self._manifest_entries_by_guid

        by_path: dict[str, dict[str, Any]] = {}
        by_guid: dict[str, dict[str, Any]] = {}
        manifest = self._load_manifest()
        for section in ("assets", "scripts", "scenes"):
            entries = manifest.get(section, [])
            if not isinstance(entries, list):
                continue
            for raw_entry in entries:
                if not isinstance(raw_entry, dict):
                    continue
                path = normalize_asset_path(raw_entry.get("path", ""))
                if not path:
                    continue
                entry = dict(raw_entry)
                entry["path"] = path
                by_path[path] = entry
                guid = str(entry.get("guid", "") or "").strip()
                if guid:
                    by_guid[guid] = entry
        self._manifest_entries_by_path = by_path
        self._manifest_entries_by_guid = by_guid
        return by_path, by_guid

    def _load_manifest(self) -> dict[str, Any]:
        if self._manifest_cache is not None:
            return self._manifest_cache
        manifest_path = self._base_path / "game.manifest.json"
        if manifest_path.exists():
            try:
                self._manifest_cache = json.loads(manifest_path.read_text(encoding="utf-8"))
                return self._manifest_cache
            except Exception:
                self._manifest_cache = {}
                return self._manifest_cache
        pak_path = self._base_path / "game.pak"
        if pak_path.exists():
            try:
                with zipfile.ZipFile(pak_path, "r") as pak:
                    self._manifest_cache = json.loads(pak.read("game.manifest.json").decode("utf-8"))
                    return self._manifest_cache
            except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError):
                self._manifest_cache = {}
                return self._manifest_cache
        self._manifest_cache = {}
        return self._manifest_cache

    def _get_pak_entries(self) -> set[str]:
        if self._pak_entries is not None:
            return self._pak_entries
        pak_path = self._base_path / "game.pak"
        try:
            with zipfile.ZipFile(pak_path, "r") as pak:
                self._pak_entries = set(pak.namelist())
        except (OSError, zipfile.BadZipFile):
            self._pak_entries = set()
        return self._pak_entries

    @staticmethod
    def _script_entry_relative_path(entry_name: str) -> Path | None:
        normalized = entry_name.replace("\\", "/")
        parts = PurePosixPath(normalized).parts
        if len(parts) >= 2 and parts[0] == "scripts":
            script_parts = parts[1:]
        elif len(parts) >= 3 and parts[0] == "content" and parts[1] == "scripts":
            script_parts = parts[2:]
        else:
            return None
        if not script_parts or any(part in {"", ".", ".."} for part in script_parts):
            return None
        if not script_parts[-1].endswith(".py"):
            return None
        candidate = Path(*script_parts)
        if candidate.is_absolute() or candidate.drive:
            return None
        return candidate
