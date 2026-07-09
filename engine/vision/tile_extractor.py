"""Extract solid tile cells from simple pixel images."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .gamespec2d import TileCell
from .image_loader import PixelImage, RGB
from .tile_grid_detector import TileGridDetection


SolidPredicate = Callable[[RGB, int, int], bool]


@dataclass(frozen=True)
class TileExtractionResult:
    solid_cells: tuple[TileCell, ...]
    warnings: tuple[str, ...] = ()


def extract_solid_cells(
    image: PixelImage,
    grid: TileGridDetection,
    *,
    background_color: RGB | None = None,
    solid_predicate: SolidPredicate | None = None,
    label: str = "solid_ground",
) -> TileExtractionResult:
    """Extract row-major solid cells using center-pixel classification."""

    if background_color is None and solid_predicate is None:
        background_color = image.pixel_at(0, 0)

    cells: list[TileCell] = []
    for cell_y in range(grid.grid_height):
        for cell_x in range(grid.grid_width):
            color = image.pixel_at(
                min(image.width - 1, cell_x * grid.tile_size + grid.tile_size // 2),
                min(image.height - 1, cell_y * grid.tile_size + grid.tile_size // 2),
            )
            is_solid = solid_predicate(color, cell_x, cell_y) if solid_predicate is not None else color != background_color
            if is_solid:
                cells.append(TileCell(x=cell_x, y=cell_y, semantics=label, label=label, confidence=1.0, metadata={"color": color}))

    warnings = () if cells else ("no_solid_tiles",)
    return TileExtractionResult(solid_cells=tuple(cells), warnings=warnings)
