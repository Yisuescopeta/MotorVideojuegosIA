"""
engine/components/polygon2d.py - Componente de renderizado de poligono 2D.

PROPOSITO:
    Define una forma poligonal rellena para renderizado 2D.
    Soporta color solido y textura con triangle fan.
    Adaptado de Polygon2D de Godot.

PROPIEDADES:
    - enabled (bool): Si el poligono se renderiza
    - points (list[list[float]]): Lista de vertices [[x, y], ...]
    - color (tuple[int,int,int,int]): Color RGBA 0-255
    - texture (dict): Asset reference para textura
    - texture_path (str): Ruta de la textura
    - offset_x (float): Desplazamiento horizontal desde Transform
    - offset_y (float): Desplazamiento vertical desde Transform

SERIALIZACION JSON:
    {
        "enabled": true,
        "points": [[0.0, -50.0], [50.0, 50.0], [-50.0, 50.0]],
        "color": [255, 128, 0, 255],
        "texture": {"guid": "", "path": ""},
        "texture_path": "",
        "offset_x": 0.0,
        "offset_y": 0.0
    }
"""

from __future__ import annotations

from typing import Any, Tuple, Union, cast

from engine.assets.asset_reference import build_asset_reference, clone_asset_reference, normalize_asset_reference
from engine.ecs.component import Component

_AssetRefInput = Union[str, dict[str, str], None]


class Polygon2D(Component):
    """Componente para renderizar un poligono 2D relleno."""

    def __init__(
        self,
        points: list[list[float]] | None = None,
        color: Tuple[int, int, int, int] = (255, 255, 255, 255),
        texture: _AssetRefInput = None,
        texture_path: str = "",
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        uvs: list[tuple[float, float]] | None = None,
        internal_vertices: int = 0,
    ) -> None:
        self.enabled: bool = True
        self.points: list[list[float]] = [list(p) for p in (points or [])]
        self.texture = normalize_asset_reference(texture if texture is not None else texture_path)
        self.texture_path: str = self.texture.get("path", "")
        self.offset_x: float = offset_x
        self.offset_y: float = offset_y
        self.uvs: list[tuple[float, float]] = [tuple(uv) for uv in (uvs or [])]
        self.internal_vertices: int = int(internal_vertices)
        self._color: Tuple[int, int, int, int] = (255, 255, 255, 255)
        self.color = color

    @property
    def color(self) -> Tuple[int, int, int, int]:
        return self._color

    @color.setter
    def color(self, value: Union[Tuple[int, ...], list[int]]) -> None:
        self._color = self._clamp_color(value)

    @staticmethod
    def _clamp_color(value: Union[Tuple[int, ...], list[int], object]) -> Tuple[int, int, int, int]:
        from engine.editor.console_panel import log_warn

        if not isinstance(value, (tuple, list)):
            log_warn(
                f"Polygon2D color: valor invalido (esperado tuple/list, recibido {type(value).__name__}); usando color por defecto"
            )
            return (255, 255, 255, 255)
        seq = list(value)
        while len(seq) < 4:
            seq.append(255)
        seq = seq[:4]
        try:
            r, g, b, a = (max(0, min(255, int(v))) for v in seq)
            return (r, g, b, a)
        except (ValueError, TypeError):
            log_warn("Polygon2D color: error al convertir valores a int; usando color por defecto")
            return (255, 255, 255, 255)

    def get_texture_reference(self) -> dict[str, str]:
        return clone_asset_reference(self.texture)

    def sync_texture_reference(self, reference: _AssetRefInput) -> None:
        self.texture = normalize_asset_reference(reference)
        self.texture_path = self.texture.get("path", "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "points": [list(p) for p in self.points],
            "color": list(self.color),
            "texture": self.get_texture_reference(),
            "texture_path": self.texture_path,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "uvs": [list(uv) for uv in self.uvs],
            "internal_vertices": self.internal_vertices,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Polygon2D":
        raw_points = data.get("points", [])
        points: list[list[float]] = []
        if isinstance(raw_points, list):
            points = [[float(p[0]), float(p[1])] for p in raw_points if isinstance(p, (list, tuple)) and len(p) >= 2]

        color = data.get("color", [255, 255, 255, 255])
        texture_ref = normalize_asset_reference(data.get("texture"))
        texture_path = cast(str, data.get("texture_path", ""))
        if texture_path and texture_ref.get("path") != texture_path:
            texture_ref = build_asset_reference(texture_path, texture_ref.get("guid", ""))

        raw_uvs = data.get("uvs", [])
        uvs: list[tuple[float, float]] = []
        if isinstance(raw_uvs, list):
            uvs = [tuple(float(v) for v in uv) for uv in raw_uvs if isinstance(uv, (list, tuple)) and len(uv) >= 2]

        component = cls(
            points=points,
            color=tuple(color) if isinstance(color, (tuple, list)) else (255, 255, 255, 255),  # type: ignore[arg-type]
            texture=texture_ref,
            texture_path=texture_path,
            offset_x=cast(float, data.get("offset_x", 0.0)),
            offset_y=cast(float, data.get("offset_y", 0.0)),
            uvs=uvs,
            internal_vertices=cast(int, data.get("internal_vertices", 0)),
        )
        component.enabled = cast(bool, data.get("enabled", True))
        return component
