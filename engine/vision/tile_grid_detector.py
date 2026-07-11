"""Deterministic tile-grid detection for simple pixel-art fixtures."""

from __future__ import annotations

from dataclasses import dataclass, field

from .image_loader import PixelImage

DEFAULT_TILE_SIZE_CANDIDATES = (8, 16, 24, 32)


@dataclass(frozen=True)
class TileGridDetection:
    tile_size: int
    grid_width: int
    grid_height: int
    confidence: float
    scores: dict[int, float] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


def detect_tile_grid(image: PixelImage, candidates: tuple[int, ...] = DEFAULT_TILE_SIZE_CANDIDATES) -> TileGridDetection:
    """Pick a tile size from known candidates using deterministic scoring.

    The score rewards candidates that divide the image dimensions and whose
    cell interiors are color-consistent. Ties are broken by the smallest tile
    size to keep output stable and conservative.
    """

    valid_candidates = tuple(candidate for candidate in candidates if candidate > 0)
    if not valid_candidates:
        raise ValueError("at least one positive tile-size candidate is required")

    warnings: list[str] = []
    uniform = len(image.colors()) <= 1
    if uniform:
        warnings.append("uniform_image")

    scores = {candidate: _score_candidate(image, candidate) for candidate in valid_candidates}
    best_tile_size = min(valid_candidates, key=lambda candidate: (-scores[candidate], candidate))
    best_score = scores[best_tile_size]

    sorted_scores = sorted(scores.values(), reverse=True)
    if uniform or best_score <= 0.0 or (len(sorted_scores) > 1 and abs(sorted_scores[0] - sorted_scores[1]) < 0.05):
        warnings.append("no_clear_grid")

    return TileGridDetection(
        tile_size=best_tile_size,
        grid_width=max(1, image.width // best_tile_size),
        grid_height=max(1, image.height // best_tile_size),
        confidence=round(max(0.0, min(1.0, best_score)), 6),
        scores={candidate: round(score, 6) for candidate, score in scores.items()},
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _score_candidate(image: PixelImage, tile_size: int) -> float:
    if image.width < tile_size or image.height < tile_size:
        return 0.0
    grid_width = image.width // tile_size
    grid_height = image.height // tile_size
    if grid_width <= 0 or grid_height <= 0:
        return 0.0
    coverage = (grid_width * tile_size * grid_height * tile_size) / (image.width * image.height)
    divisibility = 1.0 if image.width % tile_size == 0 and image.height % tile_size == 0 else 0.5

    consistent_cells = 0
    total_cells = grid_width * grid_height
    for cell_y in range(grid_height):
        for cell_x in range(grid_width):
            if _cell_is_solid_color(image, cell_x, cell_y, tile_size):
                consistent_cells += 1
    consistency = consistent_cells / total_cells if total_cells else 0.0
    boundary_contrast = _boundary_contrast(image, tile_size, grid_width, grid_height)
    return (0.40 * consistency) + (0.30 * boundary_contrast) + (0.20 * divisibility) + (0.10 * coverage)


def _cell_is_solid_color(image: PixelImage, cell_x: int, cell_y: int, tile_size: int) -> bool:
    x0 = cell_x * tile_size
    y0 = cell_y * tile_size
    first = image.pixel_at(x0, y0)
    for y in range(y0, y0 + tile_size):
        for x in range(x0, x0 + tile_size):
            if image.pixel_at(x, y) != first:
                return False
    return True


def _boundary_contrast(image: PixelImage, tile_size: int, grid_width: int, grid_height: int) -> float:
    checks = 0
    contrasts = 0
    for boundary_x in range(tile_size, grid_width * tile_size, tile_size):
        for y in range(grid_height * tile_size):
            checks += 1
            if image.pixel_at(boundary_x - 1, y) != image.pixel_at(boundary_x, y):
                contrasts += 1
    for boundary_y in range(tile_size, grid_height * tile_size, tile_size):
        for x in range(grid_width * tile_size):
            checks += 1
            if image.pixel_at(x, boundary_y - 1) != image.pixel_at(x, boundary_y):
                contrasts += 1
    return contrasts / checks if checks else 0.0
