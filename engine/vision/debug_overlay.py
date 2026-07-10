"""Deterministic stdlib-only PPM debug overlays for GameSpec2D."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from engine.vision.gamespec2d import GameSpec2D, GameSpecValidationError
from engine.vision.image_loader import RGB, PixelImage, VisionImageError, load_image


class DebugOverlayError(ValueError):
    """Structured debug overlay generation error."""


@dataclass(frozen=True)
class DebugOverlayReport:
    overlay_path: str
    source: str
    gamespec: str
    dimensions: dict[str, int]
    annotation_counts: dict[str, int]
    warning_count: int
    format: str = "PPM_P3"

    def to_dict(self) -> dict[str, Any]:
        return {
            "overlay_path": self.overlay_path,
            "source": self.source,
            "gamespec": self.gamespec,
            "dimensions": dict(self.dimensions),
            "annotation_counts": dict(self.annotation_counts),
            "warning_count": self.warning_count,
            "format": self.format,
        }


_GRID_COLOR: RGB = (0, 96, 255)
_SOLID_COLOR: RGB = (255, 128, 0)
_DECORATIVE_COLOR: RGB = (128, 0, 255)
_ENTITY_COLORS: dict[str, RGB] = {
    "player_spawn": (0, 220, 0),
    "coin": (255, 220, 0),
    "goal": (255, 0, 220),
    "hazard": (255, 0, 0),
    "enemy_patrol": (220, 0, 0),
    "checkpoint": (0, 220, 220),
    "killzone": (160, 0, 0),
    "platform": (255, 128, 0),
    "solid_ground": (180, 90, 0),
    "decorative_prop": (128, 0, 255),
}


def create_debug_overlay(image_path: str | Path, gamespec_path: str | Path, out_path: str | Path) -> DebugOverlayReport:
    """Write a deterministic PPM overlay for a PPM image and GameSpec2D.

    The input image and GameSpec are fully loaded and validated before the output
    path is opened. Existing outputs are refused. If writing fails after this call
    creates the output, the partial file is removed.
    """

    source = Path(image_path)
    spec_path = Path(gamespec_path)
    output = Path(out_path)

    image = _load_valid_image(source)
    spec = _load_valid_gamespec(spec_path)

    pixels = list(image.pixels)
    counts = {
        "grid_lines": 0,
        "solid_cells": 0,
        "decorative_cells": 0,
        "entities": 0,
    }

    counts["grid_lines"] = _draw_grid(pixels, image, spec)
    for cell in spec.tilemap.solid_cells:
        if _draw_cell(pixels, image, spec, cell.x, cell.y, _SOLID_COLOR):
            counts["solid_cells"] += 1
    for cell in spec.tilemap.decorative_cells:
        if _draw_cell(pixels, image, spec, cell.x, cell.y, _DECORATIVE_COLOR):
            counts["decorative_cells"] += 1
    for entity in spec.entities:
        color = _ENTITY_COLORS.get(entity.type, (255, 0, 255))
        if _draw_marker(pixels, image, spec, float(entity.x), float(entity.y), color):
            counts["entities"] += 1

    created = False
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="ascii", newline="\n") as handle:
            created = True
            _write_ppm_p3(handle, image.width, image.height, pixels)
    except FileExistsError as exc:
        raise FileExistsError(f"overlay output already exists: {output}") from exc
    except Exception:
        if created:
            try:
                output.unlink()
            except FileNotFoundError:
                pass
        raise

    return DebugOverlayReport(
        overlay_path=output.as_posix(),
        source=source.as_posix(),
        gamespec=spec_path.as_posix(),
        dimensions={"width": image.width, "height": image.height},
        annotation_counts=counts,
        warning_count=len(spec.warnings),
    )


def _load_valid_image(path: Path) -> PixelImage:
    try:
        return load_image(path)
    except VisionImageError as exc:
        raise DebugOverlayError(str(exc)) from exc


def _load_valid_gamespec(path: Path) -> GameSpec2D:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"GameSpec file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DebugOverlayError(f"GameSpec file is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise DebugOverlayError("GameSpec root must be a JSON object")
    try:
        spec = GameSpec2D.from_dict(raw)
        spec.validate()
    except GameSpecValidationError:
        raise
    except Exception as exc:
        raise DebugOverlayError(f"Invalid GameSpec2D: {exc}") from exc
    return spec


def _put(pixels: list[RGB], image: PixelImage, x: int, y: int, color: RGB) -> bool:
    if 0 <= x < image.width and 0 <= y < image.height:
        pixels[y * image.width + x] = color
        return True
    return False


def _draw_grid(pixels: list[RGB], image: PixelImage, spec: GameSpec2D) -> int:
    count = 0
    verticals = {round(i * (image.width - 1) / max(1, spec.grid.width)) for i in range(spec.grid.width + 1)}
    horizontals = {round(i * (image.height - 1) / max(1, spec.grid.height)) for i in range(spec.grid.height + 1)}
    for x in sorted(verticals):
        for y in range(image.height):
            _put(pixels, image, x, y, _GRID_COLOR)
        count += 1
    for y in sorted(horizontals):
        for x in range(image.width):
            _put(pixels, image, x, y, _GRID_COLOR)
        count += 1
    return count


def _cell_bounds(image: PixelImage, spec: GameSpec2D, cell_x: int, cell_y: int) -> tuple[int, int, int, int]:
    left = round(cell_x * image.width / spec.grid.width)
    right = round((cell_x + 1) * image.width / spec.grid.width) - 1
    top = round(cell_y * image.height / spec.grid.height)
    bottom = round((cell_y + 1) * image.height / spec.grid.height) - 1
    return max(0, left), max(0, top), min(image.width - 1, right), min(image.height - 1, bottom)


def _draw_cell(pixels: list[RGB], image: PixelImage, spec: GameSpec2D, cell_x: int, cell_y: int, color: RGB) -> bool:
    left, top, right, bottom = _cell_bounds(image, spec, cell_x, cell_y)
    if left > right or top > bottom:
        return False
    changed = False
    for x in range(left, right + 1):
        changed = _put(pixels, image, x, top, color) or changed
        changed = _put(pixels, image, x, bottom, color) or changed
    for y in range(top, bottom + 1):
        changed = _put(pixels, image, left, y, color) or changed
        changed = _put(pixels, image, right, y, color) or changed
    return changed


def _draw_marker(pixels: list[RGB], image: PixelImage, spec: GameSpec2D, world_x: float, world_y: float, color: RGB) -> bool:
    source_w = spec.source.width or spec.camera.width or (spec.grid.width * spec.grid.tile_size)
    source_h = spec.source.height or spec.camera.height or (spec.grid.height * spec.grid.tile_size)
    px = round(world_x * (image.width - 1) / max(1.0, float(source_w)))
    py = round(world_y * (image.height - 1) / max(1.0, float(source_h)))
    changed = False
    for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
        changed = _put(pixels, image, px + dx, py + dy, color) or changed
    return changed


def _write_ppm_p3(handle: Any, width: int, height: int, pixels: list[RGB]) -> None:
    handle.write("P3\n")
    handle.write(f"{width} {height}\n")
    handle.write("255\n")
    for y in range(height):
        row = pixels[y * width : (y + 1) * width]
        handle.write(" ".join(f"{r} {g} {b}" for r, g, b in row))
        handle.write("\n")
