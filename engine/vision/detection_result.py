"""Serializable vision detection DTOs with no optional CV dependencies."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence, cast

JsonDict = dict[str, Any]


class DetectionResultValidationError(ValueError):
    """Raised when a normalized detection payload is invalid."""


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _normalized_bbox(value: Sequence[Any]) -> tuple[float, float, float, float]:
    if isinstance(value, (str, bytes)) or len(value) != 4:
        raise DetectionResultValidationError("bbox must contain exactly four numeric values: x, y, w, h")
    x, y, width, height = value
    for name, item in (("x", x), ("y", y), ("w", width), ("h", height)):
        if not _finite_number(item):
            raise DetectionResultValidationError(f"bbox.{name} must be a finite non-bool number")
    if float(width) <= 0.0 or float(height) <= 0.0:
        raise DetectionResultValidationError("bbox.w and bbox.h must be positive")
    return (float(x), float(y), float(width), float(height))


def _normalized_confidence(value: Any) -> float | None:
    if value is None:
        return None
    if not _finite_number(value) or not 0.0 <= float(value) <= 1.0:
        raise DetectionResultValidationError("confidence must be between 0 and 1 inclusive")
    return float(value)


@dataclass(frozen=True)
class DetectionResult:
    """Normalized object-detection output used by vision adapters."""

    label: str
    bbox: tuple[float, float, float, float]
    confidence: float | None = None
    metadata: JsonDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label.strip():
            raise DetectionResultValidationError("label must be a non-empty string")
        object.__setattr__(self, "label", self.label.strip())
        object.__setattr__(self, "bbox", _normalized_bbox(self.bbox))
        object.__setattr__(self, "confidence", _normalized_confidence(self.confidence))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DetectionResult":
        bbox_value = data.get("bbox")
        if isinstance(bbox_value, Mapping):
            bbox_value = (bbox_value.get("x"), bbox_value.get("y"), bbox_value.get("w"), bbox_value.get("h"))
        return cls(
            label=cast(str, data.get("label")),
            bbox=cast(tuple[float, float, float, float], bbox_value),
            confidence=data.get("confidence"),
            metadata=dict(data.get("metadata") or {}),
        )

    def to_dict(self) -> JsonDict:
        return asdict(self)


__all__ = ["DetectionResult", "DetectionResultValidationError"]
