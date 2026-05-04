"""
engine/levels/component_registry.py - Registro de componentes para instanciacion dinamica
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type

from engine.ecs.component import Component


class ComponentRegistryError(Exception):
    """Error raised when a component type is not registered."""


@dataclass(frozen=True)
class ComponentDescriptor:
    """Describe un componente registrable y su origen visual."""

    name: str
    component_class: Type[Component]
    origin: str = "native"
    badge: str = "CORE"
    description: str = ""
    default_payload: Dict[str, Any] = field(default_factory=dict)
    editor_tags: tuple[str, ...] = ()


class ComponentRegistry:
    """
    Registro de tipos de componentes para instanciacion dinamica.

    Permite crear componentes por nombre desde datos JSON y consultar
    metadata ligera para la UI del editor.
    """

    def __init__(self) -> None:
        self._components: Dict[str, ComponentDescriptor] = {}

    def register(
        self,
        name: str,
        component_class: Type[Component],
        *,
        origin: str = "native",
        badge: str | None = None,
        description: str = "",
        default_payload: Dict[str, Any] | None = None,
        editor_tags: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        normalized_origin = str(origin or "native").strip().lower() or "native"
        resolved_badge = badge or ("AI" if normalized_origin == "ai_custom" else "CORE")
        normalized_tags = tuple(str(tag).strip() for tag in (editor_tags or ()) if str(tag).strip())
        self._components[name] = ComponentDescriptor(
            name=name,
            component_class=component_class,
            origin=normalized_origin,
            badge=resolved_badge,
            description=str(description or "").strip(),
            default_payload=copy.deepcopy(default_payload or {}),
            editor_tags=normalized_tags,
        )

    def get(self, name: str) -> Optional[Type[Component]]:
        descriptor = self._components.get(name)
        return descriptor.component_class if descriptor is not None else None

    def get_descriptor(self, name: str) -> Optional[ComponentDescriptor]:
        return self._components.get(name)

    def get_origin(self, name: str) -> str:
        descriptor = self.get_descriptor(name)
        return descriptor.origin if descriptor is not None else "unknown"

    def create(self, name: str, data: Dict[str, Any]) -> Component:
        component_class = self.get(name)

        if component_class is None:
            raise ComponentRegistryError(
                f"Component '{name}' not registered. Available: {sorted(self._components.keys())}"
            )

        try:
            if hasattr(component_class, "from_dict"):
                return component_class.from_dict(data)
            return component_class(**data)
        except ComponentRegistryError:
            raise
        except Exception as exc:
            raise ComponentRegistryError(
                f"Component '{name}' creation failed: {exc}. Data: {data}"
            ) from exc

    def list_registered(self) -> list[str]:
        return list(self._components.keys())

    def list_descriptors(self) -> list[ComponentDescriptor]:
        return list(self._components.values())


def create_default_registry() -> ComponentRegistry:
    """Crea un registro con los componentes predeterminados del motor."""
    from engine.components.animation_player_2d import AnimationPlayer2D
    from engine.components.animator import Animator
    from engine.components.area2d import Area2D
    from engine.components.audio_listener_2d import AudioListener2D
    from engine.components.audiosource import AudioSource
    from engine.components.camera2d import Camera2D
    from engine.components.canvas import Canvas
    from engine.components.canvas_item_2d import CanvasItem2D
    from engine.components.particle_emitter2d import ParticleEmitter2D
    from engine.components.charactercontroller2d import CharacterController2D
    from engine.components.collider import Collider
    from engine.components.collision_filter_2d import CollisionFilter2D
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
    from engine.components.navigation_agent_2d import NavigationAgent2D
    from engine.components.path_follower_2d import PathFollower2D
    from engine.components.inputmap import InputMap
    from engine.components.joint2d import Joint2D
    from engine.components.light2d import Light2D
    from engine.components.light_occluder_2d import LightOccluder2D
    from engine.components.line2d import Line2D
    from engine.components.marker2d import Marker2D
    from engine.components.playercontroller2d import PlayerController2D
    from engine.components.polygon2d import Polygon2D
    from engine.components.recttransform import RectTransform
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
    from engine.components.uibutton import UIButton
    from engine.components.uiimage import UIImage
    from engine.components.uitext import UIText
    from engine.components.parallax_layer import ParallaxLayer
    from engine.components.visible_on_screen_notifier_2d import (
        VisibleOnScreenEnabler2D,
        VisibleOnScreenNotifier2D,
    )

    registry = ComponentRegistry()
    registry.register("Transform", Transform)
    registry.register("Sprite", Sprite)
    registry.register(
        "Polygon2D",
        Polygon2D,
        description="2D polygon filled with color or texture.",
        default_payload=Polygon2D().to_dict(),
        editor_tags=("render", "tag:Polygon", "layer:Visual"),
    )
    registry.register("Collider", Collider)
    registry.register(
        "CollisionFilter2D",
        CollisionFilter2D,
        description="Define capas de colisión y máscara para filtrado entre entidades.",
        default_payload=CollisionFilter2D().to_dict(),
        editor_tags=("physics", "layer:Physics", "collision"),
    )
    registry.register(
        "Collectible2D",
        Collectible2D,
        description="Platformer pickup collected by trigger contact.",
        default_payload=Collectible2D().to_dict(),
        editor_tags=("platformer", "tag:Collectible", "layer:Gameplay", "trigger"),
    )
    registry.register(
        "Hazard2D",
        Hazard2D,
        description="Platformer danger area that can damage or respawn the player.",
        default_payload=Hazard2D().to_dict(),
        editor_tags=("platformer", "tag:Hazard", "layer:Gameplay", "trigger"),
    )
    registry.register(
        "Goal2D",
        Goal2D,
        description="Platformer level goal reached by trigger contact.",
        default_payload=Goal2D().to_dict(),
        editor_tags=("platformer", "tag:Goal", "layer:Gameplay", "trigger"),
    )
    registry.register(
        "RespawnPoint2D",
        RespawnPoint2D,
        description="Platformer respawn marker used by hazards and checkpoints.",
        default_payload=RespawnPoint2D().to_dict(),
        editor_tags=("platformer", "tag:Respawn", "layer:Gameplay"),
    )
    registry.register(
        "MovingPlatform2D",
        MovingPlatform2D,
        description="Platformer moving platform that follows a path of waypoints.",
        default_payload=MovingPlatform2D().to_dict(),
        editor_tags=("platformer", "tag:Platform", "layer:Gameplay", "moving"),
    )
    registry.register(
        "EnemyPatrol2D",
        EnemyPatrol2D,
        description="Platformer enemy that patrols between waypoints and damages on contact.",
        default_payload=EnemyPatrol2D().to_dict(),
        editor_tags=("platformer", "tag:Enemy", "layer:Gameplay", "trigger"),
    )
    registry.register(
        "Checkpoint2D",
        Checkpoint2D,
        description="Platformer checkpoint that sets the player respawn position on touch.",
        default_payload=Checkpoint2D().to_dict(),
        editor_tags=("platformer", "tag:Checkpoint", "layer:Gameplay", "trigger"),
    )
    registry.register(
        "KillZone2D",
        KillZone2D,
        description="Platformer kill zone that damages and respawns the player on contact.",
        default_payload=KillZone2D().to_dict(),
        editor_tags=("platformer", "tag:KillZone", "layer:Gameplay", "trigger"),
    )
    registry.register(
        "LevelBounds2D",
        LevelBounds2D,
        description="Platformer level bounds that clamp or respawn the player on exit.",
        default_payload=LevelBounds2D().to_dict(),
        editor_tags=("platformer", "tag:Bounds", "layer:Gameplay"),
    )
    registry.register("CharacterController2D", CharacterController2D)
    registry.register("Joint2D", Joint2D)
    registry.register("Light2D", Light2D)
    registry.register(
        "LightOccluder2D",
        LightOccluder2D,
        description="Bloquea luz 2D creando sombras (adaptado de Godot LightOccluder2D).",
        default_payload=LightOccluder2D().to_dict(),
        editor_tags=("render", "lighting", "occluder", "layer:Visual"),
    )
    registry.register(
        "Line2D",
        Line2D,
        description="2D line with width, color, joint mode, and closed option.",
        default_payload=Line2D().to_dict(),
        editor_tags=("render", "tag:Line", "layer:Visual"),
    )
    registry.register("RigidBody", RigidBody)
    registry.register(
        "Area2D",
        Area2D,
        description="Area de monitoreo 2D que detecta cuerpos y areas entrando/saliendo. Adaptado de Godot Area2D.",
        default_payload=Area2D().to_dict(),
        editor_tags=("physics", "trigger", "layer:Physics", "area"),
    )
    registry.register(
        "AnimationPlayer2D",
        AnimationPlayer2D,
        description="Reproduce AnimationResources en una entidad aplicando tracks de propiedades a sus componentes (adaptado de Godot AnimationPlayer).",
        default_payload=AnimationPlayer2D().to_dict(),
        editor_tags=("animation", "tag:AnimationPlayer", "layer:Gameplay"),
    )
    registry.register("Animator", Animator)
    registry.register("Camera2D", Camera2D)
    registry.register("AudioSource", AudioSource)
    registry.register("AudioListener2D", AudioListener2D)
    registry.register("InputMap", InputMap)
    registry.register("PlayerController2D", PlayerController2D)
    registry.register("RenderOrder2D", RenderOrder2D)
    registry.register("RenderStyle2D", RenderStyle2D)
    registry.register("SceneEntryPoint", SceneEntryPoint)
    registry.register("SceneLink", SceneLink)
    registry.register("SceneTransitionAction", SceneTransitionAction)
    registry.register("SceneTransitionOnContact", SceneTransitionOnContact)
    registry.register("SceneTransitionOnInteract", SceneTransitionOnInteract)
    registry.register("SceneTransitionOnPlayerDeath", SceneTransitionOnPlayerDeath)
    registry.register("ScriptBehaviour", ScriptBehaviour)
    registry.register("ResourcePreloader", ResourcePreloader)
    registry.register("Tilemap", Tilemap)
    registry.register("Canvas", Canvas)
    registry.register(
        "CanvasItem2D",
        CanvasItem2D,
        description="Componente de primitivas de dibujo 2D: rect, circle, line. Adaptado de Godot CanvasItem.",
        default_payload=CanvasItem2D().to_dict(),
        editor_tags=("render", "layer:Visual", "draw"),
    )
    registry.register("RectTransform", RectTransform)
    registry.register("UIText", UIText)
    registry.register("UIButton", UIButton)
    registry.register("UIImage", UIImage)
    registry.register("Timer", Timer)
    registry.register("Marker2D", Marker2D)
    registry.register("Tween", Tween)
    registry.register("VisibleOnScreenNotifier2D", VisibleOnScreenNotifier2D)
    registry.register("VisibleOnScreenEnabler2D", VisibleOnScreenEnabler2D)
    registry.register(
        "NavigationAgent2D",
        NavigationAgent2D,
        description="Navigates an entity toward a target using A* pathfinding on a navigation grid.",
        default_payload=NavigationAgent2D().to_dict(),
        editor_tags=("navigation", "tag:NavigationAgent", "layer:Gameplay", "moving"),
    )
    registry.register(
        "PathFollower2D",
        PathFollower2D,
        description="Makes an entity follow a Curve2D path with speed, loop and rotation support.",
        default_payload=PathFollower2D().to_dict(),
        editor_tags=("path", "tag:PathFollower", "layer:Gameplay", "moving"),
    )
    registry.register(
        "ParallaxLayer",
        ParallaxLayer,
        description="Define una capa de parallax que se desplaza relativo al movimiento de camara.",
        default_payload=ParallaxLayer().to_dict(),
        editor_tags=("parallax", "layer:Camera", "background"),
    )
    registry.register(
        "ParticleEmitter2D",
        ParticleEmitter2D,
        description="Emisor de particulas 2D calculadas en CPU (equivalente Godot CPUParticles2D).",
        default_payload=ParticleEmitter2D().to_dict(),
        editor_tags=("particles", "render", "layer:Visual", "fx"),
    )
    return registry
