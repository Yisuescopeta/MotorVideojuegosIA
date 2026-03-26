from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pyray as rl


@dataclass
class RenderTargetHandle:
    name: str
    width: int
    height: int
    render_texture: Any = None
    dry_run: bool = True


class RenderTargetPool:
    """Gestiona render targets con fallback seguro cuando no hay backend grafico."""

    def __init__(self) -> None:
        self._targets: dict[str, RenderTargetHandle] = {}
        self._active_target: str = ""
        self._frame_metrics: dict[str, int] = {
            "passes": 0,
            "composites": 0,
            "creates": 0,
            "resizes": 0,
        }

    def begin_frame(self) -> None:
        self._frame_metrics = {
            "passes": 0,
            "composites": 0,
            "creates": 0,
            "resizes": 0,
        }

    def ensure(self, name: str, width: int, height: int) -> RenderTargetHandle:
        safe_width = max(1, int(width))
        safe_height = max(1, int(height))
        current = self._targets.get(name)
        backend_ready = bool(hasattr(rl, "is_window_ready") and rl.is_window_ready())
        if current is not None and current.width == safe_width and current.height == safe_height and current.dry_run == (not backend_ready):
            return current

        if current is not None and current.render_texture is not None:
            rl.unload_render_texture(current.render_texture)
            self._frame_metrics["resizes"] += 1
        elif current is None:
            self._frame_metrics["creates"] += 1

        render_texture = None
        dry_run = not backend_ready
        if backend_ready:
            render_texture = rl.load_render_texture(safe_width, safe_height)

        handle = RenderTargetHandle(
            name=name,
            width=safe_width,
            height=safe_height,
            render_texture=render_texture,
            dry_run=dry_run,
        )
        self._targets[name] = handle
        return handle

    def begin(self, name: str, width: int, height: int, clear_color: Any) -> RenderTargetHandle:
        handle = self.ensure(name, width, height)
        self._frame_metrics["passes"] += 1
        self._active_target = handle.name
        if handle.render_texture is not None:
            rl.begin_texture_mode(handle.render_texture)
            rl.clear_background(clear_color)
        return handle

    def end(self) -> None:
        if not self._active_target:
            return
        handle = self._targets.get(self._active_target)
        self._active_target = ""
        if handle is not None and handle.render_texture is not None:
            rl.end_texture_mode()

    def compose(self, name: str, destination: Any, tint: Any = None) -> None:
        handle = self._targets.get(name)
        if handle is None:
            return
        self._frame_metrics["composites"] += 1
        if handle.render_texture is None:
            return
        texture = handle.render_texture.texture
        source = rl.Rectangle(0, 0, texture.width, -texture.height)
        rl.draw_texture_pro(texture, source, destination, rl.Vector2(0, 0), 0.0, tint or rl.WHITE)

    def get(self, name: str) -> Optional[RenderTargetHandle]:
        return self._targets.get(name)

    def get_frame_metrics(self) -> dict[str, int]:
        return dict(self._frame_metrics)

    def unload_all(self) -> None:
        for handle in self._targets.values():
            if handle.render_texture is not None:
                rl.unload_render_texture(handle.render_texture)
        self._targets.clear()
        self._active_target = ""
