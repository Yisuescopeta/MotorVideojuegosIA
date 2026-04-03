"""Paquete principal del motor de videojuegos 2D.

Las reexportaciones se resuelven de forma perezosa para evitar cargar
dependencias opcionales de runtime, como `pyray`, durante imports de utilidades
de validación o serialización.
"""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "Entity": ("engine.ecs.entity", "Entity"),
    "Component": ("engine.ecs.component", "Component"),
    "World": ("engine.ecs.world", "World"),
    "Transform": ("engine.components.transform", "Transform"),
    "Sprite": ("engine.components.sprite", "Sprite"),
    "Collider": ("engine.components.collider", "Collider"),
    "CharacterController2D": ("engine.components.charactercontroller2d", "CharacterController2D"),
    "Joint2D": ("engine.components.joint2d", "Joint2D"),
    "RigidBody": ("engine.components.rigidbody", "RigidBody"),
    "Animator": ("engine.components.animator", "Animator"),
    "AnimationData": ("engine.components.animator", "AnimationData"),
    "Camera2D": ("engine.components.camera2d", "Camera2D"),
    "AudioSource": ("engine.components.audiosource", "AudioSource"),
    "InputMap": ("engine.components.inputmap", "InputMap"),
    "PlayerController2D": ("engine.components.playercontroller2d", "PlayerController2D"),
    "SceneEntryPoint": ("engine.components.scene_entry_point", "SceneEntryPoint"),
    "SceneTransitionAction": ("engine.components.scene_transition_action", "SceneTransitionAction"),
    "SceneTransitionOnContact": ("engine.components.scene_transition_on_contact", "SceneTransitionOnContact"),
    "SceneTransitionOnInteract": ("engine.components.scene_transition_on_interact", "SceneTransitionOnInteract"),
    "SceneTransitionOnPlayerDeath": ("engine.components.scene_transition_on_player_death", "SceneTransitionOnPlayerDeath"),
    "ScriptBehaviour": ("engine.components.scriptbehaviour", "ScriptBehaviour"),
    "Tilemap": ("engine.components.tilemap", "Tilemap"),
    "RenderSystem": ("engine.systems.render_system", "RenderSystem"),
    "PhysicsSystem": ("engine.systems.physics_system", "PhysicsSystem"),
    "CollisionSystem": ("engine.systems.collision_system", "CollisionSystem"),
    "AnimationSystem": ("engine.systems.animation_system", "AnimationSystem"),
    "AudioSystem": ("engine.systems.audio_system", "AudioSystem"),
    "InputSystem": ("engine.systems.input_system", "InputSystem"),
    "PlayerControllerSystem": ("engine.systems.player_controller_system", "PlayerControllerSystem"),
    "CharacterControllerSystem": ("engine.systems.character_controller_system", "CharacterControllerSystem"),
    "ScriptBehaviourSystem": ("engine.systems.script_behaviour_system", "ScriptBehaviourSystem"),
    "InspectorSystem": ("engine.inspector.inspector_system", "InspectorSystem"),
    "LevelLoader": ("engine.levels.level_loader", "LevelLoader"),
    "ComponentRegistry": ("engine.levels.component_registry", "ComponentRegistry"),
    "create_default_registry": ("engine.levels.component_registry", "create_default_registry"),
    "EventBus": ("engine.events.event_bus", "EventBus"),
    "Event": ("engine.events.event_bus", "Event"),
    "RuleSystem": ("engine.events.rule_system", "RuleSystem"),
    "Scene": ("engine.scenes.scene", "Scene"),
    "SceneManager": ("engine.scenes.scene_manager", "SceneManager"),
    "Game": ("engine.core.game", "Game"),
    "TimeManager": ("engine.core.time_manager", "TimeManager"),
    "EngineState": ("engine.core.engine_state", "EngineState"),
    "TextureManager": ("engine.resources.texture_manager", "TextureManager"),
    "ENGINE_VERSION": ("engine.config", "ENGINE_VERSION"),
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
