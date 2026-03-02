"""
engine/scenes/__init__.py - Sistema de gestión de escenas

PROPÓSITO:
    Separa Scene (datos originales) de RuntimeWorld (copia en PLAY).
"""

from engine.scenes.scene import Scene
from engine.scenes.scene_manager import SceneManager

__all__ = [
    "Scene",
    "SceneManager",
]
