"""
engine/components/ - Componentes predefinidos del motor

PROPÓSITO:
    Contiene los componentes estándar que vienen con el motor.
    Cada componente es un contenedor de datos específico.

COMPONENTES DISPONIBLES:
    - Transform: Posición, rotación y escala
    - Sprite: Renderizado de imagen/textura
    - Collider: Área de colisión AABB
    - RigidBody: Física básica (velocidad, gravedad)
    - Animator: Animaciones por sprite sheet
"""

from engine.components.transform import Transform
from engine.components.sprite import Sprite
from engine.components.collider import Collider
from engine.components.charactercontroller2d import CharacterController2D
from engine.components.joint2d import Joint2D
from engine.components.rigidbody import RigidBody
from engine.components.animator import Animator, AnimationData
from engine.components.animator_controller import AnimatorController
from engine.components.camera2d import Camera2D
from engine.components.audiosource import AudioSource
from engine.components.inputmap import InputMap
from engine.components.playercontroller2d import PlayerController2D
from engine.components.renderorder2d import RenderOrder2D
from engine.components.renderstyle2d import RenderStyle2D
from engine.components.scene_entry_point import SceneEntryPoint
from engine.components.scene_link import SceneLink
from engine.components.scene_transition_action import SceneTransitionAction
from engine.components.scene_transition_on_contact import SceneTransitionOnContact
from engine.components.scene_transition_on_interact import SceneTransitionOnInteract
from engine.components.scene_transition_on_player_death import SceneTransitionOnPlayerDeath
from engine.components.scriptbehaviour import ScriptBehaviour
from engine.components.tilemap import Tilemap

__all__ = [
    "Transform",
    "Sprite",
    "Collider",
    "CharacterController2D",
    "Joint2D",
    "RigidBody",
    "Animator",
    "AnimationData",
    "AnimatorController",
    "Camera2D",
    "AudioSource",
    "InputMap",
    "PlayerController2D",
    "RenderOrder2D",
    "RenderStyle2D",
    "SceneEntryPoint",
    "SceneLink",
    "SceneTransitionAction",
    "SceneTransitionOnContact",
    "SceneTransitionOnInteract",
    "SceneTransitionOnPlayerDeath",
    "ScriptBehaviour",
    "Tilemap",
]
