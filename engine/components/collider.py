"""
engine/components/collider.py - Componente de colisión AABB

PROPÓSITO:
    Define un área de colisión rectangular (Axis-Aligned Bounding Box).
    Usado para detectar colisiones entre entidades.

PROPIEDADES:
    - width (float): Ancho del área de colisión
    - height (float): Alto del área de colisión
    - offset_x (float): Desplazamiento horizontal desde el Transform
    - offset_y (float): Desplazamiento vertical desde el Transform
    - is_trigger (bool): Si es True, detecta pero no bloquea físicamente

EJEMPLO DE USO:
    collider = Collider(width=32, height=48)
    entity.add_component(collider)

SERIALIZACIÓN JSON:
    {
        "width": 32,
        "height": 48,
        "offset_x": 0,
        "offset_y": 0,
        "is_trigger": false
    }
"""

from typing import Any

from engine.ecs.component import Component


class Collider(Component):
    """
    Componente de colisión AABB (caja alineada a ejes).
    
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
    ) -> None:
        """
        Inicializa el Collider.
        
        Args:
            width: Ancho del área de colisión
            height: Alto del área de colisión
            offset_x: Offset horizontal desde la posición
            offset_y: Offset vertical desde la posición
            is_trigger: Si solo detecta sin bloquear
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
    
    def get_bounds(self, x: float, y: float) -> tuple[float, float, float, float]:
        """
        Calcula los límites del collider en coordenadas mundo.
        
        Args:
            x: Posición X del Transform
            y: Posición Y del Transform
            
        Returns:
            Tupla (left, top, right, bottom)
        """
        # El collider está centrado en la posición
        half_w = self.width / 2
        half_h = self.height / 2
        
        cx = x + self.offset_x
        cy = y + self.offset_y
        
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
        )
        component.enabled = data.get("enabled", True)
        return component
