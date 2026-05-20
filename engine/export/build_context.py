"""BuildContext carries state through the export pipeline."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.export.models import ExportPreset


class BuildContext:
    def __init__(self, preset: ExportPreset, project_root: str | Path):
        self.preset = preset
        self.project_root = Path(project_root).resolve()
        self.started_at_utc = datetime.now(timezone.utc)
        self.output_dir = self.project_root / preset.output_path
        safe = _safe_name(preset.name)
        self.staging_dir = (
            self.project_root / ".motor" / "build" / "staging" / safe
        )
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.artifacts: list[dict[str, Any]] = []

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_artifact(
        self, path: str, kind: str, size_bytes: int = 0, sha256: str = ""
    ) -> None:
        artifact_path = Path(path)
        if not artifact_path.is_absolute():
            artifact_path = self.project_root / artifact_path
        if artifact_path.exists() and artifact_path.is_file():
            size_bytes = size_bytes or artifact_path.stat().st_size
            sha256 = sha256 or _sha256_file(artifact_path)
        self.artifacts.append({
            "path": path,
            "kind": kind,
            "size_bytes": size_bytes,
            "sha256": sha256,
        })


def _safe_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in name)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
