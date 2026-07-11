"""Internal experimental vision contracts and scene-builder tooling.

This package exposes vision data contracts plus experimental GameSpec2D to scene
builder helpers. It avoids importing optional computer-vision dependencies and
protected core internals.
"""

from __future__ import annotations

from .gamespec2d import (
    ALLOWED_ENTITY_TYPES,
    CURRENT_SCHEMA_VERSION,
    STATUS,
    CameraSpec,
    EntitySpec,
    GameSpec2D,
    GameSpecValidationError,
    GridSpec,
    SourceImageMetadata,
    TileCell,
    TileMapSpec,
    WarningSpec,
)
from .gamespec_to_scene import GameSpecSceneBuildError, SceneBuildReport, build_scene_from_gamespec2d

__all__ = [
    "STATUS",
    "CURRENT_SCHEMA_VERSION",
    "ALLOWED_ENTITY_TYPES",
    "GameSpecValidationError",
    "SourceImageMetadata",
    "CameraSpec",
    "GridSpec",
    "TileCell",
    "TileMapSpec",
    "EntitySpec",
    "WarningSpec",
    "GameSpec2D",
    "SceneBuildReport",
    "GameSpecSceneBuildError",
    "build_scene_from_gamespec2d",
]
