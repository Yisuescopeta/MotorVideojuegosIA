"""
engine/core/ - Módulos del núcleo del motor

PROPÓSITO:
    Contiene la lógica central del motor: game loop, tiempo e input.

MÓDULOS:
    - game: Clase principal Game con el game loop
    - time_manager: Control de delta time y FPS
"""

from engine.core.game import Game
from engine.core.time_manager import TimeManager

__all__ = [
    "Game",
    "TimeManager",
]
