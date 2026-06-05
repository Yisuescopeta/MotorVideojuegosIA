"""Thumbnail rendering helpers for Project panel assets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import pyray as rl
from engine.editor.ui.icons import ICON_AUDIO, ICON_MATERIAL, ICON_PREFAB, ICON_SCENE, ICON_SCRIPT, ICON_UNKNOWN, draw_icon


@dataclass(frozen=True)
class ThumbnailInfo:
    icon_type: str
    color_rgb: Tuple[int, int, int]
    label: str
    uses_real_texture: bool = False


class ThumbnailProvider:
    IMAGE_EXTENSIONS: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tga", ".webp")
    SCRIPT_EXTENSIONS: tuple[str, ...] = (".py", ".gd", ".lua", ".js", ".ts")
    AUDIO_EXTENSIONS: tuple[str, ...] = (".wav", ".ogg", ".mp3", ".flac", ".xm", ".mod")
    MATERIAL_EXTENSIONS: tuple[str, ...] = (".mat", ".material", ".mtl")

    ICONS: Dict[str, ThumbnailInfo] = {
        "folder": ThumbnailInfo("folder", (220, 200, 100), "DIR"),
        "image": ThumbnailInfo("image", (118, 158, 223), "IMG"),
        "scene": ThumbnailInfo(ICON_SCENE, (120, 190, 130), "SCN"),
        "prefab": ThumbnailInfo(ICON_PREFAB, (176, 135, 222), "PFB"),
        "script": ThumbnailInfo(ICON_SCRIPT, (226, 180, 96), "PY"),
        "audio": ThumbnailInfo(ICON_AUDIO, (104, 190, 205), "AUD"),
        "material": ThumbnailInfo(ICON_MATERIAL, (205, 150, 110), "MAT"),
        "unknown": ThumbnailInfo(ICON_UNKNOWN, (160, 160, 160), "?"),
    }

    def __init__(self) -> None:
        self._textures: Dict[str, Any] = {}

    def get_thumbnail_info(self, path: str, asset_kind: str = "", entry_type: str = "file") -> ThumbnailInfo:
        icon_type = self._icon_type_for(path, asset_kind, entry_type)
        base = self.ICONS.get(icon_type, self.ICONS["unknown"])
        absolute_path = os.path.abspath(path) if path else ""
        uses_real_texture = icon_type == "image" and absolute_path in self._textures
        return ThumbnailInfo(base.icon_type, base.color_rgb, base.label, uses_real_texture)

    def draw_item_icon(self, rect: rl.Rectangle, item: Dict[str, Any]) -> ThumbnailInfo:
        path = str(item.get("absolute_path", "") or "")
        asset_kind = str(item.get("asset_kind", "") or "")
        entry_type = str(item.get("entry_type", "file") or "file")
        info = self.get_thumbnail_info(path, asset_kind=asset_kind, entry_type=entry_type)
        if info.icon_type == "image":
            texture = self._get_texture(path)
            if texture is not None and self._draw_texture(rect, texture):
                return ThumbnailInfo(info.icon_type, info.color_rgb, info.label, True)
        self._draw_typed_icon(rect, info)
        return info

    def clear(self) -> None:
        unload = getattr(rl, "unload_texture", None)
        for texture in list(self._textures.values()):
            if callable(unload):
                try:
                    unload(texture)
                except Exception:
                    pass
        self._textures.clear()

    def _get_texture(self, path: str) -> Optional[Any]:
        if not self._is_image_path(path) or not self._is_window_ready():
            return None
        absolute_path = os.path.abspath(path)
        if absolute_path in self._textures:
            return self._textures[absolute_path]
        load_texture = getattr(rl, "load_texture", None)
        if not callable(load_texture):
            return None
        try:
            texture = load_texture(absolute_path)
        except Exception:
            return None
        if texture is None:
            return None
        is_ready = getattr(rl, "is_texture_ready", None)
        if callable(is_ready):
            try:
                if not is_ready(texture):
                    return None
            except Exception:
                return None
        self._textures[absolute_path] = texture
        return texture

    def _draw_texture(self, rect: rl.Rectangle, texture: Any) -> bool:
        draw_texture_pro = getattr(rl, "draw_texture_pro", None)
        if not callable(draw_texture_pro):
            return False
        width = float(getattr(texture, "width", 0) or 0)
        height = float(getattr(texture, "height", 0) or 0)
        if width <= 0 or height <= 0:
            return False
        scale = min(float(rect.width) / width, float(rect.height) / height)
        dest_w = max(1.0, width * scale)
        dest_h = max(1.0, height * scale)
        dest = rl.Rectangle(rect.x + (rect.width - dest_w) / 2, rect.y + (rect.height - dest_h) / 2, dest_w, dest_h)
        source = rl.Rectangle(0, 0, width, height)
        try:
            draw_texture_pro(texture, source, dest, rl.Vector2(0, 0), 0.0, rl.WHITE)
            return True
        except Exception:
            return False

    def _draw_typed_icon(self, rect: rl.Rectangle, info: ThumbnailInfo) -> None:
        color = rl.Color(*info.color_rgb, 255)
        dark = rl.Color(75, 75, 75, 255)
        rl.draw_rectangle_rec(rect, color)
        icon_name = info.icon_type
        if icon_name == "image":
            icon_name = "image"
        draw_icon(
            icon_name,
            (float(rect.x), float(rect.y), float(rect.width), float(rect.height)),
            (245, 245, 245, 255),
            size=min(24, int(min(rect.width, rect.height))),
        )
        if info.icon_type != "unknown" and rect.width >= 24 and rect.height >= 18:
            rl.draw_text(info.label, int(rect.x + 3), int(rect.y + rect.height - 11), 8, rl.Color(245, 245, 245, 255))
        rl.draw_rectangle_lines_ex(rect, 1, dark)

    def _icon_type_for(self, path: str, asset_kind: str, entry_type: str) -> str:
        kind = str(asset_kind or "").strip().lower()
        if entry_type == "dir" or kind == "folder":
            return "folder"
        if kind in {"texture", "sprite", "sprite_sheet", "image"} or self._is_image_path(path):
            return "image"
        if kind in {"scene", "scene_data"} or self._is_scene_path(path):
            return "scene"
        if kind == "prefab" or str(path).lower().endswith(".prefab"):
            return "prefab"
        if kind == "script" or str(path).lower().endswith(self.SCRIPT_EXTENSIONS):
            return "script"
        if kind == "audio" or str(path).lower().endswith(self.AUDIO_EXTENSIONS):
            return "audio"
        if kind == "material" or str(path).lower().endswith(self.MATERIAL_EXTENSIONS):
            return "material"
        return "unknown"

    def _is_window_ready(self) -> bool:
        is_window_ready = getattr(rl, "is_window_ready", None)
        if not callable(is_window_ready):
            return False
        try:
            return bool(is_window_ready())
        except Exception:
            return False

    def _is_image_path(self, path: str) -> bool:
        return str(path).lower().endswith(self.IMAGE_EXTENSIONS)

    def _is_scene_path(self, path: str) -> bool:
        normalized = str(path).replace("\\", "/").lower()
        return normalized.endswith(".json") and "/levels/" in f"/{normalized}"
