"""
engine/components/ - Componentes predefinidos del motor

PROPÓSITO:
    Contiene los componentes estándar que vienen con el motor.
    Cada componente es un contenedor de datos específico.

COMPONENTES DISPONIBLES:
    - Transform: Posición, rotación y escala
    - Sprite: Renderizado de imagen/textura
    - Collider: Área de colisión AABB
    - RigidBody: Física básica (velocidad, gravedad)
    - Animator: Animaciones por sprite sheet
"""

from engine.components.transform import Transform
from engine.components.sprite import Sprite
from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.animator import Animator, AnimationData

__all__ = [
    "Transform",
    "Sprite",
    "Collider",
    "RigidBody",
    "Animator",
    "AnimationData",
]
