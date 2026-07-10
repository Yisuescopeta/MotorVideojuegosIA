from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from engine.vision.debug_overlay import create_debug_overlay
from engine.vision.image_loader import load_image


ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "tests" / "fixtures" / "vision" / "simple_platformer.ppm"
SPEC = ROOT / "examples" / "vision" / "simple_platformer.gamespec.json"


class VisionDebugOverlayTests(unittest.TestCase):
    def test_create_debug_overlay_writes_same_size_loadable_ppm_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "overlay.ppm"

            report = create_debug_overlay(IMAGE, SPEC, out)

            self.assertTrue(out.exists())
            overlay = load_image(out)
            source = load_image(IMAGE)
            self.assertEqual((overlay.width, overlay.height), (source.width, source.height))
            self.assertNotEqual(overlay.pixels, source.pixels)
            data = report.to_dict()
            self.assertEqual(data["overlay_path"], out.as_posix())
            self.assertEqual(data["source"], IMAGE.as_posix())
            self.assertEqual(data["gamespec"], SPEC.as_posix())
            self.assertEqual(data["dimensions"], {"width": 16, "height": 16})
            self.assertEqual(data["warning_count"], 1)
            self.assertEqual(data["format"], "PPM_P3")
            self.assertEqual(data["annotation_counts"]["solid_cells"], 12)
            self.assertEqual(data["annotation_counts"]["decorative_cells"], 0)
            self.assertEqual(data["annotation_counts"]["entities"], 3)
            self.assertGreater(data["annotation_counts"]["grid_lines"], 0)

    def test_create_debug_overlay_refuses_overwrite_and_preserves_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "overlay.ppm"
            out.write_text("sentinel", encoding="ascii")

            with self.assertRaises(FileExistsError):
                create_debug_overlay(IMAGE, SPEC, out)

            self.assertEqual(out.read_text(encoding="ascii"), "sentinel")

    def test_invalid_gamespec_is_validated_before_output_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            invalid = Path(tmp) / "invalid.gamespec.json"
            data = json.loads(SPEC.read_text(encoding="utf-8"))
            data["grid"]["width"] = 0
            invalid.write_text(json.dumps(data), encoding="utf-8")
            out = Path(tmp) / "overlay.ppm"

            with self.assertRaises(ValueError):
                create_debug_overlay(IMAGE, invalid, out)

            self.assertFalse(out.exists())

    def test_missing_image_is_validated_before_output_is_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "overlay.ppm"

            with self.assertRaises(ValueError):
                create_debug_overlay(Path(tmp) / "missing.ppm", SPEC, out)

            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
