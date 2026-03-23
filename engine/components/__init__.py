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
from engine.components.camera2d import Camera2D
from engine.components.audiosource import AudioSource
from engine.components.inputmap import InputMap
from engine.components.playercontroller2d import PlayerController2D
from engine.components.renderorder2d import RenderOrder2D
from engine.components.scene_link import SceneLink
from engine.components.scriptbehaviour import ScriptBehaviour

__all__ = [
    "Transform",
    "Sprite",
    "Collider",
    "RigidBody",
    "Animator",
    "AnimationData",
    "Camera2D",
    "AudioSource",
    "InputMap",
    "PlayerController2D",
    "RenderOrder2D",
    "SceneLink",
    "ScriptBehaviour",
]
