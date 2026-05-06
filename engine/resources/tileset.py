"""TileSet — atlas tiles, metadata, terrain peering y autotile.

Adaptado de Godot TileSet. Define regiones de atlas, metadata por tile,
conjuntos de terreno y peering bits para autotile conectivo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


# --- cache global ---

_tileset_cache: dict[str, TileSet | None] = {}


# --- tipos de datos ---

@dataclass
class TileAtlasSource:
    """Region de atlas: textura, dimensiones de tile, columnas, márgenes."""

    texture_path: str = ""
    tile_width: int = 16
    tile_height: int = 16
    columns: int = 0
    margin: int = 0
    spacing: int = 0

    def get_tile_region(self, tile_index: int) -> tuple[int, int, int, int]:
        """Retorna (sx, sy, sw, sh) en coordenadas de textura para tile_index."""
        if self.columns <= 0:
            return (0, 0, self.tile_width, self.tile_height)
        col = tile_index % self.columns
        row = tile_index // self.columns
        sx = self.margin + col * (self.tile_width + self.spacing)
        sy = self.margin + row * (self.tile_height + self.spacing)
        return (sx, sy, self.tile_width, self.tile_height)

    def to_dict(self) -> dict[str, Any]:
        return {
            "texture_path": self.texture_path,
            "tile_width": self.tile_width,
            "tile_height": self.tile_height,
            "columns": self.columns,
            "margin": self.margin,
            "spacing": self.spacing,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TileAtlasSource:
        return cls(
            texture_path=str(data.get("texture_path", "")),
            tile_width=max(1, int(data.get("tile_width", 16))),
            tile_height=max(1, int(data.get("tile_height", 16))),
            columns=max(0, int(data.get("columns", 0))),
            margin=max(0, int(data.get("margin", 0))),
            spacing=max(0, int(data.get("spacing", 0))),
        )


@dataclass
class TilePhysicsShape:
    """Forma física por tile: box o circle con puntos locales."""

    shape_type: str = "box"  # "box" o "circle"
    points: list[list[float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "shape_type": self.shape_type,
            "points": [list(p) for p in self.points],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TilePhysicsShape:
        shape_type = str(data.get("shape_type", "box"))
        if shape_type not in ("box", "circle"):
            shape_type = "box"
        points: list[list[float]] = []
        for p in data.get("points", []) or []:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                points.append([float(p[0]), float(p[1])])
        return cls(shape_type=shape_type, points=points)


@dataclass
class TileMetadata:
    """Metadata por tile: capas físicas, datos custom, terreno."""

    tile_id: str = ""
    physics_layers: list[TilePhysicsShape] = field(default_factory=list)
    custom_data: dict[str, Any] = field(default_factory=dict)
    terrain_id: int = -1

    def to_dict(self) -> dict[str, Any]:
        return {
            "tile_id": self.tile_id,
            "physics_layers": [s.to_dict() for s in self.physics_layers],
            "custom_data": self.custom_data,
            "terrain_id": self.terrain_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TileMetadata:
        return cls(
            tile_id=str(data.get("tile_id", "")),
            physics_layers=[
                TilePhysicsShape.from_dict(s)
                for s in (data.get("physics_layers") or [])
            ],
            custom_data=dict(data.get("custom_data") or {}),
            terrain_id=int(data.get("terrain_id", -1)),
        )


@dataclass
class TerrainSet:
    """Conjunto de terreno con nombre, color y modo de peering."""

    name: str = ""
    color: str = "#ffffff"
    mode: int = 0  # 0=corners_and_sides, 1=corners, 2=sides

    VALID_MODES = {0, 1, 2}

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "color": self.color, "mode": self.mode}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TerrainSet:
        mode = int(data.get("mode", 0))
        if mode not in cls.VALID_MODES:
            mode = 0
        return cls(
            name=str(data.get("name", "")),
            color=str(data.get("color", "#ffffff")),
            mode=mode,
        )


# --- Constantes de peering ---

_NEIGHBOR_BITS: dict[str, int] = {
    "N": 0, "NE": 1, "E": 2, "SE": 3,
    "S": 4, "SW": 5, "W": 6, "NW": 7,
}

_NEIGHBOR_OFFSETS: list[tuple[int, int, str]] = [
    (0, -1, "N"), (1, -1, "NE"), (1, 0, "E"), (1, 1, "SE"),
    (0, 1, "S"), (-1, 1, "SW"), (-1, 0, "W"), (-1, -1, "NW"),
]


# --- TileSet principal ---

@dataclass
class TileSet:
    """Conjunto de tiles con atlas, metadata, terrenos y peering bits.

    Atributos:
        resource_id: Identificador único del recurso.
        resource_name: Nombre legible.
        schema_version: Versión del formato de serialización.
        atlas: Fuente de atlas de textura.
        tile_metadata: Mapa de tile_id → TileMetadata.
        terrain_sets: Lista de conjuntos de terreno.
        terrain_peering: Mapa terrain_name → {tile_id → peering_bits}.
            peering_bits es un entero de 8 bits:
            bit 0 = N, bit 1 = NE, bit 2 = E, bit 3 = SE,
            bit 4 = S, bit 5 = SW, bit 6 = W, bit 7 = NW.
    """

    resource_id: str = ""
    resource_name: str = "default"
    schema_version: int = 1
    atlas: TileAtlasSource = field(default_factory=TileAtlasSource)
    tile_metadata: dict[str, TileMetadata] = field(default_factory=dict)
    terrain_sets: list[TerrainSet] = field(default_factory=list)
    terrain_peering: dict[str, dict[str, int]] = field(default_factory=dict)

    # --- Métodos públicos ---

    def get_tile_metadata(self, source_id: str, tile_id: str = "") -> TileMetadata | None:
        """Busca metadata de tile por source_id o tile_id completo."""
        if tile_id and tile_id in self.tile_metadata:
            return self.tile_metadata[tile_id]
        combined = f"{source_id}_{tile_id}" if tile_id else source_id
        if combined in self.tile_metadata:
            return self.tile_metadata[combined]
        # Fallback: búsqueda por prefijo source_id_ cuando solo source_id dado
        if source_id and not tile_id:
            prefix = f"{source_id}_"
            for key, meta in self.tile_metadata.items():
                if key.startswith(prefix):
                    return meta
        return None

    def compute_terrain_mask(
        self,
        layer_tiles: dict[tuple[int, int], Any],
        x: int,
        y: int,
        terrain_name: str,
    ) -> int:
        """Computa mask de 8 bits para la celda (x, y) según vecinos con mismo terreno.

        Args:
            layer_tiles: dict {(x, y): tile_dict} donde tile_dict tiene "tile_id".
            x, y: coordenadas de la celda central.
            terrain_name: nombre del terreno a buscar.

        Returns:
            Entero con bits de vecinos que comparten el terreno.
        """
        mask = 0
        for dx, dy, direction in _NEIGHBOR_OFFSETS:
            neighbor_coord = (x + dx, y + dy)
            neighbor_tile = layer_tiles.get(neighbor_coord)
            if neighbor_tile is not None and self._tile_has_terrain(
                neighbor_tile, terrain_name
            ):
                mask |= 1 << _NEIGHBOR_BITS[direction]
        return mask

    def get_autotile_tile(
        self, terrain_name: str, neighbor_mask: int
    ) -> str | None:
        """Busca tile con peering bits exacto para terrain_name.

        Si no hay match exacto, busca el tile con más bits coincidentes
        como fallback. Retorna None si no encuentra ninguno.
        """
        peering = self.terrain_peering.get(terrain_name)
        if not peering:
            return None

        # Búsqueda exacta
        for tile_id, bits in peering.items():
            if bits == neighbor_mask:
                return tile_id

        # Fallback: mayor peso de bits coincidentes
        best_tile_id: str | None = None
        best_score = -1
        for tile_id, bits in peering.items():
            matching = _count_matching_bits(bits, neighbor_mask)
            if matching > best_score:
                best_score = matching
                best_tile_id = tile_id

        return best_tile_id

    def set_cells_terrain_connect(
        self,
        cells: list[dict[str, int]],
        terrain_name: str,
        get_tile_at: Any,
        set_tile_at: Any,
    ) -> int:
        """Para cada celda, computa mask, busca tile de autotile, lo coloca.

        Args:
            cells: lista de dicts con "x" e "y".
            terrain_name: nombre del terreno para peering.
            get_tile_at: callable (x, y) → tile_dict | None.
            set_tile_at: callable (x, y, tile_id) → None.

        Returns:
            Número de celdas modificadas.
        """
        count = 0
        for cell in cells:
            cx = int(cell.get("x", 0))
            cy = int(cell.get("y", 0))
            mask = self._compute_terrain_mask_from_getter(get_tile_at, cx, cy, terrain_name)
            tile_id = self.get_autotile_tile(terrain_name, mask)
            if tile_id is not None:
                set_tile_at(cx, cy, tile_id)
                count += 1
        return count

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "schema_version": self.schema_version,
            "atlas": self.atlas.to_dict(),
            "tile_metadata": {
                tile_id: meta.to_dict()
                for tile_id, meta in self.tile_metadata.items()
            },
            "terrain_sets": [ts.to_dict() for ts in self.terrain_sets],
            "terrain_peering": {
                name: dict(peering) for name, peering in self.terrain_peering.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TileSet:
        terrain_sets = [
            TerrainSet.from_dict(ts)
            for ts in (data.get("terrain_sets") or [])
        ]
        tile_metadata: dict[str, TileMetadata] = {}
        for tile_id, meta_data in (data.get("tile_metadata") or {}).items():
            tile_metadata[str(tile_id)] = TileMetadata.from_dict(meta_data)
        terrain_peering: dict[str, dict[str, int]] = {}
        for name, peering_data in (data.get("terrain_peering") or {}).items():
            terrain_peering[str(name)] = {
                str(tid): int(bits) for tid, bits in peering_data.items()
            }
        return cls(
            resource_id=str(data.get("resource_id", "")),
            resource_name=str(data.get("resource_name", "default")),
            schema_version=int(data.get("schema_version", 1)),
            atlas=TileAtlasSource.from_dict(data.get("atlas") or {}),
            tile_metadata=tile_metadata,
            terrain_sets=terrain_sets,
            terrain_peering=terrain_peering,
        )

    # --- Helpers internos ---

    def _tile_has_terrain(self, tile: Any, terrain_name: str) -> bool:
        """Verifica si un tile pertenece al terreno dado."""
        if not isinstance(tile, dict):
            return False
        tile_id = str(tile.get("tile_id", ""))
        meta = self.tile_metadata.get(tile_id)
        if meta is not None and meta.terrain_id >= 0:
            for ts in self.terrain_sets:
                if ts.name == terrain_name:
                    return meta.terrain_id == self.terrain_sets.index(ts)
        # Fallback: verificar peering
        peering = self.terrain_peering.get(terrain_name)
        if peering is not None and tile_id in peering:
            return True
        terrain_type = str(tile.get("terrain_type", ""))
        return terrain_type == terrain_name

    def _compute_terrain_mask_from_getter(
        self,
        get_tile_at: Any,
        x: int,
        y: int,
        terrain_name: str,
    ) -> int:
        """Computa mask usando un getter callable en lugar de dict directo."""
        mask = 0
        for dx, dy, direction in _NEIGHBOR_OFFSETS:
            neighbor = get_tile_at(x + dx, y + dy)
            if neighbor is not None and self._tile_has_terrain(neighbor, terrain_name):
                mask |= 1 << _NEIGHBOR_BITS[direction]
        return mask


# --- Funciones helper ---

def _count_matching_bits(a: int, b: int) -> int:
    """Cuenta bits que coinciden entre dos máscaras (bitwise AND population count)."""
    matching = a & b
    return matching.bit_count()


# --- Loader con cache ---

def load_tileset(path_str: str) -> TileSet | None:
    """Carga un TileSet desde archivo JSON con cache global.

    Retorna None si path vacío, archivo no existe, JSON inválido,
    o datos no conforman un TileSet.
    """
    if not path_str or not path_str.strip():
        return None

    resolved = Path(path_str)
    if not resolved.is_absolute():
        resolved = resolved.resolve()

    cache_key = str(resolved)
    if cache_key in _tileset_cache:
        return _tileset_cache[cache_key]

    try:
        raw = resolved.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            _tileset_cache[cache_key] = None
            return None
        ts = TileSet.from_dict(data)
        _tileset_cache[cache_key] = ts
        return ts
    except (OSError, ValueError, TypeError):
        _tileset_cache[cache_key] = None
        return None


def clear_tileset_cache() -> None:
    """Limpia el cache global de TileSet (útil para tests)."""
    _tileset_cache.clear()
