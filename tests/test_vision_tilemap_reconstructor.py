from __future__ import annotations

import unittest

from engine.vision.gamespec2d import GameSpec2D
from engine.vision.image_loader import PixelImage, VisionImageError
from engine.vision.tile_grid_detector import TileGridDetection
from engine.vision.tile_extractor import extract_solid_cells
from engine.vision.tilemap_reconstructor import reconstruct_tilemap_from_image


WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 0, 255)


def image_from_cells(tile_size: int, cells: list[list[tuple[int, int, int]]]) -> PixelImage:
    pixels = []
    for row in cells:
        for _inner_y in range(tile_size):
            for color in row:
                pixels.extend([color] * tile_size)
    return PixelImage(width=len(cells[0]) * tile_size, height=len(cells) * tile_size, pixels=tuple(pixels))


class TilemapReconstructorTests(unittest.TestCase):
    def test_extracts_solid_cells_row_major_with_background_color(self) -> None:
        image = image_from_cells(8, [[WHITE, BLACK, BLUE], [BLACK, WHITE, BLACK]])
        grid = TileGridDetection(tile_size=8, grid_width=3, grid_height=2, confidence=1.0)

        result = extract_solid_cells(image, grid, background_color=WHITE)

        self.assertEqual([(cell.x, cell.y) for cell in result.solid_cells], [(1, 0), (2, 0), (0, 1), (2, 1)])
        self.assertEqual(result.warnings, ())

    def test_solid_predicate_overrides_background_detection(self) -> None:
        image = image_from_cells(8, [[WHITE, BLACK], [BLUE, BLACK]])
        grid = TileGridDetection(tile_size=8, grid_width=2, grid_height=2, confidence=1.0)

        result = extract_solid_cells(image, grid, solid_predicate=lambda color, _x, _y: color == BLUE)

        self.assertEqual([(cell.x, cell.y) for cell in result.solid_cells], [(0, 1)])

    def test_reconstruct_tilemap_returns_valid_gamespec_only(self) -> None:
        image = image_from_cells(16, [[WHITE, BLACK], [WHITE, BLACK]])

        spec = reconstruct_tilemap_from_image(image, background_color=WHITE)

        self.assertIsInstance(spec, GameSpec2D)
        spec.validate()
        self.assertEqual((spec.grid.width, spec.grid.height, spec.grid.tile_size), (2, 2, 16.0))
        self.assertEqual([(cell.x, cell.y) for cell in spec.tilemap.solid_cells], [(1, 0), (1, 1)])
        self.assertEqual(spec.entities, [])

    def test_background_only_image_warns_no_solid_tiles(self) -> None:
        image = PixelImage(width=16, height=16, pixels=(WHITE,) * (16 * 16))

        spec = reconstruct_tilemap_from_image(image, background_color=WHITE)

        self.assertEqual(spec.tilemap.solid_cells, [])
        self.assertIn("no_solid_tiles", [warning.code for warning in spec.warnings])

    def test_unsupported_input_is_structured_error(self) -> None:
        with self.assertRaises(VisionImageError) as caught:
            reconstruct_tilemap_from_image(object())  # type: ignore[arg-type]
        self.assertEqual(caught.exception.code, "unsupported_image_input")


if __name__ == "__main__":
    unittest.main()
