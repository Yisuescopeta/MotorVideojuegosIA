"""
engine/core/ - Módulos del núcleo del motor

PROPÓSITO:
    Contiene la lógica central del motor: game loop, tiempo e input.

MÓDULOS:
    - game: Clase principal Game con el game loop
    - time_manager: Control de delta time y FPS
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from engine.core.time_manager import TimeManager

if TYPE_CHECKING:
    from engine.core.game import Game


def __getattr__(name: str) -> object:
    if name == "Game":
        from engine.core.game import Game
        return Game
    raise AttributeError(f"module 'engine.core' has no attribute {name!r}")


__all__ = [
    "Game",
    "TimeManager",
]
