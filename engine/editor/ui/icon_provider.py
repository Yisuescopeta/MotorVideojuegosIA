"""Atlas-backed icon providers for editor UI."""

from __future__ import annotations

import json
from importlib.resources import as_file, files
from typing import Any

from engine.editor.ui.colors import to_ray_color
from engine.editor.ui.geometry import Rect
from engine.editor.ui.tokens import RGBA

_PACKS = {
    "lucide": {
        "resource_package": "engine.editor.resources.icons",
        "manifest_name": "lucide_manifest.json",
        "atlas_metadata_name": "lucide_atlas.json",
        "atlas_image_name": "lucide_atlas.png",
        "size_fallbacks": (16, 24),
    },
    "godot_hierarchy": {
        "resource_package": "engine.editor.resources.icons.godot",
        "manifest_name": "godot_hierarchy_manifest.json",
        "atlas_metadata_name": "godot_hierarchy_atlas.json",
        "atlas_image_name": "godot_hierarchy_atlas.png",
        "size_fallbacks": (16, 24),
    },
}

_manifest_cache: dict[str, dict[str, Any] | None] = {}
_atlas_cache: dict[str, dict[str, Any] | None] = {}
_texture_cache: dict[str, Any] = {}


def _rl():
    import pyray as rl

    return rl


def _get_pack_config(pack_id: str) -> dict[str, Any]:
    config = _PACKS.get(pack_id)
    if config is None:
        raise KeyError(f"Unknown icon pack: {pack_id}")
    return config


def _read_json_resource(pack_id: str, resource_name: str) -> dict[str, Any] | None:
    config = _get_pack_config(pack_id)
    try:
        resource = files(config["resource_package"]).joinpath(resource_name)
        return json.loads(resource.read_text(encoding="utf-8"))
    except Exception:
        return None


