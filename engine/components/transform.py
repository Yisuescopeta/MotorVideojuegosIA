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

from typing import Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.components.transform import Transform

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
        """
        # Posición y escala LOCAL
        self.local_x: float = x
        self.local_y: float = y
        self.local_rotation: float = rotation
        self.local_scale_x: float = scale_x
        self.local_scale_y: float = scale_y
        
        # Jerarquía
        self.parent: Optional['Transform'] = None
        self.children: List['Transform'] = []
        
    @property
    def x(self) -> float:
        """Posición global X (calculada recursivamente)."""
        if self.parent:
            return self.parent.x + self.local_x
        return self.local_x
        
    @x.setter
    def x(self, value: float) -> None:
        """Establece posición global X."""
        if self.parent:
            self.local_x = value - self.parent.x
        else:
            self.local_x = value

    @property
    def y(self) -> float:
        """Posición global Y (calculada recursivamente)."""
        if self.parent:
            return self.parent.y + self.local_y
        return self.local_y
        
    @y.setter
    def y(self, value: float) -> None:
        """Establece posición global Y."""
        if self.parent:
            self.local_y = value - self.parent.y
        else:
            self.local_y = value

    @property
    def rotation(self) -> float:
        if self.parent:
            return self.parent.rotation + self.local_rotation
        return self.local_rotation
        
    @rotation.setter
    def rotation(self, value: float) -> None:
        if self.parent:
            self.local_rotation = value - self.parent.rotation
        else:
            self.local_rotation = value

    @property
    def scale_x(self) -> float:
        if self.parent:
            return self.parent.scale_x * self.local_scale_x
        return self.local_scale_x
        
    @scale_x.setter
    def scale_x(self, value: float) -> None:
        if self.parent:
            self.local_scale_x = value / self.parent.scale_x if self.parent.scale_x != 0 else value
        else:
            self.local_scale_x = value

    @property
    def scale_y(self) -> float:
        if self.parent:
            return self.parent.scale_y * self.local_scale_y
        return self.local_scale_y
        
    @scale_y.setter
    def scale_y(self, value: float) -> None:
        if self.parent:
            self.local_scale_y = value / self.parent.scale_y if self.parent.scale_y != 0 else value
        else:
            self.local_scale_y = value

    def set_parent(self, parent: Optional['Transform']) -> None:
        """Asigna un nuevo padre manteniendo la posición global actual."""
        # Guardar posición global actual
        global_x, global_y = self.x, self.y
        
        # Eliminar de padre anterior
        if self.parent:
            self.parent.children.remove(self)
        
        # Asignar nuevo padre
        self.parent = parent
        if self.parent:
            self.parent.children.append(self)
        
        # Restaurar posición global (recalculando local)
        self.x = global_x
        self.y = global_y
        
    def add_child(self, child: 'Transform') -> None:
        """Añade un hijo a este transform."""
        child.set_parent(self)
    
    def set_position(self, x: float, y: float) -> None:
        """
        Establece la posición de la entidad.
        
        Args:
            x: Nueva posición horizontal
            y: Nueva posición vertical
        """
    def set_position(self, x: float, y: float) -> None:
        """Establece la posición global."""
        self.x = x
        self.y = y
    
    def translate(self, dx: float, dy: float) -> None:
        """
        Mueve la entidad una cantidad relativa.
        
        Args:
            dx: Desplazamiento horizontal
            dy: Desplazamiento vertical
        """
    def translate(self, dx: float, dy: float) -> None:
        """Mueve la entidad en coordenadas globales."""
        self.x += dx
        self.y += dy
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa el Transform (guarda valores LOCALES)."""
        return {
            "x": self.local_x,
            "y": self.local_y,
            "rotation": self.local_rotation,
            "scale_x": self.local_scale_x,
            "scale_y": self.local_scale_y
            # Nota: Parent no se serializa aquí para evitar referencias circulares simples en JSON
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
