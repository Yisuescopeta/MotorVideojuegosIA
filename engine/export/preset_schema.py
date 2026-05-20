"""Schema validation for export presets."""

from __future__ import annotations

from typing import Any

from engine.export.models import ExportPreset, ExportValidationError, PresetsDocument

SCHEMA_VERSION = 1

_VALID_PLATFORMS = frozenset({"windows", "linux", "macos", "android", "ios"})
_VALID_MODES = frozenset({"debug", "release"})
_VALID_ARCHITECTURES = frozenset({"x86_64", "x86", "arm64-v8a", "armeabi-v7a", "universal"})
_VALID_BUNDLE_MODES = frozenset({"packed", "directory"})
_VALID_ORIENTATIONS = frozenset({"landscape", "portrait", "sensor"})
_ALLOWED_EXTRA_FIELDS = frozenset({
    "include_all_assets",
    "keystore_path",
    "keystore_password",
    "key_alias",
    "key_password",
})


def validate_preset(preset: ExportPreset) -> list[ExportValidationError]:
    errors: list[ExportValidationError] = []

    for key in sorted(set(preset.extra) - _ALLOWED_EXTRA_FIELDS):
        errors.append(ExportValidationError(
            "UNKNOWN_PRESET_FIELD",
            path=key,
            hint="Remove the unknown field or add it to the export preset schema."
        ))

    if not preset.name or not preset.name.strip():
        errors.append(ExportValidationError(
            "PRESET_NAME_REQUIRED",
            hint="Each preset must have a unique name."
        ))

    if preset.platform not in _VALID_PLATFORMS:
        errors.append(ExportValidationError(
            "INVALID_PLATFORM",
            path=preset.platform,
            hint=f"Platform must be one of: {', '.join(sorted(_VALID_PLATFORMS))}"
        ))

    if preset.architecture not in _VALID_ARCHITECTURES:
        errors.append(ExportValidationError(
            "INVALID_ARCHITECTURE",
            path=preset.architecture,
            hint=f"Architecture must be one of: {', '.join(sorted(_VALID_ARCHITECTURES))}"
        ))

    if preset.mode not in _VALID_MODES:
        errors.append(ExportValidationError(
            "INVALID_MODE",
            path=preset.mode,
            hint=f"Mode must be one of: {', '.join(sorted(_VALID_MODES))}"
        ))

    if not preset.entry_scene:
        errors.append(ExportValidationError(
            "ENTRY_SCENE_REQUIRED",
            hint="Specify an entry_scene path."
        ))

    if not preset.output_path:
        errors.append(ExportValidationError(
            "OUTPUT_PATH_REQUIRED",
            hint="Specify an output_path for the build."
        ))

    if preset.bundle_mode not in _VALID_BUNDLE_MODES:
        errors.append(ExportValidationError(
            "INVALID_BUNDLE_MODE",
            path=preset.bundle_mode,
            hint=f"Bundle mode must be one of: {', '.join(sorted(_VALID_BUNDLE_MODES))}"
        ))

    if preset.platform in ("android", "ios") and not preset.application_id:
        errors.append(ExportValidationError(
            "APPLICATION_ID_REQUIRED",
            hint=f"application_id is required for {preset.platform} exports."
        ))

    if preset.platform in ("android", "ios") and preset.application_id:
        if not _valid_application_id(preset.application_id):
            errors.append(ExportValidationError(
                "INVALID_APPLICATION_ID",
                path=preset.application_id,
                hint="Use reverse-DNS form, for example com.example.game."
            ))

    if preset.platform == "android" and preset.mode == "release" and preset.version_code < 1:
        errors.append(ExportValidationError(
            "ANDROID_VERSION_CODE_REQUIRED",
            hint="Android release exports require version_code >= 1."
        ))

    if preset.platform == "android" and preset.orientation not in _VALID_ORIENTATIONS:
        errors.append(ExportValidationError(
            "INVALID_ORIENTATION",
            path=preset.orientation,
            hint=f"Orientation must be one of: {', '.join(sorted(_VALID_ORIENTATIONS))}"
        ))

    return errors


def _valid_application_id(value: str) -> bool:
    parts = value.split(".")
    if len(parts) < 2:
        return False
    for part in parts:
        if not part or not (part[0].isalpha() or part[0] == "_"):
            return False
        if not all(ch.isalnum() or ch == "_" for ch in part):
            return False
    return True


def validate_presets_document(doc: PresetsDocument) -> list[ExportValidationError]:
    errors: list[ExportValidationError] = []

    if doc.schema_version < 1:
        errors.append(ExportValidationError(
            "INVALID_SCHEMA_VERSION",
            hint="schema_version must be >= 1."
        ))

    seen_names: set[str] = set()
    for preset in doc.presets:
        if preset.name in seen_names:
            errors.append(ExportValidationError(
                "DUPLICATE_PRESET_NAME",
                path=preset.name,
                hint=f"Preset name '{preset.name}' is duplicated."
            ))
        seen_names.add(preset.name)
        errors.extend(validate_preset(preset))

    return errors


def validate_presets_raw(data: dict[str, Any]) -> list[ExportValidationError]:
    if not isinstance(data, dict):
        return [ExportValidationError(
            "INVALID_JSON_ROOT",
            hint="export_presets.motor.json must be a JSON object."
        )]

    if "schema_version" not in data:
        return [ExportValidationError(
            "MISSING_SCHEMA_VERSION",
            hint="Root must have schema_version."
        )]

    if "presets" not in data:
        return [ExportValidationError(
            "MISSING_PRESETS",
            hint="Root must have a 'presets' array."
        )]

    presets_list = data.get("presets")
    if not isinstance(presets_list, list):
        return [ExportValidationError(
            "INVALID_PRESETS_TYPE",
            hint="'presets' must be an array."
        )]

    doc = PresetsDocument.from_dict(data)
    return validate_presets_document(doc)
