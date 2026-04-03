"""Sistemas de runtime del motor.

Las reexportaciones se resuelven de forma perezosa para evitar cargar
dependencias de renderizado al importar el paquete.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "RenderSystem": ("engine.systems.render_system", "RenderSystem"),
    "PhysicsSystem": ("engine.systems.physics_system", "PhysicsSystem"),
    "CollisionSystem": ("engine.systems.collision_system", "CollisionSystem"),
    "AnimationSystem": ("engine.systems.animation_system", "AnimationSystem"),
    "AudioSystem": ("engine.systems.audio_system", "AudioSystem"),
    "InputSystem": ("engine.systems.input_system", "InputSystem"),
    "PlayerControllerSystem": ("engine.systems.player_controller_system", "PlayerControllerSystem"),
    "CharacterControllerSystem": ("engine.systems.character_controller_system", "CharacterControllerSystem"),
    "ScriptBehaviourSystem": ("engine.systems.script_behaviour_system", "ScriptBehaviourSystem"),
}

__all__ = list(_LAZY_IMPORTS)


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(name)
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    names = set(globals()) | set(__all__)
    return sorted(names)
