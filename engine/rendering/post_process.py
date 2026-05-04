"""
engine/rendering/post_process.py - Efectos de post-procesado serializables + pipeline real.
"""

from __future__ import annotations

from typing import Any, Optional

import pyray as rl


class PostProcessEffect:
    """Base class for post-processing effects."""

    def __init__(self, name: str = "", enabled: bool = True) -> None:
        self.name: str = str(name or self.__class__.__name__)
        self.enabled: bool = bool(enabled)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "enabled": self.enabled, "type": self.__class__.__name__}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PostProcessEffect":
        return cls(name=data.get("name", ""), enabled=data.get("enabled", True))


class BlurEffect(PostProcessEffect):
    """Box blur post-processing effect (CPU fallback)."""

    def __init__(self, radius: float = 4.0, name: str = "", enabled: bool = True) -> None:
        super().__init__(name=name or "Blur", enabled=enabled)
        self.radius: float = max(0.0, float(radius))

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["radius"] = self.radius
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BlurEffect":
        return cls(
            radius=data.get("radius", 4.0),
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
        )


class ColorCorrectEffect(PostProcessEffect):
    """Color correction post-processing effect."""

    def __init__(
        self,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        name: str = "",
        enabled: bool = True,
    ) -> None:
        super().__init__(name=name or "ColorCorrect", enabled=enabled)
        self.brightness: float = max(0.0, float(brightness))
        self.contrast: float = max(0.0, float(contrast))
        self.saturation: float = max(0.0, float(saturation))

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["brightness"] = self.brightness
        result["contrast"] = self.contrast
        result["saturation"] = self.saturation
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColorCorrectEffect":
        return cls(
            brightness=data.get("brightness", 1.0),
            contrast=data.get("contrast", 1.0),
            saturation=data.get("saturation", 1.0),
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
        )


class PostProcessPipeline:
    """Real post-processing using raylib RenderTextures. Ping-pong between two textures."""

    def __init__(self) -> None:
        self._effects: list[PostProcessEffect] = []
        self._ping_texture: Any = None
        self._pong_texture: Any = None

    def add_effect(self, effect: PostProcessEffect) -> None:
        self._effects.append(effect)

    def clear_effects(self) -> None:
        self._effects.clear()

    @property
    def effects(self) -> list[PostProcessEffect]:
        return list(self._effects)

    def process(
        self,
        source_texture: Any,
        screen_w: int,
        screen_h: int,
    ) -> Any:
        """Apply all enabled effects. Returns final texture."""
        backend_ready = bool(hasattr(rl, "is_window_ready") and rl.is_window_ready())
        if not backend_ready:
            return source_texture

        active = [e for e in self._effects if e.enabled]
        if not active:
            return source_texture

        self._ensure_ping_pong(screen_w, screen_h)

        current_src: Any = source_texture
        current_dst: Any = self._pong_texture
        use_ping = True

        for i, effect in enumerate(active):
            is_last = i == len(active) - 1
            if isinstance(effect, BlurEffect):
                current_dst = self._pong_texture if use_ping else self._ping_texture
                self._apply_blur(current_src, current_dst, effect.radius, screen_w, screen_h)
            elif isinstance(effect, ColorCorrectEffect):
                current_dst = self._pong_texture if use_ping else self._ping_texture
                self._apply_color_correct(current_src, current_dst, effect, screen_w, screen_h)
            else:
                continue

            current_src = current_dst
            use_ping = not use_ping

        return current_src

    def _ensure_ping_pong(self, width: int, height: int) -> None:
        safe_w = max(1, int(width))
        safe_h = max(1, int(height))
        if self._ping_texture is None:
            self._ping_texture = rl.load_render_texture(safe_w, safe_h)
        elif hasattr(self._ping_texture, "texture"):
            tex = self._ping_texture.texture
            if tex.width != safe_w or tex.height != safe_h:
                rl.unload_render_texture(self._ping_texture)
                self._ping_texture = rl.load_render_texture(safe_w, safe_h)
        if self._pong_texture is None:
            self._pong_texture = rl.load_render_texture(safe_w, safe_h)
        elif hasattr(self._pong_texture, "texture"):
            tex = self._pong_texture.texture
            if tex.width != safe_w or tex.height != safe_h:
                rl.unload_render_texture(self._pong_texture)
                self._pong_texture = rl.load_render_texture(safe_w, safe_h)

    def _apply_blur(self, src: Any, dst: Any, radius: float, screen_w: int, screen_h: int) -> None:
        """Box blur via CPU: sample source, draw blurred to destination."""
        rl.begin_texture_mode(dst)
        rl.clear_background(rl.BLANK)

        tex = self._extract_texture(src)
        if tex is None:
            rl.end_texture_mode()
            return

        r = max(1, int(radius))
        step = max(1, r // 2)
        alpha_total = 0.0

        for dy in range(-r, r + 1, step):
            for dx in range(-r, r + 1, step):
                dist = abs(dx) + abs(dy)
                alpha = 1.0 / (1.0 + float(dist) / max(1, r))
                alpha_total += alpha
                color = rl.Color(255, 255, 255, min(255, int(255 * alpha / (r * 2 + 1))))
                source_rect = rl.Rectangle(0, 0, float(tex.width), -float(tex.height))
                dest_rect = rl.Rectangle(float(dx), float(dy), float(screen_w), float(screen_h))
                rl.draw_texture_pro(tex, source_rect, dest_rect, rl.Vector2(0, 0), 0.0, color)

        rl.end_texture_mode()

    def _apply_color_correct(
        self, src: Any, dst: Any, effect: ColorCorrectEffect, screen_w: int, screen_h: int
    ) -> None:
        """Apply brightness/contrast/saturation via tint modulation."""
        rl.begin_texture_mode(dst)
        rl.clear_background(rl.BLANK)

        tex = self._extract_texture(src)
        if tex is None:
            rl.end_texture_mode()
            return

        b = effect.brightness
        c = effect.contrast
        s = effect.saturation

        r_val = min(255, int(255 * b * c))
        g_val = min(255, int(255 * b * c * s))
        b_val = min(255, int(255 * b * c * (2.0 - s)))
        a_val = min(255, int(255 * b))

        tint = rl.Color(
            max(0, r_val),
            max(0, g_val),
            max(0, b_val),
            max(0, a_val),
        )
        source_rect = rl.Rectangle(0, 0, float(tex.width), -float(tex.height))
        dest_rect = rl.Rectangle(0, 0, float(screen_w), float(screen_h))
        rl.draw_texture_pro(tex, source_rect, dest_rect, rl.Vector2(0, 0), 0.0, tint)

        rl.end_texture_mode()

    @staticmethod
    def _extract_texture(rt_or_tex: Any) -> Any:
        if rt_or_tex is None:
            return None
        if hasattr(rt_or_tex, "texture"):
            return rt_or_tex.texture
        if hasattr(rt_or_tex, "id") and hasattr(rt_or_tex, "width"):
            return rt_or_tex
        return None

    def cleanup(self) -> None:
        if self._ping_texture is not None:
            try:
                rl.unload_render_texture(self._ping_texture)
            except Exception:
                pass
            self._ping_texture = None
        if self._pong_texture is not None:
            try:
                rl.unload_render_texture(self._pong_texture)
            except Exception:
                pass
            self._pong_texture = None
        self._effects.clear()
