"""
engine/systems/ - Sistemas que procesan componentes

PROPÓSITO:
    Los sistemas contienen la LÓGICA del juego.
    Cada sistema procesa entidades que tienen ciertos componentes.

SISTEMAS DISPONIBLES:
    - RenderSystem: Dibuja entidades (sprites, animaciones, placeholders)
    - PhysicsSystem: Aplica gravedad y movimiento
    - CollisionSystem: Detecta colisiones AABB
    - AnimationSystem: Actualiza animaciones por sprite sheet
"""

from engine.systems.render_system import RenderSystem
from engine.systems.physics_system import PhysicsSystem
from engine.systems.collision_system import CollisionSystem
from engine.systems.animation_system import AnimationSystem
from engine.systems.audio_system import AudioSystem
from engine.systems.input_system import InputSystem
from engine.systems.player_controller_system import PlayerControllerSystem
from engine.systems.script_behaviour_system import ScriptBehaviourSystem

__all__ = [
    "RenderSystem",
    "PhysicsSystem",
    "CollisionSystem",
    "AnimationSystem",
    "AudioSystem",
    "InputSystem",
    "PlayerControllerSystem",
    "ScriptBehaviourSystem",
]
