"""Export/Build Pipeline for MotorVideojuegosIA.

Godot-inspired export preset system:
  - Serializable presets (export_presets.motor.json)
  - Content graph + deterministic pack
  - Platform exporters with common interface
  - Build reports
  - Separated runtime entrypoint
"""

from engine.export.artifact_writer import safe_copy
from engine.export.build_context import BuildContext
from engine.export.build_graph import build_content_graph
from engine.export.content_collector import collect_content, verify_pak, write_manifest, write_pak
from engine.export.content_pack import build_content_pack
from engine.export.diagnostics import run_export_doctor
from engine.export.exporter_registry import ExporterRegistry
from engine.export.models import (
    BuildGraphResult,
    BundleMode,
    ContentManifest,
    ContentManifestEntry,
    ExportMode,
    ExportPlatform,
    ExportPreset,
    ExportValidationError,
    ExportValidationResult,
    PresetsDocument,
)
from engine.export.platform_exporter import PlatformExporter
from engine.export.preset_loader import (
    PresetLoadError,
    get_preset_by_name,
    list_preset_names,
    load_presets,
)
from engine.export.preset_migrations import (
    LATEST_SCHEMA_VERSION,
    migrate_presets,
)
from engine.export.preset_schema import (
    SCHEMA_VERSION,
    validate_preset,
    validate_presets_document,
    validate_presets_raw,
)
from engine.export.reports import generate_build_report, write_build_report
from engine.export.validator import validate_preset_against_project

__all__ = [
    "BuildContext",
    "BuildGraphResult",
    "BundleMode",
    "ContentManifest",
    "ContentManifestEntry",
    "ExporterRegistry",
    "ExportMode",
    "ExportPlatform",
    "ExportPreset",
    "ExportValidationError",
    "ExportValidationResult",
    "LATEST_SCHEMA_VERSION",
    "PlatformExporter",
    "PresetLoadError",
    "PresetsDocument",
    "SCHEMA_VERSION",
    "build_content_graph",
    "build_content_pack",
    "collect_content",
    "generate_build_report",
    "get_preset_by_name",
    "list_preset_names",
    "load_presets",
    "migrate_presets",
    "run_export_doctor",
    "safe_copy",
    "validate_preset",
    "validate_preset_against_project",
    "validate_presets_document",
    "validate_presets_raw",
    "write_build_report",
    "write_manifest",
    "write_pak",
    "verify_pak",
]
