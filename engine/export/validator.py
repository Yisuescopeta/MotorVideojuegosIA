"""Runtime validation of export presets against project state."""

from __future__ import annotations

from pathlib import Path

from engine.export.models import ExportPreset, ExportValidationError


def validate_preset_against_project(
    preset: ExportPreset, project_root: str | Path
) -> list[ExportValidationError]:
    root = Path(project_root).resolve()
    errors: list[ExportValidationError] = []

    entry_path = _safe_project_path(root, preset.entry_scene)
    if entry_path is None:
        errors.append(ExportValidationError(
            "UNSAFE_ENTRY_SCENE_PATH",
            path=preset.entry_scene,
            hint="entry_scene must be a relative path inside the project."
        ))
    elif not entry_path.exists():
        errors.append(ExportValidationError(
            "ENTRY_SCENE_NOT_FOUND",
            path=preset.entry_scene,
            hint="Create the scene or update export_presets.motor.json"
        ))

    output_dir = root / preset.output_path
    if not _is_safe_output_path(str(output_dir), str(root)):
        errors.append(ExportValidationError(
            "UNSAFE_OUTPUT_PATH",
            path=preset.output_path,
            hint="Output path must be under dist/ or .motor/build/"
        ))

    return errors


def _safe_project_path(root: Path, relative_path: str) -> Path | None:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    try:
        resolved = (root / candidate).resolve()
        resolved.relative_to(root)
    except (ValueError, OSError):
        return None
    return resolved


def _is_safe_output_path(output_path: str, project_root: str) -> bool:
    try:
        resolved = Path(output_path).resolve()
        root_resolved = Path(project_root).resolve()
        relative = str(resolved.relative_to(root_resolved)).replace("\\", "/")
        safe_prefixes = ("dist/", ".motor/build/")
        return any(relative.startswith(p) for p in safe_prefixes)
    except (ValueError, OSError):
        return False
