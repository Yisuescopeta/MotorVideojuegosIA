"""Minimal project service for exported runtime — resolves file paths without asset database."""

from __future__ import annotations

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

    def resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path against the runtime base directory."""
        candidate = self._base_path / relative_path
        # Try content/ prefix first (common for directory-mode exports)
        if not candidate.exists():
            alt = self._base_path / "content" / relative_path
            if alt.exists():
                return alt.resolve()
        return candidate.resolve()
