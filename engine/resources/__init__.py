"""
engine/resources/ - Gestión de recursos y assets

PROPÓSITO:
    Contiene clases para cargar y gestionar recursos del juego
    como texturas, sonidos, etc.

MÓDULOS:
    - texture_manager: Carga y caché de texturas
"""

from engine.resources.texture_manager import TextureManager

__all__ = [
    "TextureManager",
]
