"""
engine/levels/__init__.py - Sistema de carga de niveles

PROPÓSITO:
    Módulo para carga de niveles basados en datos (JSON).
    Permite definir entidades y componentes sin código.
"""

from engine.levels.component_registry import ComponentRegistry
from engine.levels.level_loader import LevelLoader

__all__ = [
    "ComponentRegistry",
    "LevelLoader",
]
