"""
engine/components/line2d.py - Componente de renderizado de linea 2D.

PROPOSITO:
    Define una linea 2D con grosor, color, multiples puntos, joint modes
    y opcion cerrada. Adaptado de Line2D de Godot.

PROPIEDADES:
    - enabled (bool): Si la linea se renderiza
    - points (list[list[float]]): Lista de vertices [[x, y], ...]
    - width (float): Grosor de la linea en pixeles
    - color (tuple[int,int,int,int]): Color RGBA 0-255
    - joint_mode (str): Modo de union: 'sharp', 'bevel', 'round'
    - closed (bool): Si conecta ultimo punto con primero
    - cap_mode (str): Modo de extremos: 'none', 'round'

SERIALIZACION JSON:
    {
        "enabled": true,
        "points": [[0.0, 0.0], [100.0, 100.0]],
        "width": 2.0,
        "color": [255, 255, 255, 255],
        "joint_mode": "sharp",
        "closed": false,
        "cap_mode": "none"
    }
"""

from __future__ import annotations

from typing import Any, Union

from engine.ecs.component import Component


class Line2D(Component):
    """Componente para renderizar una linea 2D con grosor."""

    VALID_JOINT_MODES = ("sharp", "bevel", "round")
    VALID_CAP_MODES = ("none", "round")

    def __init__(
        self,
        points: list[list[float]] | None = None,
        width: float = 2.0,
        color: tuple[int, int, int, int] = (255, 255, 255, 255),
        joint_mode: str = "sharp",
        closed: bool = False,
        cap_mode: str = "none",
    ) -> None:
        self.enabled: bool = True
        self.points: list[list[float]] = [list(p) for p in (points or [])]
        self.width: float = max(0.0, float(width))
        self.joint_mode: str = joint_mode if joint_mode in self.VALID_JOINT_MODES else "sharp"
        self.closed: bool = bool(closed)
        self.cap_mode: str = cap_mode if cap_mode in self.VALID_CAP_MODES else "none"
        self._color: tuple[int, int, int, int] = (255, 255, 255, 255)
        self.color = color

    @property
    def color(self) -> tuple[int, int, int, int]:
        return self._color

    @color.setter
    def color(self, value: Union[tuple[int, ...], list[int]]) -> None:
        self._color = self._clamp_color(value)

    @staticmethod
    def _clamp_color(value: object) -> tuple[int, int, int, int]:
        if not isinstance(value, (tuple, list)):
            return (255, 255, 255, 255)
        seq = list(value)
        while len(seq) < 4:
            seq.append(255)
        seq = seq[:4]
        try:
            return tuple(max(0, min(255, int(v))) for v in seq)
        except (ValueError, TypeError):
            return (255, 255, 255, 255)

    def add_point(self, x: float, y: float) -> None:
        self.points.append([float(x), float(y)])

    def remove_point(self, index: int) -> None:
        if 0 <= index < len(self.points):
            self.points.pop(index)

    def get_point(self, index: int) -> tuple[float, float] | None:
        if 0 <= index < len(self.points):
            pt = self.points[index]
            return (float(pt[0]), float(pt[1]))
        return None

    def set_point(self, index: int, x: float, y: float) -> None:
        if 0 <= index < len(self.points):
            self.points[index] = [float(x), float(y)]

    def clear_points(self) -> None:
        self.points.clear()

    @property
    def point_count(self) -> int:
        return len(self.points)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "points": [list(p) for p in self.points],
            "width": self.width,
            "color": list(self.color),
            "joint_mode": self.joint_mode,
            "closed": self.closed,
            "cap_mode": self.cap_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Line2D":
        raw_points = data.get("points", [])
        points: list[list[float]] = []
        if isinstance(raw_points, list):
            points = [[float(p[0]), float(p[1])] for p in raw_points if isinstance(p, (list, tuple)) and len(p) >= 2]

        raw_color = data.get("color", [255, 255, 255, 255])
        joint_mode = str(data.get("joint_mode", "sharp"))
        cap_mode = str(data.get("cap_mode", "none"))

        component = cls(
            points=points,
            width=float(data.get("width", 2.0)),
            color=tuple(raw_color) if isinstance(raw_color, (tuple, list)) else (255, 255, 255, 255),
            joint_mode=joint_mode,
            closed=bool(data.get("closed", False)),
            cap_mode=cap_mode,
        )
        component.enabled = bool(data.get("enabled", True))
        return component
