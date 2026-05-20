"""Build a deterministic content pack from project."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from engine.export.build_graph import build_content_graph
from engine.export.content_collector import collect_content, write_manifest, write_pak
from engine.export.models import BuildGraphResult, ContentManifest, ExportPreset


def build_content_pack(
    preset: ExportPreset,
    project_root: str | Path,
    staging_dir: str | Path,
) -> tuple[ContentManifest, BuildGraphResult]:
    root = Path(project_root)
    staging = Path(staging_dir)

    include_all = (
        preset.include_debug_tools
        or preset.mode == "debug"
        or bool(preset.extra.get("include_all_assets", False))
    )
    graph = build_content_graph(
        preset.entry_scene, root, include_all_assets=include_all,
    )

    if graph.missing_assets:
        non_optional = [
            a for a in graph.missing_assets
            if not a.startswith(("http://", "https://"))
        ]
        if non_optional and preset.mode == "release":
            raise RuntimeError(
                f"Missing required assets for release build: "
                f"{', '.join(non_optional[:10])}"
            )

    manifest = collect_content(graph, root, staging)
    manifest.generated_at_utc = _deterministic_timestamp()
    manifest.schema_version = 1

    write_manifest(manifest, staging)
    if preset.bundle_mode == "packed":
        write_pak(staging)

    return manifest, graph


def _deterministic_timestamp() -> str:
    raw = os.environ.get("SOURCE_DATE_EPOCH", "0")
    try:
        epoch = int(raw)
    except ValueError:
        epoch = 0
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()
