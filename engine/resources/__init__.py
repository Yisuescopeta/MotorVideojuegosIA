"""
engine/resources/ - Gestión de recursos y assets

PROPÓSITO:
    Contiene clases para cargar y gestionar recursos del juego
    como texturas, sonidos, etc.

MÓDULOS:
    - texture_manager: Carga y caché de texturas
    - curve_2d: Curva Bezier 2D serializable
    - animation_resource: AnimationResource y AnimationTrack serializables
    - sprite_frames_resource: SpriteFramesResource serializable
"""

from engine.resources.animation_resource import AnimationResource, AnimationTrack
from engine.resources.curve_2d import Curve2D
from engine.resources.sprite_frames_resource import SpriteFramesResource
from engine.resources.texture_manager import TextureManager

__all__ = [
    "AnimationResource",
    "AnimationTrack",
    "Curve2D",
    "SpriteFramesResource",
    "TextureManager",
]
