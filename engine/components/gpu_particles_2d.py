"""engine/components/gpu_particles_2d.py — GPUParticles2D MVP (Godot parity).
GPU-based particles — MVP wraps CPU-friendly settings.
"""

from __future__ import annotations

from typing import Any

from engine.ecs.component import Component


class GPUParticles2D(Component):
    """GPU-based particles (MVP: wraps CPU particles with GPU-friendly settings)."""

    def __init__(
        self,
        emitting: bool = True,
        amount: int = 32,
        lifetime: float = 1.0,
        speed_scale: float = 1.0,
        one_shot: bool = False,
        preprocess: float = 0.0,
        explosiveness: float = 0.0,
        randomness: float = 0.0,
        texture_path: str = "",
        local_coords: bool = True,
        draw_order: str = "index",
        fixed_fps: int = 0,
        fract_delta: bool = True,
        sub_emitter_path: str = "",
    ) -> None:
        self.enabled: bool = True
        self.emitting: bool = bool(emitting)
        self.amount: int = max(1, int(amount))
        self.lifetime: float = max(0.01, float(lifetime))
        self.speed_scale: float = float(speed_scale)
        self.one_shot: bool = bool(one_shot)
        self.preprocess: float = max(0.0, float(preprocess))
        self.explosiveness: float = max(0.0, min(1.0, float(explosiveness)))
        self.randomness: float = max(0.0, min(1.0, float(randomness)))
        self.texture_path: str = str(texture_path)
        self.local_coords: bool = bool(local_coords)
        self.draw_order: str = (
            str(draw_order)
            if str(draw_order) in ("index", "lifetime", "reverse_lifetime")
            else "index"
        )
        self.fixed_fps: int = max(0, int(fixed_fps))
        self.fract_delta: bool = bool(fract_delta)
        self.sub_emitter_path: str = str(sub_emitter_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "emitting": self.emitting,
            "amount": self.amount,
            "lifetime": self.lifetime,
            "speed_scale": self.speed_scale,
            "one_shot": self.one_shot,
            "preprocess": self.preprocess,
            "explosiveness": self.explosiveness,
            "randomness": self.randomness,
            "texture_path": self.texture_path,
            "local_coords": self.local_coords,
            "draw_order": self.draw_order,
            "fixed_fps": self.fixed_fps,
            "fract_delta": self.fract_delta,
            "sub_emitter_path": self.sub_emitter_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GPUParticles2D":
        component = cls(
            emitting=data.get("emitting", True),
            amount=data.get("amount", 32),
            lifetime=data.get("lifetime", 1.0),
            speed_scale=data.get("speed_scale", 1.0),
            one_shot=data.get("one_shot", False),
            preprocess=data.get("preprocess", 0.0),
            explosiveness=data.get("explosiveness", 0.0),
            randomness=data.get("randomness", 0.0),
            texture_path=data.get("texture_path", ""),
            local_coords=data.get("local_coords", True),
            draw_order=data.get("draw_order", "index"),
            fixed_fps=data.get("fixed_fps", 0),
            fract_delta=data.get("fract_delta", True),
            sub_emitter_path=data.get("sub_emitter_path", ""),
        )
        component.enabled = data.get("enabled", True)
        return component
