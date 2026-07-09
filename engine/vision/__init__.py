"""Internal experimental vision contracts.

This package intentionally exposes data contracts only. It does not import
runtime scene, serialization, rendering, or optional computer-vision packages.
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
]
