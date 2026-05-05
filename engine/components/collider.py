"""
engine/components/collider.py - Componente de colisión AABB

PROPÓSITO:
    Define un área de colisión. Soporta múltiples tipos de forma:
    - box: rectángulo alineado a ejes (AABB)
    - circle: círculo
    - polygon: polígono convexo
    - capsule: cápsula vertical (rectángulo con extremos semicirculares)

PROPIEDADES:
    - width (float): Ancho del área de colisión
    - height (float): Alto del área de colisión
    - offset_x (float): Desplazamiento horizontal desde el Transform
    - offset_y (float): Desplazamiento vertical desde el Transform
    - is_trigger (bool): Si es True, detecta pero no bloquea físicamente
    - shape_type (str): "box", "circle", "polygon", "capsule"
    - radius (float): Radio para circle/capsule
    - capsule_height (float): Altura de la sección rectangular de la cápsula

EJEMPLO DE USO:
    collider = Collider(width=32, height=48)
    entity.add_component(collider)

SERIALIZACIÓN JSON:
    {
        "width": 32,
        "height": 48,
        "offset_x": 0,
        "offset_y": 0,
        "is_trigger": false,
        "shape_type": "box",
        "radius": 16.0,
        "capsule_height": 0.0
    }
"""

from typing import Any

from engine.ecs.component import Component


class Collider(Component):
    """
    Componente de colisión. Soporta box, circle, polygon y capsule.

    Atributos:
        width: Ancho del área de colisión
        height: Alto del área de colisión
        offset_x: Desplazamiento horizontal desde Transform
        offset_y: Desplazamiento vertical desde Transform
        is_trigger: Si es True, solo detecta sin bloquear
    """

    def __init__(
        self,
        width: float = 32.0,
        height: float = 32.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        is_trigger: bool = False,
        shape_type: str = "box",
        radius: float = 16.0,
        points: list[list[float]] | None = None,
        friction: float = 0.2,
        restitution: float = 0.0,
        density: float = 1.0,
        capsule_height: float = 0.0,
        one_way_collision: bool = False,
        one_way_collision_direction_y: float = -1.0,
    ) -> None:
        """
        Inicializa el Collider.

        Args:
            width: Ancho del área de colisión
            height: Alto del área de colisión
            offset_x: Offset horizontal desde la posición
            offset_y: Offset vertical desde la posición
            is_trigger: Si solo detecta sin bloquear
            capsule_height: Altura de la sección rectangular de la cápsula
        """
        self.enabled: bool = True
        self.width: float = width
        self.height: float = height
        self.offset_x: float = offset_x
        self.offset_y: float = offset_y
        self.is_trigger: bool = is_trigger
        self.shape_type: str = str(shape_type or "box")
        self.radius: float = radius
        self.points: list[list[float]] = [list(point) for point in (points or [])]
        self.friction: float = friction
        self.restitution: float = restitution
        self.density: float = density
        self.capsule_height: float = capsule_height
        self.one_way_collision: bool = bool(one_way_collision)
        self.one_way_collision_direction_y: float = float(one_way_collision_direction_y)

    def get_bounds(self, x: float, y: float) -> tuple[float, float, float, float]:
        """
        Calcula los límites AABB del collider en coordenadas mundo.
        Para cápsulas: el AABB cubre la cápsula completa (radio + altura).
        """
        cx = x + self.offset_x
        cy = y + self.offset_y

        if self.shape_type == "capsule":
            half_h = self.radius + self.capsule_height / 2
            return (
                cx - self.radius,  # left
                cy - half_h,       # top
                cx + self.radius,  # right
                cy + half_h        # bottom
            )

        half_w = self.width / 2
        half_h = self.height / 2

        return (
            cx - half_w,  # left
            cy - half_h,  # top
            cx + half_w,  # right
            cy + half_h   # bottom
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa el Collider a diccionario."""
        return {
            "enabled": self.enabled,
            "width": self.width,
            "height": self.height,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "is_trigger": self.is_trigger,
            "shape_type": self.shape_type,
            "radius": self.radius,
            "points": [list(point) for point in self.points],
            "friction": self.friction,
            "restitution": self.restitution,
            "density": self.density,
            "capsule_height": self.capsule_height,
            "one_way_collision": self.one_way_collision,
            "one_way_collision_direction_y": self.one_way_collision_direction_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Collider":
        """Crea un Collider desde un diccionario."""
        component = cls(
            width=data.get("width", 32.0),
            height=data.get("height", 32.0),
            offset_x=data.get("offset_x", 0.0),
            offset_y=data.get("offset_y", 0.0),
            is_trigger=data.get("is_trigger", False),
            shape_type=data.get("shape_type", "box"),
            radius=data.get("radius", data.get("width", 32.0) / 2),
            points=data.get("points", []),
            friction=data.get("friction", 0.2),
            restitution=data.get("restitution", 0.0),
            density=data.get("density", 1.0),
            capsule_height=data.get("capsule_height", 0.0),
            one_way_collision=data.get("one_way_collision", False),
            one_way_collision_direction_y=data.get("one_way_collision_direction_y", -1.0),
        )
        component.enabled = data.get("enabled", True)
        return component
