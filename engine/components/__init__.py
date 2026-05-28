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

from engine.components.animator import AnimationData, Animator
from engine.components.audiosource import AudioSource
from engine.components.camera2d import Camera2D
from engine.components.charactercontroller2d import CharacterController2D
from engine.components.collider import Collider
from engine.components.collision_shape_set_2d import CollisionShape2DDef, CollisionShapeSet2D
from engine.components.gameplay2d import (
    Checkpoint2D,
    Collectible2D,
    EnemyPatrol2D,
    Goal2D,
    Hazard2D,
    KillZone2D,
    LevelBounds2D,
    MovingPlatform2D,
    RespawnPoint2D,
)
from engine.components.inputmap import InputMap
from engine.components.joint2d import Joint2D
from engine.components.marker2d import Marker2D
from engine.components.mobile_controls_2d import MobileControls2D
from engine.components.playercontroller2d import PlayerController2D
from engine.components.polygon2d import Polygon2D
from engine.components.renderorder2d import RenderOrder2D
from engine.components.renderstyle2d import RenderStyle2D
from engine.components.resource_preloader import ResourcePreloader
from engine.components.rigidbody import RigidBody
from engine.components.scene_entry_point import SceneEntryPoint
from engine.components.scene_link import SceneLink
from engine.components.scene_transition_action import SceneTransitionAction
from engine.components.scene_transition_on_contact import SceneTransitionOnContact
from engine.components.scene_transition_on_interact import SceneTransitionOnInteract
from engine.components.scene_transition_on_player_death import SceneTransitionOnPlayerDeath
from engine.components.scriptbehaviour import ScriptBehaviour
from engine.components.sprite import Sprite
from engine.components.tilemap import Tilemap
from engine.components.timer import Timer
from engine.components.transform import Transform
from engine.components.tween import Tween
from engine.components.visible_on_screen_notifier_2d import (
    VisibleOnScreenEnabler2D,
    VisibleOnScreenNotifier2D,
)

__all__ = [
    "Transform",
    "Sprite",
    "Collider",
    "CollisionShape2DDef",
    "CollisionShapeSet2D",
    "Collectible2D",
    "Hazard2D",
    "Goal2D",
    "RespawnPoint2D",
    "MovingPlatform2D",
    "EnemyPatrol2D",
    "Checkpoint2D",
    "KillZone2D",
    "LevelBounds2D",
    "CharacterController2D",
    "Joint2D",
    "RigidBody",
    "Animator",
    "AnimationData",
    "Camera2D",
    "AudioSource",
    "InputMap",
    "PlayerController2D",
    "Polygon2D",
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
    "Timer",
    "Marker2D",
    "MobileControls2D",
    "ResourcePreloader",
    "Tween",
    "VisibleOnScreenNotifier2D",
    "VisibleOnScreenEnabler2D",
]
