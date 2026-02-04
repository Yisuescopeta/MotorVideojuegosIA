"""
engine/components/transform.py - Componente de posición y transformación

PROPÓSITO:
    Define la posición, rotación y escala de una entidad en el mundo 2D.
    Es el componente más básico y casi todas las entidades lo tienen.

PROPIEDADES:
    - x (float): Posición horizontal en píxeles
    - y (float): Posición vertical en píxeles
    - rotation (float): Rotación en grados (0-360)
    - scale_x (float): Escala horizontal (1.0 = tamaño normal)
    - scale_y (float): Escala vertical (1.0 = tamaño normal)

EJEMPLO DE USO:
    transform = Transform(x=100, y=200)
    entity.add_component(transform)
    
    # Mover la entidad
    transform.x += 10
    
SERIALIZACIÓN JSON:
    {
        "x": 100.0,
        "y": 200.0,
        "rotation": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0
    }
"""

from typing import Any

from engine.ecs.component import Component


class Transform(Component):
    """
    Componente que define la posición y transformación de una entidad.
    
    Atributos:
        x: Posición horizontal en píxeles
        y: Posición vertical en píxeles
        rotation: Rotación en grados (0-360)
        scale_x: Escala horizontal (1.0 = normal)
        scale_y: Escala vertical (1.0 = normal)
    """
    
    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0
    ) -> None:
        """
        Inicializa el Transform con valores por defecto.
        
        Args:
            x: Posición horizontal inicial
            y: Posición vertical inicial
            rotation: Rotación inicial en grados
            scale_x: Escala horizontal inicial
            scale_y: Escala vertical inicial
        """
        self.x: float = x
        self.y: float = y
        self.rotation: float = rotation
        self.scale_x: float = scale_x
        self.scale_y: float = scale_y
    
    def set_position(self, x: float, y: float) -> None:
        """
        Establece la posición de la entidad.
        
        Args:
            x: Nueva posición horizontal
            y: Nueva posición vertical
        """
        self.x = x
        self.y = y
    
    def translate(self, dx: float, dy: float) -> None:
        """
        Mueve la entidad una cantidad relativa.
        
        Args:
            dx: Desplazamiento horizontal
            dy: Desplazamiento vertical
        """
        self.x += dx
        self.y += dy
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa el Transform a diccionario."""
        return {
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Transform":
        """Crea un Transform desde un diccionario."""
        return cls(
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            rotation=data.get("rotation", 0.0),
            scale_x=data.get("scale_x", 1.0),
            scale_y=data.get("scale_y", 1.0)
        )
