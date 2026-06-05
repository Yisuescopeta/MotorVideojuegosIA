from __future__ import annotations

import json
import math
from io import BytesIO
from pathlib import Path

from PIL import Image

try:
    import cairosvg  # type: ignore[import-not-found]
except Exception:
    cairosvg = None

try:
    import resvg_py  # type: ignore[import-not-found]
except Exception:
    resvg_py = None


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = ROOT / "engine" / "editor" / "resources" / "icons"
VENDOR_ICONS_DIR = RESOURCE_ROOT / "vendor" / "lucide" / "icons"
MANIFEST_PATH = RESOURCE_ROOT / "lucide_manifest.json"
ATLAS_IMAGE_PATH = RESOURCE_ROOT / "lucide_atlas.png"
ATLAS_METADATA_PATH = RESOURCE_ROOT / "lucide_atlas.json"
ATLAS_SIZES = (16, 24)
PADDING = 4


def _load_manifest() -> dict[str, str]:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("lucide_manifest.json must be a JSON object")
    manifest: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("lucide_manifest.json must map strings to strings")
        manifest[key] = value
    return manifest


def _iter_svg_names() -> list[str]:
    if not VENDOR_ICONS_DIR.exists():
        raise FileNotFoundError(f"Vendor icon directory not found: {VENDOR_ICONS_DIR}")
    return sorted(path.stem for path in VENDOR_ICONS_DIR.glob("*.svg"))


def _validate_manifest(svg_names: set[str], manifest: dict[str, str]) -> None:
    missing = sorted({value for value in manifest.values() if value not in svg_names})
    if missing:
        raise ValueError(f"Manifest references missing Lucide icons: {', '.join(missing)}")


def _render_svg(svg_path: Path, size: int) -> Image.Image:
    if cairosvg is not None:
        png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=size, output_height=size)
    elif resvg_py is not None:
        png_bytes = resvg_py.svg_to_bytes(svg_path=str(svg_path), width=size, height=size)
    else:
        raise RuntimeError("Install CairoSVG or resvg-py to build the Lucide atlas.")
    image = Image.open(BytesIO(png_bytes))
    return image.convert("RGBA")


def _normalize_icon_to_white(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    white_icon = Image.new("RGBA", image.size, (255, 255, 255, 0))
    white_icon.putalpha(alpha)
    return white_icon


def build_atlas() -> None:
    svg_names = _iter_svg_names()
    manifest = _load_manifest()
    svg_name_set = set(svg_names)
    _validate_manifest(svg_name_set, manifest)

    cell_size = max(ATLAS_SIZES) + (PADDING * 2)
    cells_per_icon = len(ATLAS_SIZES)
    total_cells = len(svg_names) * cells_per_icon
    columns = max(1, math.ceil(math.sqrt(total_cells)))
    rows = math.ceil(total_cells / columns)

    atlas = Image.new("RGBA", (columns * cell_size, rows * cell_size), (0, 0, 0, 0))
    metadata = {
        "schema_version": 1,
        "image": ATLAS_IMAGE_PATH.name,
        "sizes": list(ATLAS_SIZES),
        "padding": PADDING,
        "cell_size": cell_size,
        "columns": columns,
        "rows": rows,
        "icons": {},
    }

    cell_index = 0
    for svg_name in svg_names:
        frames: dict[str, dict[str, int]] = {}
        svg_path = VENDOR_ICONS_DIR / f"{svg_name}.svg"
        for size in ATLAS_SIZES:
            rendered = _normalize_icon_to_white(_render_svg(svg_path, size))
            col = cell_index % columns
            row = cell_index // columns
            x = col * cell_size + PADDING
            y = row * cell_size + PADDING
            atlas.alpha_composite(rendered, (x, y))
            frames[str(size)] = {"x": x, "y": y, "w": size, "h": size}
            cell_index += 1
        metadata["icons"][svg_name] = frames

    ATLAS_IMAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(ATLAS_IMAGE_PATH)
    ATLAS_METADATA_PATH.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    build_atlas()
