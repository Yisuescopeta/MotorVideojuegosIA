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
    from engine.components.animation_tree import AnimationTree
    from engine.components.animatable_body_2d import AnimatableBody2D
    from engine.components.animator import Animator
    from engine.components.area2d import Area2D
    from engine.components.audio_listener_2d import AudioListener2D
    from engine.components.audio_stream_player_2d import AudioStreamPlayer2D
    from engine.components.audiosource import AudioSource
    from engine.components.camera2d import Camera2D
    from engine.components.canvas import Canvas
    from engine.components.canvas_item_2d import CanvasItem2D
    from engine.components.canvas_layer import CanvasLayer
    from engine.components.particle_emitter2d import ParticleEmitter2D
    from engine.components.charactercontroller2d import CharacterController2D
    from engine.components.collider import Collider
    from engine.components.collision_filter_2d import CollisionFilter2D
    from engine.components.collision_polygon_2d import CollisionPolygon2D
    from engine.components.collision_shape_2d import CollisionShape2D
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
    from engine.components.navigation_obstacle_2d import NavigationObstacle2D
    from engine.components.navigation_region_2d import NavigationRegion2D
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
    from engine.components.static_body_2d import StaticBody2D
    from engine.components.scene_link import SceneLink
    from engine.components.scene_transition_action import SceneTransitionAction
    from engine.components.scene_transition_on_contact import SceneTransitionOnContact
    from engine.components.scene_transition_on_interact import SceneTransitionOnInteract
    from engine.components.scene_transition_on_player_death import SceneTransitionOnPlayerDeath
    from engine.components.scriptbehaviour import ScriptBehaviour
    from engine.components.sprite import Sprite
    from engine.components.tilemap import Tilemap
    from engine.components.sub_viewport import SubViewport, ViewportTexture
    from engine.components.post_process_effect import PostProcessEffectComp
    from engine.components.timer import Timer
    from engine.components.transform import Transform
    from engine.components.tween import Tween
    from engine.components.uibutton import UIButton
    from engine.components.uiimage import UIImage
    from engine.components.uipanel import UIPanel
    from engine.components.ui_popup import UIPopup, UIPopupMenu, UIWindow
    from engine.components.uiscrollcontainer import UIScrollContainer
    from engine.components.ui_splitcontainer import UISplitContainer
    from engine.components.ui_tabbar import UITabBar, UITabContainer
    from engine.components.uitext import UIText
    from engine.components.ui_ninepatch import UINinePatchRect
    from engine.components.ui_texture_button import UITextureButton
    from engine.components.ui_tree import UITree
    from engine.components.uicheckbox import CheckBox
    from engine.components.uilabel import Label
    from engine.components.uilineedit import LineEdit
    from engine.components.uiprogressbar import ProgressBar
    from engine.components.uislider import Slider
    from engine.components.uispinbox import SpinBox
    from engine.components.uitextedit import TextEdit
    from engine.components.backbuffer_copy import BackBufferCopy
    from engine.components.colorrect import ColorRect
    from engine.components.rich_text_label import RichTextLabel
    from engine.components.directional_light_2d import DirectionalLight2D
    from engine.components.parallax_background import ParallaxBackground
    from engine.components.parallax_layer import ParallaxLayer
    from engine.components.path_2d import Path2D
    from engine.components.point_light_2d import PointLight2D
    from engine.components.remote_transform_2d import RemoteTransform2D
    from engine.components.touch_screen_button import TouchScreenButton
    from engine.components.gpu_particles_2d import GPUParticles2D
    from engine.components.animated_sprite_2d import AnimatedSprite2D
    from engine.components.canvas_modulate import CanvasModulate
    from engine.components.raycast_2d import RayCast2D
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
        "CollisionShape2D",
        CollisionShape2D,
        description="Dedicated collision shape (Godot CollisionShape2D). Takes precedence over Collider when both present.",
        default_payload=CollisionShape2D().to_dict(),
        editor_tags=("physics", "layer:Physics", "collision", "shape"),
    )
    registry.register(
        "CollisionPolygon2D",
        CollisionPolygon2D,
        description="Polygon collision shape from vertex data (Godot CollisionPolygon2D).",
        default_payload=CollisionPolygon2D().to_dict(),
        editor_tags=("physics", "layer:Physics", "collision", "polygon"),
    )
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
        "StaticBody2D",
        StaticBody2D,
        description="Immovable physics body (Godot StaticBody2D). No velocity integration, no gravity, infinite mass.",
        default_payload=StaticBody2D().to_dict(),
        editor_tags=("physics", "layer:Physics", "static"),
    )
    registry.register(
        "AnimatableBody2D",
        AnimatableBody2D,
        description="Static body movable by AnimationPlayer (Godot AnimatableBody2D). Syncs collider from Transform when enabled.",
        default_payload=AnimatableBody2D().to_dict(),
        editor_tags=("physics", "layer:Physics", "animation", "static"),
    )
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
    registry.register(
        "AnimationTree",
        AnimationTree,
        description="Arbol de animacion con blend spaces, state machine y blending (adaptado de Godot AnimationTree).",
        default_payload=AnimationTree().to_dict(),
        editor_tags=("animation", "tag:AnimationTree", "layer:Gameplay", "blend"),
    )
    registry.register("Animator", Animator)
    registry.register("Camera2D", Camera2D)
    registry.register("AudioSource", AudioSource)
    registry.register("AudioListener2D", AudioListener2D)
    registry.register(
        "AudioStreamPlayer2D",
        AudioStreamPlayer2D,
        description="Reproduce un AudioStreamResource (adaptado de Godot AudioStreamPlayer2D).",
        default_payload=AudioStreamPlayer2D().to_dict(),
        editor_tags=("audio", "tag:AudioStreamPlayer", "layer:Audio"),
    )
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
        "CanvasLayer",
        CanvasLayer,
        description="Capa de renderizado independiente con su propio transform (adaptado de Godot CanvasLayer).",
        default_payload=CanvasLayer().to_dict(),
        editor_tags=("render", "layer:Visual", "capa"),
    )
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
    registry.register(
        "UIPanel",
        UIPanel,
        description="Panel UI con fondo de color o textura (adaptado de Godot Panel).",
        default_payload=UIPanel().to_dict(),
        editor_tags=("ui", "layer:UI", "container"),
    )
    registry.register(
        "UIScrollContainer",
        UIScrollContainer,
        description="Contenedor con scroll vertical/horizontal (adaptado de Godot ScrollContainer).",
        default_payload=UIScrollContainer().to_dict(),
        editor_tags=("ui", "layer:UI", "container", "scroll"),
    )
    registry.register(
        "UINinePatchRect",
        UINinePatchRect,
        description="Rectangulo 9-slice escalable que divide una textura en 9 regiones (adaptado Godot NinePatchRect).",
        default_payload=UINinePatchRect().to_dict(),
        editor_tags=("ui", "layer:UI", "9patch", "texture"),
    )
    registry.register(
        "UITextureButton",
        UITextureButton,
        description="Boton basado en texturas con estados normal/hover/pressed/disabled (adaptado Godot TextureButton).",
        default_payload=UITextureButton().to_dict(),
        editor_tags=("ui", "layer:UI", "button", "texture"),
    )
    registry.register(
        "LineEdit",
        LineEdit,
        description="Control de entrada de texto de una sola linea (adaptado Godot LineEdit).",
        default_payload=LineEdit().to_dict(),
        editor_tags=("ui", "layer:UI", "input", "text"),
    )
    registry.register(
        "Slider",
        Slider,
        description="Barra deslizante para seleccion de valor numerico (adaptado Godot Slider).",
        default_payload=Slider().to_dict(),
        editor_tags=("ui", "layer:UI", "input", "slider"),
    )
    registry.register(
        "ProgressBar",
        ProgressBar,
        description="Barra de progreso visual (adaptado Godot ProgressBar).",
        default_payload=ProgressBar().to_dict(),
        editor_tags=("ui", "layer:UI", "display", "progress"),
    )
    registry.register(
        "CheckBox",
        CheckBox,
        description="Casilla de verificacion con etiqueta (adaptado Godot CheckBox).",
        default_payload=CheckBox().to_dict(),
        editor_tags=("ui", "layer:UI", "input", "toggle"),
    )
    registry.register(
        "SpinBox",
        SpinBox,
        description="Control de entrada numerica con flechas de incremento/decremento (adaptado Godot SpinBox).",
        default_payload=SpinBox().to_dict(),
        editor_tags=("ui", "layer:UI", "input", "numeric"),
    )
    registry.register(
        "Label",
        Label,
        description="Etiqueta de texto con soporte rich text (adaptado Godot Label).",
        default_payload=Label().to_dict(),
        editor_tags=("ui", "layer:UI", "display", "text"),
    )
    registry.register(
        "RichTextLabel",
        RichTextLabel,
        description="Etiqueta de texto con BBCode styling, word-wrap, scroll y reveal effect (adaptado Godot RichTextLabel).",
        default_payload=RichTextLabel().to_dict(),
        editor_tags=("ui", "layer:UI", "display", "text", "rich"),
    )
    registry.register(
        "UIPopup",
        UIPopup,
        description="Popup modal que aparece sobre el UI con fondo oscuro opcional (adaptado Godot Popup).",
        default_payload=UIPopup().to_dict(),
        editor_tags=("ui", "layer:UI", "modal", "popup"),
    )
    registry.register(
        "UIPopupMenu",
        UIPopupMenu,
        description="Menu popup con items seleccionables y separadores (adaptado Godot PopupMenu).",
        default_payload=UIPopupMenu().to_dict(),
        editor_tags=("ui", "layer:UI", "modal", "menu"),
    )
    registry.register(
        "UIWindow",
        UIWindow,
        description="Ventana arrastrable con barra de titulo y boton de cierre (adaptado Godot Window).",
        default_payload=UIWindow().to_dict(),
        editor_tags=("ui", "layer:UI", "modal", "window"),
    )
    registry.register(
        "TextEdit",
        TextEdit,
        description="Editor de texto multilinea (adaptado Godot TextEdit).",
        default_payload=TextEdit().to_dict(),
        editor_tags=("ui", "layer:UI", "input", "text", "multiline"),
    )
    registry.register(
        "UITabBar",
        UITabBar,
        description="Barra de pestañas con tabs clickeables (adaptado Godot TabBar).",
        default_payload=UITabBar().to_dict(),
        editor_tags=("ui", "layer:UI", "container", "tabs"),
    )
    registry.register(
        "UITabContainer",
        UITabContainer,
        description="Contenedor de pestañas que muestra un hijo por tab (adaptado Godot TabContainer).",
        default_payload=UITabContainer().to_dict(),
        editor_tags=("ui", "layer:UI", "container", "tabs"),
    )
    registry.register(
        "UISplitContainer",
        UISplitContainer,
        description="Contenedor dividido redimensionable entre dos hijos (adaptado Godot SplitContainer).",
        default_payload=UISplitContainer().to_dict(),
        editor_tags=("ui", "layer:UI", "container", "split"),
    )
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
        "NavigationObstacle2D",
        NavigationObstacle2D,
        description="Dynamic obstacle that blocks navigation paths and affects avoidance when active.",
        default_payload=NavigationObstacle2D().to_dict(),
        editor_tags=("navigation", "tag:NavigationObstacle", "layer:Gameplay", "obstacle"),
    )
    registry.register(
        "NavigationRegion2D",
        NavigationRegion2D,
        description="Defines navigable region with cost modifiers and references a NavigationPolygon resource.",
        default_payload=NavigationRegion2D().to_dict(),
        editor_tags=("navigation", "tag:NavigationRegion", "layer:Gameplay", "region"),
    )
    registry.register(
        "PathFollower2D",
        PathFollower2D,
        description="Makes an entity follow a Curve2D path with speed, loop and rotation support.",
        default_payload=PathFollower2D().to_dict(),
        editor_tags=("path", "tag:PathFollower", "layer:Gameplay", "moving"),
    )
    registry.register(
        "ParallaxBackground",
        ParallaxBackground,
        description="Contenedor que agrupa ParallaxLayers con offset/escala/limite compartidos (Godot ParallaxBackground).",
        default_payload=ParallaxBackground().to_dict(),
        editor_tags=("parallax", "layer:Camera", "background", "container"),
    )
    registry.register(
        "ParallaxLayer",
        ParallaxLayer,
        description="Define una capa de parallax que se desplaza relativo al movimiento de camara.",
        default_payload=ParallaxLayer().to_dict(),
        editor_tags=("parallax", "layer:Camera", "background"),
    )
    registry.register(
        "Path2D",
        Path2D,
        description="Define un path Curve2D para PathFollow2D (Godot Path2D).",
        default_payload=Path2D().to_dict(),
        editor_tags=("path", "tag:Path", "layer:Gameplay", "curve"),
    )
    registry.register(
        "PointLight2D",
        PointLight2D,
        description="Luz puntual radial 2D con sombras y textura (Godot PointLight2D).",
        default_payload=PointLight2D().to_dict(),
        editor_tags=("render", "lighting", "layer:Visual", "point"),
    )
    registry.register(
        "ParticleEmitter2D",
        ParticleEmitter2D,
        description="Emisor de particulas 2D calculadas en CPU (equivalente Godot CPUParticles2D).",
        default_payload=ParticleEmitter2D().to_dict(),
        editor_tags=("particles", "render", "layer:Visual", "fx"),
    )
    registry.register(
        "RemoteTransform2D",
        RemoteTransform2D,
        description="Pushes transform (position, rotation, scale) to another entity (Godot RemoteTransform2D).",
        default_payload=RemoteTransform2D().to_dict(),
        editor_tags=("transform", "layer:Gameplay", "remote"),
    )
    registry.register(
        "TouchScreenButton",
        TouchScreenButton,
        description="Button designed for touch screen interaction (Godot TouchScreenButton).",
        default_payload=TouchScreenButton().to_dict(),
        editor_tags=("ui", "touch", "layer:UI", "button"),
    )
    registry.register(
        "GPUParticles2D",
        GPUParticles2D,
        description="GPU-based particles 2D (MVP wrapper, Godot GPUParticles2D).",
        default_payload=GPUParticles2D().to_dict(),
        editor_tags=("particles", "render", "layer:Visual", "fx", "gpu"),
    )
    registry.register(
        "DirectionalLight2D",
        DirectionalLight2D,
        description="Luz direccional 2D que proyecta en una direccion con distancia configurable.",
        default_payload=DirectionalLight2D().to_dict(),
        editor_tags=("render", "lighting", "layer:Visual"),
    )
    registry.register(
        "ColorRect",
        ColorRect,
        description="Rectangulo de color solido para fondos UI o debug.",
        default_payload=ColorRect().to_dict(),
        editor_tags=("ui", "render", "layer:UI", "debug"),
    )
    registry.register(
        "BackBufferCopy",
        BackBufferCopy,
        description="Copia una region de pantalla en un buffer para efectos de post-procesado.",
        default_payload=BackBufferCopy().to_dict(),
        editor_tags=("render", "postfx", "layer:Visual"),
    )
    registry.register(
        "AnimatedSprite2D",
        AnimatedSprite2D,
        description="Sprite animado con soporte de SpriteFrames, modos loop/none/pingpong (Godot AnimatedSprite2D).",
        default_payload=AnimatedSprite2D().to_dict(),
        editor_tags=("animation", "sprite", "layer:Visual", "render"),
    )
    registry.register(
        "RayCast2D",
        RayCast2D,
        description="Rayo 2D que detecta colisiones en linea recta (Godot RayCast2D).",
        default_payload=RayCast2D().to_dict(),
        editor_tags=("physics", "raycast", "layer:Physics", "detection"),
    )
    registry.register(
        "CanvasModulate",
        CanvasModulate,
        description="Aplica un multiply de color sobre todo el canvas (Godot CanvasModulate).",
        default_payload=CanvasModulate().to_dict(),
        editor_tags=("render", "postfx", "layer:Visual", "canvas"),
    )
    registry.register(
        "UITree",
        UITree,
        description="Arbol jerarquico de items con seleccion, checkboxes y columnas (Godot Tree).",
        default_payload=UITree().to_dict(),
        editor_tags=("ui", "layer:UI", "tree", "data"),
    )
    registry.register(
        "SubViewport",
        SubViewport,
        description="Renders a subtree to a texture (Godot SubViewport).",
        default_payload=SubViewport().to_dict(),
        editor_tags=("render", "viewport", "layer:Visual"),
    )
    registry.register(
        "ViewportTexture",
        ViewportTexture,
        description="Texture dynamically updated from a SubViewport (apply to Sprite).",
        default_payload=ViewportTexture().to_dict(),
        editor_tags=("render", "viewport", "layer:Visual", "texture"),
    )
    registry.register(
        "PostProcessEffectComp",
        PostProcessEffectComp,
        description="List of post-processing effects to apply after rendering.",
        default_payload=PostProcessEffectComp().to_dict(),
        editor_tags=("render", "postfx", "layer:Visual"),
    )
    return registry
