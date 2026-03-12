"""
engine/components/rigidbody.py - Componente de física básica

PROPÓSITO:
    Añade propiedades físicas simples a una entidad:
    velocidad, gravedad y detección de suelo.

PROPIEDADES:
    - velocity_x (float): Velocidad horizontal (píxeles/segundo)
    - velocity_y (float): Velocidad vertical (píxeles/segundo)
    - gravity_scale (float): Multiplicador de gravedad (0 = sin gravedad)
    - is_grounded (bool): Si la entidad está en el suelo

EJEMPLO DE USO:
    rb = RigidBody(gravity_scale=1.0)
    entity.add_component(rb)
    
    # El PhysicsSystem actualizará la posición
    rb.velocity_x = 100  # Mover a la derecha

SERIALIZACIÓN JSON:
    {
        "velocity_x": 0,
        "velocity_y": 0,
        "gravity_scale": 1.0,
        "is_grounded": false
    }
"""

from typing import Any

from engine.ecs.component import Component


class RigidBody(Component):
    """
    Componente de física básica con velocidad y gravedad.
    
    Atributos:
        velocity_x: Velocidad horizontal (px/s)
        velocity_y: Velocidad vertical (px/s)
        gravity_scale: Multiplicador de gravedad
        is_grounded: Si está tocando el suelo
    """
    
    def __init__(
        self,
        velocity_x: float = 0.0,
        velocity_y: float = 0.0,
        gravity_scale: float = 1.0,
        is_grounded: bool = False
    ) -> None:
        """
        Inicializa el RigidBody.
        
        Args:
            velocity_x: Velocidad horizontal inicial
            velocity_y: Velocidad vertical inicial
            gravity_scale: Multiplicador de gravedad (0=sin gravedad)
            is_grounded: Estado inicial de contacto con suelo
        """
        self.enabled: bool = True
        self.velocity_x: float = velocity_x
        self.velocity_y: float = velocity_y
        self.gravity_scale: float = gravity_scale
        self.is_grounded: bool = is_grounded
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa el RigidBody a diccionario."""
        return {
            "enabled": self.enabled,
            "velocity_x": self.velocity_x,
            "velocity_y": self.velocity_y,
            "gravity_scale": self.gravity_scale,
            "is_grounded": self.is_grounded
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RigidBody":
        """Crea un RigidBody desde un diccionario."""
        component = cls(
            velocity_x=data.get("velocity_x", 0.0),
            velocity_y=data.get("velocity_y", 0.0),
            gravity_scale=data.get("gravity_scale", 1.0),
            is_grounded=data.get("is_grounded", False)
        )
        component.enabled = data.get("enabled", True)
        return component