def _normalize_manifest(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    source = raw.get("icons") if isinstance(raw.get("icons"), dict) else raw
    manifest: dict[str, Any] = {}
    if isinstance(source, dict):
        for key, value in source.items():
            if isinstance(key, str):
                manifest[key] = value
    return manifest


def _load_manifest_for_pack(pack_id: str) -> dict[str, Any]:
    if pack_id not in _manifest_cache:
        config = _get_pack_config(pack_id)
        _manifest_cache[pack_id] = _normalize_manifest(_read_json_resource(pack_id, config["manifest_name"]))
    cached = _manifest_cache.get(pack_id)
    return cached if isinstance(cached, dict) else {}


def _load_atlas_metadata_for_pack(pack_id: str) -> dict[str, Any] | None:
    if pack_id not in _atlas_cache:
        config = _get_pack_config(pack_id)
        raw = _read_json_resource(pack_id, config["atlas_metadata_name"])
        _atlas_cache[pack_id] = raw if isinstance(raw, dict) else None
    cached = _atlas_cache.get(pack_id)
    return cached if isinstance(cached, dict) else None


def _is_window_ready() -> bool:
    is_window_ready = getattr(_rl(), "is_window_ready", None)
    if not callable(is_window_ready):
        return False
    try:
        return bool(is_window_ready())
    except Exception:
        return False


def _is_texture_ready(texture: Any) -> bool:
    is_texture_ready = getattr(_rl(), "is_texture_ready", None)
    if not callable(is_texture_ready):
        return True
    try:
        return bool(is_texture_ready(texture))
    except Exception:
        return False


def _load_texture_for_pack(pack_id: str) -> Any | None:
    if pack_id in _texture_cache:
        texture = _texture_cache[pack_id]
        return texture if _is_texture_ready(texture) else None
    if not _is_window_ready():
        return None
    load_texture = getattr(_rl(), "load_texture", None)
    if not callable(load_texture):
        return None
    config = _get_pack_config(pack_id)
    try:
        atlas_resource = files(config["resource_package"]).joinpath(config["atlas_image_name"])
        with as_file(atlas_resource) as atlas_path:
            texture = load_texture(str(atlas_path))
    except Exception:
        return None
    if texture is None or not _is_texture_ready(texture):
        return None
    _texture_cache[pack_id] = texture
    return texture


def _available_icon_entries_for_pack(pack_id: str) -> dict[str, Any]:
    atlas = _load_atlas_metadata_for_pack(pack_id)
    icons = atlas.get("icons") if isinstance(atlas, dict) else None
    return icons if isinstance(icons, dict) else {}


def _manifest_atlas_name(entry: Any) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        atlas_name = entry.get("atlas_name")
        return atlas_name if isinstance(atlas_name, str) else None
    return None


def _resolve_icon_name(pack_id: str, name: str) -> str | None:
    normalized = str(name or "").strip()
    if not normalized:
        return None
    icons = _available_icon_entries_for_pack(pack_id)
    if normalized in icons:
        return normalized
    alias = _manifest_atlas_name(_load_manifest_for_pack(pack_id).get(normalized))
    if alias in icons:
        return alias
    return None


def _choose_size_for_pack(pack_id: str, requested_size: int | None, rect: Rect) -> str:
    atlas = _load_atlas_metadata_for_pack(pack_id) or {}
    raw_sizes = atlas.get("sizes")
    config = _get_pack_config(pack_id)
    available = [int(size) for size in raw_sizes] if isinstance(raw_sizes, list) and raw_sizes else list(config["size_fallbacks"])
    x, y, w, h = rect
    del x, y
    target = int(requested_size) if requested_size is not None else int(min(float(w), float(h)))
    if target <= 0:
        target = available[0]
    return str(min(available, key=lambda candidate: abs(candidate - target)))


def icon_exists_in_pack(pack_id: str, name: str) -> bool:
    return _resolve_icon_name(pack_id, name) is not None


def draw_icon_from_pack(
    pack_id: str,
    name: str,
    rect: Rect,
    color: RGBA,
    theme: object | None = None,
    *,
    size: int | None = None,
) -> bool:
    del theme
    resolved_name = _resolve_icon_name(pack_id, name)
    if resolved_name is None:
        return False
    atlas = _load_atlas_metadata_for_pack(pack_id)
    if atlas is None:
        return False
    icon_entry = _available_icon_entries_for_pack(pack_id).get(resolved_name)
    if not isinstance(icon_entry, dict):
        return False
    size_key = _choose_size_for_pack(pack_id, size, rect)
    frame = icon_entry.get(size_key)
    if not isinstance(frame, dict):
        return False
    texture = _load_texture_for_pack(pack_id)
    if texture is None:
        return False

    rl = _rl()
    draw_texture_pro = getattr(rl, "draw_texture_pro", None)
    if not callable(draw_texture_pro):
        return False

    try:
        x, y, w, h = rect
        requested_size = int(size_key) if size is None else max(1, int(size))
        dest_size = float(min(max(1.0, float(w)), max(1.0, float(h)), float(requested_size)))
        dest = rl.Rectangle(
            float(x) + (float(w) - dest_size) / 2.0,
            float(y) + (float(h) - dest_size) / 2.0,
            dest_size,
            dest_size,
        )
        source = rl.Rectangle(
            float(frame.get("x", 0)),
            float(frame.get("y", 0)),
            float(frame.get("w", 0)),
            float(frame.get("h", 0)),
        )
        if source.width <= 0 or source.height <= 0:
            return False
        draw_texture_pro(texture, source, dest, rl.Vector2(0.0, 0.0), 0.0, to_ray_color(color))
        return True
    except Exception:
        return False


def _load_manifest() -> dict[str, Any]:
    return _load_manifest_for_pack("lucide")


def _load_atlas_metadata() -> dict[str, Any] | None:
    return _load_atlas_metadata_for_pack("lucide")


def _load_texture() -> Any | None:
    return _load_texture_for_pack("lucide")


def _available_icon_entries() -> dict[str, Any]:
    return _available_icon_entries_for_pack("lucide")


def _resolve_lucide_name(name: str) -> str | None:
    return _resolve_icon_name("lucide", name)


def icon_exists(name: str) -> bool:
    return icon_exists_in_pack("lucide", name)


def draw_icon(
    name: str,
    rect: Rect,
    color: RGBA,
    theme: object | None = None,
    *,
    size: int | None = None,
) -> bool:
    return draw_icon_from_pack("lucide", name, rect, color, theme, size=size)


def reset_cache() -> None:
    for pack_id, texture in list(_texture_cache.items()):
        unload_texture = getattr(_rl(), "unload_texture", None)
        if callable(unload_texture):
            try:
                unload_texture(texture)
            except Exception:
                pass
        _texture_cache.pop(pack_id, None)
    _manifest_cache.clear()
    _atlas_cache.clear()
