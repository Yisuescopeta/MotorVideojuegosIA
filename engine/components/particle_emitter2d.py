"""
engine/components/particle_emitter2d.py - Emisor de particulas CPU 2D (equivalente Godot CPUParticles2D).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple, Union, cast

from engine.assets.asset_reference import build_asset_reference, clone_asset_reference, normalize_asset_reference
from engine.ecs.component import Component

_AssetRefInput = Union[str, dict[str, str], None]

DEFAULT_COLOR: Tuple[int, int, int, int] = (255, 255, 255, 255)
DEFAULT_DIRECTION: Tuple[float, float] = (1.0, 0.0)
DEFAULT_GRAVITY: Tuple[float, float] = (0.0, 0.0)
DEFAULT_RANGE: Tuple[float, float] = (0.0, 0.0)
DEFAULT_RECT_EXTENTS: Tuple[float, float] = (1.0, 1.0)

VALID_SHAPES = {"point", "sphere", "sphere_surface", "rectangle"}


@dataclass
class ColorRampStop:
    """Parada de gradiente de color: posicion 0-1 y color RGBA."""
    position: float = 0.0
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)

    def to_dict(self) -> dict[str, Any]:
        return {"position": self.position, "color": list(self.color)}

    @classmethod
    def from_dict(cls, data: Any) -> "ColorRampStop":
        if not isinstance(data, dict):
            return cls()
        color_data = data.get("color", list(DEFAULT_COLOR))
        if isinstance(color_data, (tuple, list)) and len(color_data) >= 4:
            color = (max(0, min(255, int(color_data[0]))), max(0, min(255, int(color_data[1]))),
                      max(0, min(255, int(color_data[2]))), max(0, min(255, int(color_data[3]))))
        else:
            color = DEFAULT_COLOR
        return cls(position=float(data.get("position", 0.0)), color=color)


def _clamp_range(value: Any) -> Tuple[float, float]:
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        return (float(value[0]), float(value[1]))
    if isinstance(value, (int, float)):
        v = float(value)
        return (v, v)
    return (0.0, 0.0)


def _clamp_tuple2(value: Any) -> Tuple[float, float]:
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        return (float(value[0]), float(value[1]))
    return (0.0, 0.0)


def _clamp_color_tuple(value: Any) -> Tuple[int, int, int, int]:
    if isinstance(value, (tuple, list)) and len(value) >= 4:
        return (max(0, min(255, int(value[0]))), max(0, min(255, int(value[1]))),
                max(0, min(255, int(value[2]))), max(0, min(255, int(value[3]))))
    if isinstance(value, str) and value.startswith("#"):
        try:
            h = value.lstrip("#")
            if len(h) == 6:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
            if len(h) == 8:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16))
        except (ValueError, IndexError):
            pass
    return DEFAULT_COLOR


def _clamp_shape(value: Any) -> str:
    normalized = str(value or "point").strip().lower()
    return normalized if normalized in VALID_SHAPES else "point"


class ParticleEmitter2D(Component):
    """Emisor de particulas 2D calculadas en CPU.

    Configuracion serializable equivalente a CPUParticles2D de Godot.
    Usa tuplas (min, max) para parametros con rango.
    """

    def __init__(
        self,
        amount: int = 64,
        lifetime: float = 1.0,
        lifetime_randomness: float = 0.0,
        speed_scale: float = 1.0,
        explosiveness: float = 0.0,
        one_shot: bool = False,
        emitting: bool = True,
        local_coords: bool = False,
        preprocess: float = 0.0,
        emission_shape: str = "point",
        emission_rect_extents: Optional[Tuple[float, float]] = None,
        emission_sphere_radius: float = 1.0,
        direction: Optional[Tuple[float, float]] = None,
        spread: float = 45.0,
        initial_velocity: Optional[Tuple[float, float]] = None,
        angular_velocity: Optional[Tuple[float, float]] = None,
        linear_accel: Optional[Tuple[float, float]] = None,
        radial_accel: Optional[Tuple[float, float]] = None,
        tangential_accel: Optional[Tuple[float, float]] = None,
        damping: Optional[Tuple[float, float]] = None,
        angle: Optional[Tuple[float, float]] = None,
        scale_amount: Optional[Tuple[float, float]] = None,
        color: Optional[Tuple[int, int, int, int]] = None,
        texture: _AssetRefInput = None,
        texture_path: str = "",
        color_ramp: Optional[List[ColorRampStop]] = None,
        gravity: Optional[Tuple[float, float]] = None,
        enabled: bool = True,
        seed: int = 0,
    ) -> None:
        self.enabled: bool = enabled
        self.amount: int = max(1, int(amount))
        self.lifetime: float = max(0.01, float(lifetime))
        self.lifetime_randomness: float = max(0.0, min(1.0, float(lifetime_randomness)))
        self.speed_scale: float = float(speed_scale)
        self.explosiveness: float = max(0.0, min(1.0, float(explosiveness)))
        self.one_shot: bool = bool(one_shot)
        self.emitting: bool = bool(emitting)
        self.local_coords: bool = bool(local_coords)
        self.preprocess: float = max(0.0, float(preprocess))
        self.emission_shape: str = _clamp_shape(emission_shape)
        self.emission_rect_extents: Tuple[float, float] = emission_rect_extents or DEFAULT_RECT_EXTENTS
        self.emission_sphere_radius: float = max(0.0, float(emission_sphere_radius))
        self.direction: Tuple[float, float] = direction or DEFAULT_DIRECTION
        self.spread: float = max(0.0, min(180.0, float(spread)))
        self.initial_velocity: Tuple[float, float] = _clamp_range(initial_velocity)
        self.angular_velocity: Tuple[float, float] = _clamp_range(angular_velocity)
        self.linear_accel: Tuple[float, float] = _clamp_range(linear_accel)
        self.radial_accel: Tuple[float, float] = _clamp_range(radial_accel)
        self.tangential_accel: Tuple[float, float] = _clamp_range(tangential_accel)
        self.damping: Tuple[float, float] = _clamp_range(damping)
        self.angle: Tuple[float, float] = _clamp_range(angle)
        self.scale_amount: Tuple[float, float] = _clamp_range(scale_amount)
        self.color: Tuple[int, int, int, int] = _clamp_color_tuple(color) if color is not None else DEFAULT_COLOR
        self.texture = normalize_asset_reference(texture if texture is not None else texture_path)
        self.texture_path: str = self.texture.get("path", "")
        self.color_ramp: List[ColorRampStop] = list(color_ramp) if color_ramp else []
        self.gravity: Tuple[float, float] = gravity if gravity is not None else DEFAULT_GRAVITY
        self.seed: int = int(seed)

    def get_texture_reference(self) -> dict[str, str]:
        return clone_asset_reference(self.texture)

    def sync_texture_reference(self, reference: _AssetRefInput) -> None:
        self.texture = normalize_asset_reference(reference)
        self.texture_path = self.texture.get("path", "")

    @staticmethod
    def _serialize_range(r: Tuple[float, float]) -> list[float]:
        return [r[0], r[1]]

    @staticmethod
    def _serialize_tuple2(t: Tuple[float, float]) -> list[float]:
        return [t[0], t[1]]

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "enabled": self.enabled,
            "amount": self.amount,
            "lifetime": self.lifetime,
            "lifetime_randomness": self.lifetime_randomness,
            "speed_scale": self.speed_scale,
            "explosiveness": self.explosiveness,
            "one_shot": self.one_shot,
            "emitting": self.emitting,
            "local_coords": self.local_coords,
            "preprocess": self.preprocess,
            "emission_shape": self.emission_shape,
            "emission_rect_extents": self._serialize_tuple2(self.emission_rect_extents),
            "emission_sphere_radius": self.emission_sphere_radius,
            "direction": self._serialize_tuple2(self.direction),
            "spread": self.spread,
            "initial_velocity": self._serialize_range(self.initial_velocity),
            "angular_velocity": self._serialize_range(self.angular_velocity),
            "linear_accel": self._serialize_range(self.linear_accel),
            "radial_accel": self._serialize_range(self.radial_accel),
            "tangential_accel": self._serialize_range(self.tangential_accel),
            "damping": self._serialize_range(self.damping),
            "angle": self._serialize_range(self.angle),
            "scale_amount": self._serialize_range(self.scale_amount),
            "color": list(self.color),
            "texture": self.get_texture_reference(),
            "texture_path": self.texture_path,
            "gravity": self._serialize_tuple2(self.gravity),
            "seed": self.seed,
        }
        if self.color_ramp:
            result["color_ramp"] = [stop.to_dict() for stop in self.color_ramp]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ParticleEmitter2D":
        color = data.get("color", list(DEFAULT_COLOR))
        texture_ref = normalize_asset_reference(data.get("texture"))
        texture_path = cast(str, data.get("texture_path", ""))
        if texture_path and texture_ref.get("path") != texture_path:
            texture_ref = build_asset_reference(texture_path, texture_ref.get("guid", ""))

        color_ramp_data = data.get("color_ramp")
        color_ramp = (
            [ColorRampStop.from_dict(s) for s in color_ramp_data]
            if isinstance(color_ramp_data, list)
            else []
        )

        def _read_range(key: str) -> Tuple[float, float]:
            raw = data.get(key, [0.0, 0.0])
            if isinstance(raw, (tuple, list)) and len(raw) >= 2:
                return (float(raw[0]), float(raw[1]))
            if isinstance(raw, (int, float)):
                v = float(raw)
                return (v, v)
            return (0.0, 0.0)

        component = cls(
            amount=cast(int, data.get("amount", 64)),
            lifetime=cast(float, data.get("lifetime", 1.0)),
            lifetime_randomness=cast(float, data.get("lifetime_randomness", 0.0)),
            speed_scale=cast(float, data.get("speed_scale", 1.0)),
            explosiveness=cast(float, data.get("explosiveness", 0.0)),
            one_shot=cast(bool, data.get("one_shot", False)),
            emitting=cast(bool, data.get("emitting", True)),
            local_coords=cast(bool, data.get("local_coords", False)),
            preprocess=cast(float, data.get("preprocess", 0.0)),
            emission_shape=cast(str, data.get("emission_shape", "point")),
            emission_rect_extents=_clamp_tuple2(data.get("emission_rect_extents", DEFAULT_RECT_EXTENTS)),
            emission_sphere_radius=cast(float, data.get("emission_sphere_radius", 1.0)),
            direction=_clamp_tuple2(data.get("direction", DEFAULT_DIRECTION)),
            spread=cast(float, data.get("spread", 45.0)),
            initial_velocity=_read_range("initial_velocity"),
            angular_velocity=_read_range("angular_velocity"),
            linear_accel=_read_range("linear_accel"),
            radial_accel=_read_range("radial_accel"),
            tangential_accel=_read_range("tangential_accel"),
            damping=_read_range("damping"),
            angle=_read_range("angle"),
            scale_amount=_read_range("scale_amount"),
            color=cast(Tuple[int, int, int, int], tuple(color) if isinstance(color, (tuple, list)) else DEFAULT_COLOR),
            texture=texture_ref,
            texture_path=texture_path,
            color_ramp=color_ramp,
            gravity=_clamp_tuple2(data.get("gravity", DEFAULT_GRAVITY)),
            seed=cast(int, data.get("seed", 0)),
        )
        component.enabled = cast(bool, data.get("enabled", True))
        return component
