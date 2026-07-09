"""Build GameSpec2D tilemaps from simple images without ML dependencies."""

from __future__ import annotations

from pathlib import Path

from .gamespec2d import CameraSpec, GameSpec2D, GridSpec, SourceImageMetadata, TileMapSpec, WarningSpec
from .image_loader import PixelImage, RGB, load_image
from .tile_extractor import SolidPredicate, extract_solid_cells
from .tile_grid_detector import detect_tile_grid


def reconstruct_tilemap_from_image(
    image_or_path: PixelImage | str | Path,
    *,
    background_color: RGB | None = None,
    solid_predicate: SolidPredicate | None = None,
) -> GameSpec2D:
    """Return a validated GameSpec2D with only grid/tilemap data."""

    image = load_image(image_or_path) if isinstance(image_or_path, (str, Path)) else image_or_path
    if not isinstance(image, PixelImage):
        from .image_loader import VisionImageError

        raise VisionImageError("unsupported_image_input", "expected PixelImage or filesystem path")

    grid_detection = detect_tile_grid(image)
    extraction = extract_solid_cells(
        image,
        grid_detection,
        background_color=background_color,
        solid_predicate=solid_predicate,
    )
    warnings = [WarningSpec(code=code, message=_warning_message(code)) for code in (*grid_detection.warnings, *extraction.warnings)]
    spec = GameSpec2D(
        source=SourceImageMetadata(width=image.width, height=image.height, path=image.source_path),
        camera=CameraSpec(x=0.0, y=0.0, width=float(image.width), height=float(image.height), confidence=1.0),
        grid=GridSpec(
            width=grid_detection.grid_width,
            height=grid_detection.grid_height,
            tile_size=float(grid_detection.tile_size),
            confidence=grid_detection.confidence,
            metadata={"scores": grid_detection.scores},
        ),
        tilemap=TileMapSpec(solid_cells=list(extraction.solid_cells), confidence=1.0 if extraction.solid_cells else 0.0),
        warnings=warnings,
        confidence=grid_detection.confidence,
        metadata={"generator": "simple_tilemap_reconstructor"},
    )
    spec.validate()
    return spec


def _warning_message(code: str) -> str:
    messages = {
        "uniform_image": "image is uniform; tile grid cannot be inferred confidently",
        "no_clear_grid": "no clear tile grid was detected; using deterministic best candidate",
        "no_solid_tiles": "no solid tiles were extracted",
    }
    return messages.get(code, code.replace("_", " "))
