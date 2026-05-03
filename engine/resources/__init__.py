"""
engine/resources/ - Gestión de recursos y assets

PROPÓSITO:
    Contiene clases para cargar y gestionar recursos del juego
    como texturas, sonidos, etc.

MÓDULOS:
    - texture_manager: Carga y caché de texturas
    - curve_2d: Curva Bezier 2D serializable
"""

from engine.resources.curve_2d import Curve2D
from engine.resources.texture_manager import TextureManager

__all__ = [
    "Curve2D",
    "TextureManager",
]
