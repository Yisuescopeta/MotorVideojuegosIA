"""Optional Supervision-compatible adapter for GameSpec2D generation.

This module intentionally avoids importing optional vision/ML packages at module
import time. Callers may pass normalized :class:`DetectionResult` values or
plain dictionaries without installing ``supervision``.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from typing import Any, Iterable, Mapping

from .detection_result import DetectionResult
from .gamespec2d import EntitySpec, GameSpec2D, GridSpec, SourceImageMetadata, WarningSpec


class OptionalSupervisionDependencyError(ImportError):
    """Raised for supervision-native objects when the optional package is absent."""


class UnknownDetectionLabelError(ValueError):
    """Raised when unknown labels are rejected by policy."""


@dataclass(frozen=True)
class SupervisionAdapterOptions:
    unknown_label_policy: str = "decorative_prop"
    tile_size: float = 1.0
    source_width: int | None = None
    source_height: int | None = None
    source_path: str | None = None


_SEMANTIC_ALIASES = {
    "player": "player_spawn",
    "player_spawn": "player_spawn",
    "spawn": "player_spawn",
    "ground": "solid_ground",
    "solid": "solid_ground",
    "solid_ground": "solid_ground",
    "platform": "platform",
    "coin": "coin",
    "collectible": "coin",
    "enemy": "enemy_patrol",
    "enemy_patrol": "enemy_patrol",
    "hazard": "hazard",
    "spike": "hazard",
    "spikes": "hazard",
    "goal": "goal",
    "finish": "goal",
    "checkpoint": "checkpoint",
    "killzone": "killzone",
    "kill_zone": "killzone",
    "decor": "decorative_prop",
    "decoration": "decorative_prop",
    "decorative_prop": "decorative_prop",
}


def detections_to_gamespec2d(
    detections: Iterable[DetectionResult | Mapping[str, Any]] | DetectionResult | Mapping[str, Any],
    *,
    unknown_label_policy: str = "decorative_prop",
    tile_size: float = 1.0,
    source_width: int | None = None,
    source_height: int | None = None,
    source_path: str | None = None,
) -> GameSpec2D:
    """Convert normalized detections into a valid internal GameSpec2D."""

    options = SupervisionAdapterOptions(
        unknown_label_policy=unknown_label_policy,
        tile_size=tile_size,
        source_width=source_width,
        source_height=source_height,
        source_path=source_path,
    )
    normalized = normalize_detections(detections)
    warnings: list[WarningSpec] = []
    entities: list[EntitySpec] = []

    if not normalized:
        warnings.append(WarningSpec(code="no_detections", message="No detections were provided by the vision adapter."))

    for index, detection in enumerate(normalized):
        entity_type = _semantic_type_for_label(detection.label)
        if entity_type is None:
            if options.unknown_label_policy == "reject":
                raise UnknownDetectionLabelError(f"unknown detection label {detection.label!r} at index {index}")
            if options.unknown_label_policy != "decorative_prop":
                raise ValueError("unknown_label_policy must be 'decorative_prop' or 'reject'")
            entity_type = "decorative_prop"
            warnings.append(
                WarningSpec(
                    code="unknown_detection_label",
                    message=f"Unknown detection label {detection.label!r} mapped to decorative_prop.",
                    confidence=detection.confidence,
                    metadata={"label": detection.label, "index": index},
                )
            )
        x, y, width, height = detection.bbox
        entities.append(
            EntitySpec(
                type=entity_type,
                x=x + (width / 2.0),
                y=y + (height / 2.0),
                semantics=entity_type,
                label=entity_type if entity_type != "decorative_prop" else detection.label,
                confidence=detection.confidence,
                metadata={"bbox": {"x": x, "y": y, "w": width, "h": height}, "source_label": detection.label, **detection.metadata},
            )
        )

    spec = GameSpec2D(
        source=SourceImageMetadata(width=options.source_width, height=options.source_height, path=options.source_path),
        grid=_grid_for_detections(normalized, options),
        entities=entities,
        warnings=warnings,
        metadata={"adapter": "supervision_optional", "detection_count": len(normalized)},
    )
    spec.validate()
    return spec


def normalize_detections(
    detections: Iterable[DetectionResult | Mapping[str, Any]] | DetectionResult | Mapping[str, Any],
) -> list[DetectionResult]:
    """Normalize supported detection payloads without importing supervision."""

    if isinstance(detections, DetectionResult):
        return [detections]
    if isinstance(detections, Mapping):
        return [DetectionResult.from_dict(detections)]
    if _looks_like_supervision_native(detections):
        _require_supervision_for_native_object(detections)
    return [_normalize_one(item) for item in detections]


def _normalize_one(item: DetectionResult | Mapping[str, Any]) -> DetectionResult:
    if isinstance(item, DetectionResult):
        return item
    if isinstance(item, Mapping):
        return DetectionResult.from_dict(item)
    if _looks_like_supervision_native(item):
        _require_supervision_for_native_object(item)
    raise TypeError(f"unsupported detection item type: {type(item).__name__}")


def _semantic_type_for_label(label: str) -> str | None:
    return _SEMANTIC_ALIASES.get(label.strip().lower().replace(" ", "_"))


def _grid_for_detections(detections: list[DetectionResult], options: SupervisionAdapterOptions) -> GridSpec:
    max_x = float(options.source_width or 1)
    max_y = float(options.source_height or 1)
    for detection in detections:
        x, y, width, height = detection.bbox
        max_x = max(max_x, x + width)
        max_y = max(max_y, y + height)
    tile_size = float(options.tile_size)
    width = max(1, int(max_x // tile_size) + 1)
    height = max(1, int(max_y // tile_size) + 1)
    return GridSpec(width=width, height=height, tile_size=tile_size)


def _looks_like_supervision_native(value: Any) -> bool:
    cls = value.__class__
    module = getattr(cls, "__module__", "")
    return module.startswith("supervision") or cls.__name__ == "Detections"


def _require_supervision_for_native_object(value: Any) -> None:
    if find_spec("supervision") is None:
        raise OptionalSupervisionDependencyError(
            "A supervision-native detection object was provided, but optional dependency 'supervision' is not installed. "
            "Convert detections to DetectionResult/dict first or install supervision in your application environment."
        )
    raise TypeError(f"supervision-native object conversion is not enabled for {type(value).__name__}; pass normalized detections")


__all__ = [
    "OptionalSupervisionDependencyError",
    "SupervisionAdapterOptions",
    "UnknownDetectionLabelError",
    "detections_to_gamespec2d",
    "normalize_detections",
]
