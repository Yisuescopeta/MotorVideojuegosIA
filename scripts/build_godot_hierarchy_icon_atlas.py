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
RESOURCE_ROOT = ROOT / "engine" / "editor" / "resources" / "icons" / "godot"
VENDOR_ICONS_DIR = RESOURCE_ROOT / "svg"
MANIFEST_PATH = RESOURCE_ROOT / "godot_hierarchy_manifest.json"
ATLAS_IMAGE_PATH = RESOURCE_ROOT / "godot_hierarchy_atlas.png"
ATLAS_METADATA_PATH = RESOURCE_ROOT / "godot_hierarchy_atlas.json"
ATLAS_SIZES = (16, 24)
PADDING = 4


def _load_manifest_document() -> dict[str, object]:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("godot_hierarchy_manifest.json must be a JSON object")
    return raw


def _load_manifest_icons() -> dict[str, dict[str, str]]:
    raw = _load_manifest_document().get("icons")
    if not isinstance(raw, dict):
        raise ValueError("godot_hierarchy_manifest.json must contain an 'icons' object")
    manifest: dict[str, dict[str, str]] = {}
    for alias, value in raw.items():
        if not isinstance(alias, str) or not isinstance(value, dict):
            raise ValueError("godot_hierarchy manifest icon entries must map strings to objects")
        source = value.get("source")
        atlas_name = value.get("atlas_name")
        if not isinstance(source, str) or not isinstance(atlas_name, str):
            raise ValueError("Each godot_hierarchy icon entry requires string source and atlas_name")
        manifest[alias] = dict(value)
    return manifest


def _validate_manifest(manifest: dict[str, dict[str, str]]) -> None:
    missing = sorted(
        entry["source"]
        for entry in manifest.values()
        if not (VENDOR_ICONS_DIR / entry["source"]).exists()
    )
    if missing:
        raise ValueError(f"Manifest references missing Godot icons: {', '.join(missing)}")


def _render_svg(svg_path: Path, size: int) -> Image.Image:
    if cairosvg is not None:
        png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=size, output_height=size)
    elif resvg_py is not None:
        png_bytes = resvg_py.svg_to_bytes(svg_path=str(svg_path), width=size, height=size)
    else:
        raise RuntimeError("Install CairoSVG or resvg-py to build the Godot hierarchy atlas.")
    image = Image.open(BytesIO(png_bytes))
    return image.convert("RGBA")


def build_atlas() -> None:
    manifest = _load_manifest_icons()
    _validate_manifest(manifest)

    aliases = sorted(manifest)
    cell_size = max(ATLAS_SIZES) + (PADDING * 2)
    total_cells = len(aliases) * len(ATLAS_SIZES)
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
    for alias in aliases:
        entry = manifest[alias]
        frames: dict[str, dict[str, int]] = {}
        svg_path = VENDOR_ICONS_DIR / entry["source"]
        atlas_name = entry["atlas_name"]
        for size in ATLAS_SIZES:
            rendered = _render_svg(svg_path, size)
            col = cell_index % columns
            row = cell_index // columns
            x = col * cell_size + PADDING
            y = row * cell_size + PADDING
            atlas.alpha_composite(rendered, (x, y))
            frames[str(size)] = {"x": x, "y": y, "w": size, "h": size}
            cell_index += 1
        metadata["icons"][atlas_name] = frames

    ATLAS_IMAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(ATLAS_IMAGE_PATH)
    ATLAS_METADATA_PATH.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    build_atlas()
