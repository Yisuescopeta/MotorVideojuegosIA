"""Load and parse export_presets.motor.json."""

from __future__ import annotations

import json
from pathlib import Path

from engine.export.models import ExportPreset, ExportValidationError, PresetsDocument
from engine.export.preset_migrations import migrate_presets
from engine.export.preset_schema import validate_presets_raw


class PresetLoadError(Exception):
    def __init__(self, message: str, errors: list[ExportValidationError] | None = None):
        super().__init__(message)
        self.errors = errors or []


def load_presets(project_root: str | Path) -> PresetsDocument:
    root = Path(project_root)
    presets_path = root / "export_presets.motor.json"

    if not presets_path.exists():
        raise PresetLoadError(
            f"export_presets.motor.json not found at {presets_path}",
            [ExportValidationError(
                "PRESETS_FILE_NOT_FOUND",
                path=str(presets_path),
                hint="Create export_presets.motor.json in the project root."
            )]
        )

    try:
        raw_text = presets_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise PresetLoadError(f"Cannot read presets file: {exc}")

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PresetLoadError(
            f"Invalid JSON in export_presets.motor.json: {exc}",
            [ExportValidationError(
                "INVALID_JSON",
                path=str(presets_path),
                hint=str(exc)
            )]
        )

    if not isinstance(data, dict):
        raise PresetLoadError(
            "export_presets.motor.json root must be a JSON object.",
            [ExportValidationError("INVALID_JSON_ROOT", hint="Root must be a JSON object.")]
        )

    data = migrate_presets(data)

    errors = validate_presets_raw(data)
    if errors:
        raise PresetLoadError(
            f"Preset validation failed with {len(errors)} error(s).",
            errors
        )

    return PresetsDocument.from_dict(data)


def get_preset_by_name(doc: PresetsDocument, name: str) -> ExportPreset | None:
    for preset in doc.presets:
        if preset.name == name:
            return preset
    return None


def list_preset_names(doc: PresetsDocument) -> list[str]:
    return [p.name for p in doc.presets]
