"""Minimal project service for exported runtime — resolves file paths without asset database."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path


class RuntimeProjectService:
    """Lightweight project service for export runtime.

    Provides resolve_path() so RenderSystem can find texture files on disk.
    Does NOT require asset database, editor config, or any project.json.
    """

    def __init__(self, base_path: Path | str) -> None:
        self._base_path = Path(base_path).resolve()
        self.read_only = True
        self.auto_ensure = False

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
        pak_path = self._base_path / "game.pak"
        if not pak_path.exists():
            return None
        try:
            with zipfile.ZipFile(pak_path, "r") as pak:
                if relative_path not in pak.namelist():
                    return None
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(pak.read(relative_path))
                return destination.resolve()
        except (OSError, zipfile.BadZipFile, KeyError):
            return None
