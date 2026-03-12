"""
engine/ - Paquete principal del motor de videojuegos 2D
"""

# ECS
from engine.ecs.entity import Entity
from engine.ecs.component import Component
from engine.ecs.world import World

# Componentes
from engine.components.transform import Transform
from engine.components.sprite import Sprite
from engine.components.collider import Collider
from engine.components.rigidbody import RigidBody
from engine.components.animator import Animator, AnimationData
from engine.components.camera2d import Camera2D
from engine.components.audiosource import AudioSource
from engine.components.inputmap import InputMap
from engine.components.playercontroller2d import PlayerController2D
from engine.components.scriptbehaviour import ScriptBehaviour

# Sistemas
from engine.systems.render_system import RenderSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.animation_system import AnimationSystem
from engine.systems.audio_system import AudioSystem
from engine.systems.input_system import InputSystem
from engine.systems.player_controller_system import PlayerControllerSystem
from engine.systems.script_behaviour_system import ScriptBehaviourSystem

# Inspector
from engine.inspector.inspector_system import InspectorSystem

# Levels
from engine.levels.level_loader import LevelLoader
from engine.levels.component_registry import ComponentRegistry, create_default_registry

# Events
from engine.events.event_bus import EventBus, Event
from engine.events.rule_system import RuleSystem

# Scenes
from engine.scenes.scene import Scene
from engine.scenes.scene_manager import SceneManager

# Core
from engine.core.game import Game
from engine.core.time_manager import TimeManager
from engine.core.engine_state import EngineState

# Resources
from engine.resources.texture_manager import TextureManager

__all__ = [
    # ECS
    "Entity", "Component", "World",
    # Componentes
    "Transform", "Sprite", "Collider", "RigidBody", "Animator", "AnimationData",
    "Camera2D", "AudioSource", "InputMap",
    "PlayerController2D", "ScriptBehaviour",
    # Sistemas
    "RenderSystem", "PhysicsSystem", "CollisionSystem", "AnimationSystem", "AudioSystem", "InputSystem", "PlayerControllerSystem", "ScriptBehaviourSystem",
    # Inspector
    "InspectorSystem",
    # Levels
    "LevelLoader", "ComponentRegistry", "create_default_registry",
    # Events
    "EventBus", "Event", "RuleSystem",
    # Scenes
    "Scene", "SceneManager",
    # Core
    "Game", "TimeManager", "EngineState",
    # Resources
    "TextureManager",
]
