"""
engine/core/ - Modulos del nucleo del motor

PROPOSITO:
    Contiene la logica central del motor: game loop, tiempo e input.

MODULOS:
    - game: Clase principal Game con el game loop
    - time_manager: Control de delta time y FPS
"""

from importlib import import_module

__all__ = [
    "Game",
    "TimeManager",
    "EditorHost",
    "EngineCompositionRoot",
    "RuntimeHost",
]

_MODULE_BY_EXPORT = {
    "Game": "engine.core.game",
    "TimeManager": "engine.core.time_manager",
    "EditorHost": "engine.core.composition_root",
    "EngineCompositionRoot": "engine.core.composition_root",
    "RuntimeHost": "engine.core.composition_root",
}


def __getattr__(name: str):
    module_name = _MODULE_BY_EXPORT.get(name)
    if module_name is None:
        raise AttributeError(f"module 'engine.core' has no attribute {name!r}")
    module = import_module(module_name)
    return getattr(module, name)
