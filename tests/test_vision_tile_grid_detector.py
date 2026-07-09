from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from engine.vision.image_loader import PixelImage, VisionImageError, load_image
from engine.vision.tile_grid_detector import detect_tile_grid


WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)


def image_from_cells(tile_size: int, cells: list[list[tuple[int, int, int]]]) -> PixelImage:
    pixels = []
    for row in cells:
        for inner_y in range(tile_size):
            for color in row:
                pixels.extend([color] * tile_size)
    return PixelImage(width=len(cells[0]) * tile_size, height=len(cells) * tile_size, pixels=tuple(pixels))


class TileGridDetectorTests(unittest.TestCase):
    def test_detects_simple_16_px_grid_with_deterministic_scores(self) -> None:
        image = image_from_cells(16, [[WHITE, BLACK], [RED, WHITE]])

        result = detect_tile_grid(image)

        self.assertEqual(result.tile_size, 16)
        self.assertEqual((result.grid_width, result.grid_height), (2, 2))
        self.assertGreater(result.scores[16], result.scores[24])
        self.assertEqual(result.warnings, ())

    def test_uniform_image_warns_and_uses_smallest_tied_candidate(self) -> None:
        image = PixelImage(width=32, height=32, pixels=(WHITE,) * (32 * 32))

        result = detect_tile_grid(image)

        self.assertEqual(result.tile_size, 8)
        self.assertIn("uniform_image", result.warnings)
        self.assertIn("no_clear_grid", result.warnings)

    def test_ppm_p3_and_p6_loading_and_structured_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p3 = root / "fixture.ppm"
            p3.write_text("P3\n# comment\n2 1\n255\n255 0 0 0 0 0\n", encoding="ascii")
            self.assertEqual(load_image(p3).pixels, (RED, BLACK))

            p6 = root / "fixture-p6.ppm"
            p6.write_bytes(b"P6\n1 1\n255\n" + bytes([255, 255, 255]))
            self.assertEqual(load_image(p6).pixel_at(0, 0), WHITE)

            bad = root / "bad.ppm"
            bad.write_bytes(b"not an image")
            with self.assertRaises(VisionImageError) as caught:
                load_image(bad)
            self.assertEqual(caught.exception.code, "unsupported_image_format")


if __name__ == "__main__":
    unittest.main()
