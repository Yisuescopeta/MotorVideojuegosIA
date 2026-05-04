"""engine/resources/tileset_resource.py — TileSet resource adaptado de Godot TileSet.

TileSetResource es un recurso serializable independiente del Tilemap.
Define fuentes atlas, tiles alternativos, animaciones, capas de datos,
fisica por tile, navegacion, oclusion y terrain auto-tiling.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


# ── Per-tile physics, navigation, occlusion ───────────────────────────

@dataclass
class TilePhysicsShape:
    """Collision shape for a specific tile."""
    shape_type: str = "box"
    points: list = field(default_factory=list)
    one_way: bool = False
    one_way_direction: tuple = (0, -1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shape_type": self.shape_type,
            "points": [list(p) if isinstance(p, (tuple, list)) else p for p in self.points],
            "one_way": self.one_way,
            "one_way_direction": list(self.one_way_direction),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TilePhysicsShape":
        return cls(
            shape_type=str(data.get("shape_type", "box")),
            points=[list(p) if isinstance(p, (tuple, list)) else p for p in data.get("points", [])],
            one_way=bool(data.get("one_way", False)),
            one_way_direction=tuple(data.get("one_way_direction", (0, -1))),
        )


@dataclass
class TileNavigationPolygon:
    """Navigation polygon for a tile."""
    points: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": [list(p) if isinstance(p, (tuple, list)) else p for p in self.points],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TileNavigationPolygon":
        return cls(
            points=[list(p) if isinstance(p, (tuple, list)) else p for p in data.get("points", [])],
        )


@dataclass
class TileOcclusionPolygon:
    """Light occlusion polygon for a tile."""
    points: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": [list(p) if isinstance(p, (tuple, list)) else p for p in self.points],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TileOcclusionPolygon":
        return cls(
            points=[list(p) if isinstance(p, (tuple, list)) else p for p in data.get("points", [])],
        )


# ── Per-tile animation data ───────────────────────────────────────────

@dataclass
class TileAnimation:
    """Animation data for a tile."""
    frames: list = field(default_factory=list)
    speed: float = 1.0
    mode: str = "forward"

    def to_dict(self) -> dict[str, Any]:
        return {
            "frames": self.frames,
            "speed": self.speed,
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TileAnimation":
        return cls(
            frames=list(data.get("frames", [])),
            speed=float(data.get("speed", 1.0)),
            mode=str(data.get("mode", "forward")),
        )


# ── Per-tile metadata (physics, nav, occlusion, animation, terrain, etc.) ──

@dataclass
class TileMetaData:
    """Per-tile metadata stored on TileSetAtlasSource."""
    tile_id: str = ""
    physics_layers: list[TilePhysicsShape] = field(default_factory=list)
    navigation_polygon: Optional[TileNavigationPolygon] = None
    occlusion_polygon: Optional[TileOcclusionPolygon] = None
    animation: Optional[TileAnimation] = None
    terrain_set: int = -1
    terrain: int = -1
    terrain_peering_bits: int = 0
    custom_data: dict = field(default_factory=dict)
    probability: float = 1.0
    z_index: int = 0
    modulate: tuple = (255, 255, 255, 255)
    y_sort_origin: int = 0

    @property
    def is_solid(self) -> bool:
        """True if tile has any physics shapes defined."""
        return len(self.physics_layers) > 0

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "tile_id": self.tile_id,
            "physics_layers": [ps.to_dict() for ps in self.physics_layers],
            "terrain_set": self.terrain_set,
            "terrain": self.terrain,
            "terrain_peering_bits": self.terrain_peering_bits,
            "custom_data": deepcopy(self.custom_data),
            "probability": self.probability,
            "z_index": self.z_index,
            "modulate": list(self.modulate),
            "y_sort_origin": self.y_sort_origin,
        }
        if self.navigation_polygon is not None:
            result["navigation_polygon"] = self.navigation_polygon.to_dict()
        if self.occlusion_polygon is not None:
            result["occlusion_polygon"] = self.occlusion_polygon.to_dict()
        if self.animation is not None:
            result["animation"] = self.animation.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TileMetaData":
        nav_poly = None
        if "navigation_polygon" in data:
            nav_poly = TileNavigationPolygon.from_dict(data["navigation_polygon"])
        occ_poly = None
        if "occlusion_polygon" in data:
            occ_poly = TileOcclusionPolygon.from_dict(data["occlusion_polygon"])
        anim = None
        if "animation" in data:
            anim = TileAnimation.from_dict(data["animation"])
        return cls(
            tile_id=str(data.get("tile_id", "")),
            physics_layers=[TilePhysicsShape.from_dict(ps) for ps in data.get("physics_layers", [])],
            navigation_polygon=nav_poly,
            occlusion_polygon=occ_poly,
            animation=anim,
            terrain_set=int(data.get("terrain_set", -1)),
            terrain=int(data.get("terrain", -1)),
            terrain_peering_bits=int(data.get("terrain_peering_bits", 0)),
            custom_data=deepcopy(data.get("custom_data", {})),
            probability=float(data.get("probability", 1.0)),
            z_index=int(data.get("z_index", 0)),
            modulate=tuple(data.get("modulate", (255, 255, 255, 255))),
            y_sort_origin=int(data.get("y_sort_origin", 0)),
        )


# ── Animation frame (existing) ────────────────────────────────────────

@dataclass
class TileAnimationFrame:
    """Un frame de animación de tile.

    Adaptado de Godot TileSet tile animations.
    """

    tile_id: str = ""
    duration: float = 0.1

    def to_dict(self) -> dict[str, Any]:
        return {
            "tile_id": self.tile_id,
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TileAnimationFrame":
        return cls(
            tile_id=str(data.get("tile_id", "")),
            duration=float(data.get("duration", 0.1)),
        )

    def __repr__(self) -> str:
        return f"TileAnimationFrame(tile_id={self.tile_id!r}, duration={self.duration:.2f})"


@dataclass
class CustomDataLayerDef:
    """Definición de una capa de datos personalizados.

    Adaptado de Godot TileData custom data layers.
    """

    name: str = ""
    layer_type: str = "int"
    default_value: Any = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "layer_type": self.layer_type,
            "default_value": self.default_value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CustomDataLayerDef":
        return cls(
            name=str(data.get("name", "")),
            layer_type=str(data.get("layer_type", "int")),
            default_value=data.get("default_value", 0),
        )

    def __repr__(self) -> str:
        return f"CustomDataLayerDef(name={self.name!r}, type={self.layer_type})"


@dataclass
class TileSetAtlasSource:
    """Una región de textura atlas que contiene tiles.

    Adaptado de Godot TileSetAtlasSource. Define una zona rectangular
    dentro de una textura atlas y los tiles que contiene.
    """

    source_id: str = ""
    texture_region_x: int = 0
    texture_region_y: int = 0
    texture_region_w: int = 0
    texture_region_h: int = 0
    tile_width: int = 16
    tile_height: int = 16
    columns: int = 0
    margin: int = 0
    spacing: int = 0
    alternative_tiles: dict[str, list[str]] = field(default_factory=dict)
    tile_metadata: dict[str, TileMetaData] = field(default_factory=dict)

    @property
    def tile_count(self) -> int:
        """Número de tiles en esta fuente atlas."""
        cols = self.columns if self.columns > 0 else (self.texture_region_w // self.tile_width if self.tile_width > 0 else 0)
        rows = self.texture_region_h // self.tile_height if self.tile_height > 0 else 0
        return cols * rows

    @property
    def computed_columns(self) -> int:
        if self.columns > 0:
            return self.columns
        if self.tile_width > 0 and self.texture_region_w > 0:
            return self.texture_region_w // self.tile_width
        return 0

    @property
    def computed_rows(self) -> int:
        if self.tile_height > 0 and self.texture_region_h > 0:
            return self.texture_region_h // self.tile_height
        return 0

    def tile_id_at(self, col: int, row: int) -> str:
        """Devuelve el tile_id para una coordenada de grilla (col, row)."""
        return f"{self.source_id}_{col}_{row}"

    def tile_coords_from_id(self, tile_id: str) -> tuple[int, int]:
        """Extrae coordenadas (col, row) desde un tile_id de este source."""
        prefix = f"{self.source_id}_"
        if tile_id.startswith(prefix):
            parts = tile_id[len(prefix):].rsplit("_", 1)
            if len(parts) == 2:
                try:
                    return (int(parts[0]), int(parts[1]))
                except ValueError:
                    pass
        return (-1, -1)

    def get_alternatives(self, col: int, row: int) -> list[str]:
        """Devuelve los IDs de tiles alternativos para una celda."""
        return list(self.alternative_tiles.get(f"{col},{row}", []))

    def add_alternative(self, col: int, row: int, alt_tile_id: str) -> None:
        """Añade un tile alternativo a la celda (col, row)."""
        key = f"{col},{row}"
        if key not in self.alternative_tiles:
            self.alternative_tiles[key] = []
        if alt_tile_id not in self.alternative_tiles[key]:
            self.alternative_tiles[key].append(alt_tile_id)

    def remove_alternative(self, col: int, row: int, alt_tile_id: str) -> None:
        """Elimina un tile alternativo de la celda (col, row)."""
        key = f"{col},{row}"
        if key in self.alternative_tiles:
            self.alternative_tiles[key] = [t for t in self.alternative_tiles[key] if t != alt_tile_id]
            if not self.alternative_tiles[key]:
                del self.alternative_tiles[key]

    def set_tile_metadata(self, tile_id: str, metadata: TileMetaData) -> None:
        """Asigna metadata por tile a este source."""
        self.tile_metadata[tile_id] = metadata

    def get_tile_metadata(self, tile_id: str) -> Optional[TileMetaData]:
        """Obtiene metadata por tile de este source."""
        return self.tile_metadata.get(tile_id)

    def get_tile_metadata_at(self, col: int, row: int) -> Optional[TileMetaData]:
        """Obtiene metadata por coordenada de grilla."""
        return self.tile_metadata.get(self.tile_id_at(col, row))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "texture_region_x": self.texture_region_x,
            "texture_region_y": self.texture_region_y,
            "texture_region_w": self.texture_region_w,
            "texture_region_h": self.texture_region_h,
            "tile_width": self.tile_width,
            "tile_height": self.tile_height,
            "columns": self.columns,
            "margin": self.margin,
            "spacing": self.spacing,
            "alternative_tiles": deepcopy(self.alternative_tiles),
            "tile_metadata": {tid: tm.to_dict() for tid, tm in self.tile_metadata.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TileSetAtlasSource":
        alts: dict[str, list[str]] = {}
        raw_alts = data.get("alternative_tiles", {}) or {}
        if isinstance(raw_alts, dict):
            for key, val in raw_alts.items():
                alts[str(key)] = [str(v) for v in val] if isinstance(val, list) else []
        tile_meta: dict[str, TileMetaData] = {}
        raw_meta = data.get("tile_metadata", {}) or {}
        if isinstance(raw_meta, dict):
            for tid, meta_data in raw_meta.items():
                if isinstance(meta_data, dict):
                    tile_meta[str(tid)] = TileMetaData.from_dict(meta_data)
        return cls(
            source_id=str(data.get("source_id", "")),
            texture_region_x=int(data.get("texture_region_x", 0)),
            texture_region_y=int(data.get("texture_region_y", 0)),
            texture_region_w=int(data.get("texture_region_w", 0)),
            texture_region_h=int(data.get("texture_region_h", 0)),
            tile_width=int(data.get("tile_width", 16)),
            tile_height=int(data.get("tile_height", 16)),
            columns=int(data.get("columns", 0)),
            margin=int(data.get("margin", 0)),
            spacing=int(data.get("spacing", 0)),
            alternative_tiles=alts,
            tile_metadata=tile_meta,
        )

    def __repr__(self) -> str:
        return (
            f"TileSetAtlasSource(id={self.source_id!r}, "
            f"region=({self.texture_region_x},{self.texture_region_y},{self.texture_region_w},{self.texture_region_h}), "
            f"tiles={self.tile_count})"
        )


@dataclass
class TileSetResource:
    """Recurso TileSet serializable (adaptado de Godot TileSet).

    Define un conjunto de tiles con fuentes atlas, tiles alternativos,
    definiciones de animación y capas de datos personalizadas.
    Puede ser referenciado por múltiples Tilemaps.
    """

    resource_id: str = ""
    resource_name: str = "New TileSet"
    tile_width: int = 16
    tile_height: int = 16
    texture_ref: dict[str, str] = field(default_factory=dict)
    columns: int = 0
    margin: int = 0
    spacing: int = 0
    sources: list[TileSetAtlasSource] = field(default_factory=list)
    tile_animations: dict[str, list[TileAnimationFrame]] = field(default_factory=dict)
    custom_data_layers: list[CustomDataLayerDef] = field(default_factory=list)
    terrain_sets: list[dict] = field(default_factory=list)
    physics_layers: list[dict] = field(default_factory=list)
    navigation_layers: list[dict] = field(default_factory=list)
    occlusion_layers: list[dict] = field(default_factory=list)

    # ── helpers ────────────────────────────────────────────────────────

    def add_source(self, source: TileSetAtlasSource) -> None:
        """Añade una fuente atlas al tileset."""
        self.sources.append(source)

    def remove_source(self, source_id: str) -> bool:
        """Elimina una fuente atlas por source_id."""
        for i, src in enumerate(self.sources):
            if src.source_id == source_id:
                self.sources.pop(i)
                return True
        return False

    def get_source(self, source_id: str) -> TileSetAtlasSource | None:
        """Obtiene una fuente atlas por source_id."""
        for src in self.sources:
            if src.source_id == source_id:
                return src
        return None

    def total_tile_count(self) -> int:
        """Número total de tiles en todas las fuentes atlas."""
        return sum(src.tile_count for src in self.sources)

    # ── animation helpers ──────────────────────────────────────────────

    def set_tile_animation(self, tile_id: str, frames: list[TileAnimationFrame]) -> None:
        """Asigna frames de animación a un tile."""
        self.tile_animations[tile_id] = list(frames)

    def get_tile_animation(self, tile_id: str) -> list[TileAnimationFrame]:
        """Obtiene los frames de animación de un tile."""
        return list(self.tile_animations.get(tile_id, []))

    def has_animation(self, tile_id: str) -> bool:
        """Comprueba si un tile tiene animación definida."""
        return tile_id in self.tile_animations and len(self.tile_animations[tile_id]) > 0

    def clear_animation(self, tile_id: str) -> None:
        """Elimina la animación de un tile."""
        self.tile_animations.pop(tile_id, None)

    # ── custom data layer helpers ──────────────────────────────────────

    def add_custom_data_layer(self, layer: CustomDataLayerDef) -> None:
        """Añade una capa de datos personalizados."""
        self.custom_data_layers.append(layer)

    def remove_custom_data_layer(self, name: str) -> bool:
        """Elimina una capa de datos personalizados por nombre."""
        for i, layer in enumerate(self.custom_data_layers):
            if layer.name == name:
                self.custom_data_layers.pop(i)
                return True
        return False

    def get_custom_data_layer(self, name: str) -> CustomDataLayerDef | None:
        """Obtiene una capa de datos personalizados por nombre."""
        for layer in self.custom_data_layers:
            if layer.name == name:
                return layer
        return None

    # ── terrain auto-tiling ────────────────────────────────────────────

    def get_tile_metadata(self, source_id: str, tile_id: str) -> Optional[TileMetaData]:
        """Get per-tile metadata from a source by tile_id."""
        source = self.get_source(source_id)
        if source is None:
            return None
        return source.get_tile_metadata(tile_id)

    def get_terrain_peering_bits(self, source_id: str, cells: dict, x: int, y: int, terrain_set: int, terrain: int) -> int:
        """Calculate terrain peering bits (8-bit mask) for a cell.

        Bits: N=1, NE=2, E=4, SE=8, S=16, SW=32, W=64, NW=128
        Bit set if neighbor has same terrain_set and terrain.
        """
        source = self.get_source(source_id)
        if source is None:
            return 0
        bits = 0
        neighbors = [
            (0, -1, 1),     # N
            (1, -1, 2),     # NE
            (1, 0, 4),      # E
            (1, 1, 8),      # SE
            (0, 1, 16),     # S
            (-1, 1, 32),    # SW
            (-1, 0, 64),    # W
            (-1, -1, 128),  # NW
        ]
        for dx, dy, bit in neighbors:
            nx, ny = x + dx, y + dy
            neighbor_key = (nx, ny)
            neighbor_tile_id = None
            if isinstance(cells, dict):
                neighbor_tile = cells.get(neighbor_key)
            else:
                neighbor_tile = None
            if isinstance(neighbor_tile, dict):
                neighbor_tile_id = neighbor_tile.get("tile_id", "")
            if neighbor_tile_id:
                meta = source.get_tile_metadata(neighbor_tile_id)
                if meta is not None and meta.terrain_set == terrain_set and meta.terrain == terrain:
                    bits |= bit
        return bits

    def get_auto_tile_id(self, source_id: str, terrain_set: int, peering_bits: int) -> Optional[str]:
        """Find matching tile ID for terrain peering bits pattern.
        
        Returns tile_id of tile whose terrain_peering_bits matches exactly,
        or None if no match found.
        """
        source = self.get_source(source_id)
        if source is None:
            return None
        for tid, meta in source.tile_metadata.items():
            if meta.terrain_set == terrain_set and meta.terrain_peering_bits == peering_bits:
                return tid
        return None

    def set_cells_terrain_connect(
        self, source_id: str, cells: dict, terrain_set: int, terrain: int
    ) -> dict:
        """Auto-place tiles based on terrain connectivity.
        
        For each cell in `cells`, computes terrain peering bits and
        replaces tile_id with matching terrain tile. Returns dict
        of changed cell coords -> new tile_id.
        """
        source = self.get_source(source_id)
        if source is None:
            return {}
        changes = {}
        for coord, tile in list(cells.items()):
            if not isinstance(tile, dict):
                continue
            x, y = coord if isinstance(coord, tuple) else (0, 0)
            bits = self.get_terrain_peering_bits(source_id, cells, x, y, terrain_set, terrain)
            matching_id = self.get_auto_tile_id(source_id, terrain_set, bits)
            if matching_id and matching_id != tile.get("tile_id"):
                tile["tile_id"] = matching_id
                changes[coord] = matching_id
        return changes

    def _compute_terrain_bits(
        self, source_id: str, cells: dict, x: int, y: int, terrain_set: int, terrain: int
    ) -> int:
        """Compute 8-bit peering mask for auto-tiling."""
        return self.get_terrain_peering_bits(source_id, cells, x, y, terrain_set, terrain)

    def get_matching_terrain_tile(
        self, source_id: str, terrain_set: int, bits: int
    ) -> Optional[str]:
        """Find tile matching the terrain bitmask pattern."""
        return self.get_auto_tile_id(source_id, terrain_set, bits)

    # ── serialization ──────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "tile_width": self.tile_width,
            "tile_height": self.tile_height,
            "texture_ref": dict(self.texture_ref),
            "columns": self.columns,
            "margin": self.margin,
            "spacing": self.spacing,
            "sources": [src.to_dict() for src in self.sources],
            "tile_animations": {
                str(tid): [frame.to_dict() for frame in frames]
                for tid, frames in self.tile_animations.items()
            },
            "custom_data_layers": [layer.to_dict() for layer in self.custom_data_layers],
            "terrain_sets": deepcopy(self.terrain_sets),
            "physics_layers": deepcopy(self.physics_layers),
            "navigation_layers": deepcopy(self.navigation_layers),
            "occlusion_layers": deepcopy(self.occlusion_layers),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TileSetResource":
        tileset = cls(
            resource_id=str(data.get("resource_id", "")),
            resource_name=str(data.get("resource_name", "New TileSet")),
            tile_width=int(data.get("tile_width", 16)),
            tile_height=int(data.get("tile_height", 16)),
            texture_ref=dict(data.get("texture_ref", {}) or {}),
            columns=int(data.get("columns", 0)),
            margin=int(data.get("margin", 0)),
            spacing=int(data.get("spacing", 0)),
        )
        for src_data in data.get("sources", []) or []:
            if isinstance(src_data, dict):
                tileset.sources.append(TileSetAtlasSource.from_dict(src_data))
            else:
                _logger.warning("TileSetResource.from_dict: skipping non-dict source: %s", type(src_data))
        raw_anim = data.get("tile_animations", {}) or {}
        if isinstance(raw_anim, dict):
            for tid, frames in raw_anim.items():
                if isinstance(frames, list):
                    tileset.tile_animations[str(tid)] = [
                        TileAnimationFrame.from_dict(f) if isinstance(f, dict) else TileAnimationFrame()
                        for f in frames
                    ]
        else:
            _logger.warning("TileSetResource.from_dict: skipping non-dict tile_animations: %s", type(raw_anim))
        raw_layers = data.get("custom_data_layers", []) or []
        if isinstance(raw_layers, list):
            for layer_data in raw_layers:
                if isinstance(layer_data, dict):
                    tileset.custom_data_layers.append(CustomDataLayerDef.from_dict(layer_data))
                else:
                    _logger.warning("TileSetResource.from_dict: skipping non-dict custom_data_layer: %s", type(layer_data))
        else:
            _logger.warning("TileSetResource.from_dict: custom_data_layers is not a list: %s", type(raw_layers))
        raw_terrain = data.get("terrain_sets", None)
        if isinstance(raw_terrain, list):
            tileset.terrain_sets = deepcopy(raw_terrain)
        raw_physics = data.get("physics_layers", None)
        if isinstance(raw_physics, list):
            tileset.physics_layers = deepcopy(raw_physics)
        raw_nav = data.get("navigation_layers", None)
        if isinstance(raw_nav, list):
            tileset.navigation_layers = deepcopy(raw_nav)
        raw_occlusion = data.get("occlusion_layers", None)
        if isinstance(raw_occlusion, list):
            tileset.occlusion_layers = deepcopy(raw_occlusion)
        return tileset

    def __repr__(self) -> str:
        return (
            f"TileSetResource(name={self.resource_name!r}, "
            f"tile_size=({self.tile_width},{self.tile_height}), "
            f"sources={len(self.sources)}, tiles={self.total_tile_count()})"
        )
