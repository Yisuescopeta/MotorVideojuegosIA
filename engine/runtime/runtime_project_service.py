"""Minimal project service for exported runtime — resolves file paths without asset database."""

from __future__ import annotations

import os
import shutil
import tempfile
import weakref
import zipfile
from pathlib import Path, PurePosixPath


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
