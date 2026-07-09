"""Internal experimental GameSpec2D contract.

The schema describes a 2D platformer interpretation of an image without
creating scenes or depending on optional CV/runtime packages.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any, ClassVar, Mapping


STATUS = "internal-experimental"
CURRENT_SCHEMA_VERSION = "gamespec2d.v1"
SUPPORTED_GAME_TYPE = "platformer"

ALLOWED_ENTITY_TYPES = frozenset(
    {
        "player_spawn",
        "solid_ground",
        "platform",
        "coin",
        "enemy_patrol",
        "hazard",
        "goal",
        "checkpoint",
        "killzone",
        "decorative_prop",
    }
)


class GameSpecValidationError(ValueError):
    """Validation error carrying the failing field path."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


JsonDict = dict[str, Any]


def _dict(value: Mapping[str, Any] | None) -> JsonDict:
    return dict(value or {})


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _validate_confidence(value: Any, field_path: str) -> None:
    if value is None:
        return
    if not _finite_number(value) or not 0.0 <= float(value) <= 1.0:
        raise GameSpecValidationError(field_path, "confidence must be between 0 and 1 inclusive")


def _validate_confidences_in_metadata(value: Any, field_path: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            item_path = f"{field_path}.{key}"
            if key == "confidence":
                _validate_confidence(item, item_path)
            else:
                _validate_confidences_in_metadata(item, item_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_confidences_in_metadata(item, f"{field_path}[{index}]")


def _validate_semantic_label(semantic: str | None, label: str | None, field_path: str, *, decorative: bool) -> None:
    if decorative:
        return
    for attr, value in (("semantics", semantic), ("label", label)):
        if value is not None and value not in ALLOWED_ENTITY_TYPES:
            raise GameSpecValidationError(f"{field_path}.{attr}", f"unknown semantic label {value!r}")


@dataclass
class SourceImageMetadata:
    width: int | None = None
    height: int | None = None
    path: str | None = None
    metadata: JsonDict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "SourceImageMetadata":
        data = data or {}
        return cls(
            width=data.get("width"),
            height=data.get("height"),
            path=data.get("path"),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class CameraSpec:
    x: float = 0.0
    y: float = 0.0
    width: float | None = None
    height: float | None = None
    confidence: float | None = None
    metadata: JsonDict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "CameraSpec":
        data = data or {}
        return cls(
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            width=data.get("width"),
            height=data.get("height"),
            confidence=data.get("confidence"),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class GridSpec:
    width: int
    height: int
    tile_size: float
    origin_x: float = 0.0
    origin_y: float = 0.0
    confidence: float | None = None
    metadata: JsonDict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GridSpec":
        return cls(
            width=data.get("width"),
            height=data.get("height"),
            tile_size=data.get("tile_size"),
            origin_x=data.get("origin_x", 0.0),
            origin_y=data.get("origin_y", 0.0),
            confidence=data.get("confidence"),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class TileCell:
    x: int
    y: int
    semantics: str | None = None
    label: str | None = None
    confidence: float | None = None
    metadata: JsonDict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TileCell":
        return cls(
            x=data.get("x"),
            y=data.get("y"),
            semantics=data.get("semantics"),
            label=data.get("label"),
            confidence=data.get("confidence"),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class TileMapSpec:
    solid_cells: list[TileCell] = field(default_factory=list)
    decorative_cells: list[TileCell] = field(default_factory=list)
    confidence: float | None = None
    metadata: JsonDict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "TileMapSpec":
        data = data or {}
        return cls(
            solid_cells=[TileCell.from_dict(item) for item in data.get("solid_cells", [])],
            decorative_cells=[TileCell.from_dict(item) for item in data.get("decorative_cells", [])],
            confidence=data.get("confidence"),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class EntitySpec:
    type: str
    x: float
    y: float
    semantics: str | None = None
    label: str | None = None
    confidence: float | None = None
    metadata: JsonDict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EntitySpec":
        return cls(
            type=data.get("type"),
            x=data.get("x"),
            y=data.get("y"),
            semantics=data.get("semantics"),
            label=data.get("label"),
            confidence=data.get("confidence"),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class WarningSpec:
    code: str
    message: str
    confidence: float | None = None
    metadata: JsonDict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WarningSpec":
        return cls(
            code=data.get("code"),
            message=data.get("message"),
            confidence=data.get("confidence"),
            metadata=_dict(data.get("metadata")),
        )


@dataclass
class GameSpec2D:
    schema_version: str = CURRENT_SCHEMA_VERSION
    game_type: str = SUPPORTED_GAME_TYPE
    source: SourceImageMetadata = field(default_factory=SourceImageMetadata)
    camera: CameraSpec = field(default_factory=CameraSpec)
    grid: GridSpec = field(default_factory=lambda: GridSpec(width=1, height=1, tile_size=1.0))
    tilemap: TileMapSpec = field(default_factory=TileMapSpec)
    entities: list[EntitySpec] = field(default_factory=list)
    warnings: list[WarningSpec] = field(default_factory=list)
    confidence: float | None = None
    metadata: JsonDict = field(default_factory=dict)

    allowed_entity_types: ClassVar[frozenset[str]] = ALLOWED_ENTITY_TYPES

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GameSpec2D":
        return cls(
            schema_version=data.get("schema_version", CURRENT_SCHEMA_VERSION),
            game_type=data.get("game_type", SUPPORTED_GAME_TYPE),
            source=SourceImageMetadata.from_dict(data.get("source")),
            camera=CameraSpec.from_dict(data.get("camera")),
            grid=GridSpec.from_dict(data.get("grid", {})),
            tilemap=TileMapSpec.from_dict(data.get("tilemap")),
            entities=[EntitySpec.from_dict(item) for item in data.get("entities", [])],
            warnings=[WarningSpec.from_dict(item) for item in data.get("warnings", [])],
            confidence=data.get("confidence"),
            metadata=_dict(data.get("metadata")),
        )

    def to_dict(self) -> JsonDict:
        return asdict(self)

    def validate(self) -> None:
        if self.schema_version != CURRENT_SCHEMA_VERSION:
            raise GameSpecValidationError("schema_version", f"unsupported schema version {self.schema_version!r}")
        if self.game_type != SUPPORTED_GAME_TYPE:
            raise GameSpecValidationError("game_type", f"unsupported game type {self.game_type!r}")
        self._validate_grid()
        self._validate_camera()
        self._validate_tilemap()
        self._validate_entities()
        self._validate_confidences()

    def _validate_grid(self) -> None:
        if not isinstance(self.grid.width, int) or isinstance(self.grid.width, bool) or self.grid.width <= 0:
            raise GameSpecValidationError("grid.width", "must be a positive integer")
        if not isinstance(self.grid.height, int) or isinstance(self.grid.height, bool) or self.grid.height <= 0:
            raise GameSpecValidationError("grid.height", "must be a positive integer")
        if not _finite_number(self.grid.tile_size) or float(self.grid.tile_size) <= 0.0:
            raise GameSpecValidationError("grid.tile_size", "must be a positive finite number")
        for attr in ("origin_x", "origin_y"):
            if not _finite_number(getattr(self.grid, attr)):
                raise GameSpecValidationError(f"grid.{attr}", "must be finite")

    def _validate_camera(self) -> None:
        for attr in ("x", "y"):
            if not _finite_number(getattr(self.camera, attr)):
                raise GameSpecValidationError(f"camera.{attr}", "must be finite")
        for attr in ("width", "height"):
            value = getattr(self.camera, attr)
            if value is not None and (not _finite_number(value) or float(value) <= 0.0):
                raise GameSpecValidationError(f"camera.{attr}", "must be a positive finite number")

    def _validate_tilemap(self) -> None:
        for collection_name, cells in (("solid_cells", self.tilemap.solid_cells), ("decorative_cells", self.tilemap.decorative_cells)):
            for index, cell in enumerate(cells):
                base = f"tilemap.{collection_name}[{index}]"
                if not isinstance(cell.x, int) or isinstance(cell.x, bool) or not 0 <= cell.x < self.grid.width:
                    raise GameSpecValidationError(f"{base}.x", "cell is outside grid bounds")
                if not isinstance(cell.y, int) or isinstance(cell.y, bool) or not 0 <= cell.y < self.grid.height:
                    raise GameSpecValidationError(f"{base}.y", "cell is outside grid bounds")
                _validate_semantic_label(
                    cell.semantics,
                    cell.label,
                    base,
                    decorative=collection_name == "decorative_cells" and cell.label == "decorative_prop",
                )

    def _validate_entities(self) -> None:
        for index, entity in enumerate(self.entities):
            base = f"entities[{index}]"
            if entity.type not in ALLOWED_ENTITY_TYPES:
                raise GameSpecValidationError(f"{base}.type", f"unknown entity type {entity.type!r}")
            if not _finite_number(entity.x):
                raise GameSpecValidationError(f"{base}.x", "coordinate must be finite")
            if not _finite_number(entity.y):
                raise GameSpecValidationError(f"{base}.y", "coordinate must be finite")
            _validate_semantic_label(
                entity.semantics,
                entity.label,
                base,
                decorative=entity.type == "decorative_prop",
            )

    def _validate_confidences(self) -> None:
        _validate_confidences_in_metadata(self.to_dict(), "gamespec")


def validate_gamespec2d(spec: GameSpec2D) -> None:
    spec.validate()
