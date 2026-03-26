"""
engine/levels/component_registry.py - Registro de componentes para instanciacion dinamica
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Type

from engine.ecs.component import Component


@dataclass(frozen=True)
class ComponentDescriptor:
    """Describe un componente registrable y su origen visual."""

    name: str
    component_class: Type[Component]
    origin: str = "native"
    badge: str = "CORE"


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
    ) -> None:
        normalized_origin = str(origin or "native").strip().lower() or "native"
        resolved_badge = badge or ("AI" if normalized_origin == "ai_custom" else "CORE")
        self._components[name] = ComponentDescriptor(
            name=name,
            component_class=component_class,
            origin=normalized_origin,
            badge=resolved_badge,
        )

    def get(self, name: str) -> Optional[Type[Component]]:
        descriptor = self._components.get(name)
        return descriptor.component_class if descriptor is not None else None

    def get_descriptor(self, name: str) -> Optional[ComponentDescriptor]:
        return self._components.get(name)

    def get_origin(self, name: str) -> str:
        descriptor = self.get_descriptor(name)
        return descriptor.origin if descriptor is not None else "unknown"

    def create(self, name: str, data: Dict[str, Any]) -> Optional[Component]:
        component_class = self.get(name)

        if component_class is None:
            print(f"[ERROR] ComponentRegistry: componente '{name}' no registrado")
            return None

        try:
            if hasattr(component_class, "from_dict"):
                return component_class.from_dict(data)
            return component_class(**data)
        except Exception as exc:
            print(f"[ERROR] ComponentRegistry: error creando '{name}': {exc}")
            return None

    def list_registered(self) -> list[str]:
        return list(self._components.keys())

    def list_descriptors(self) -> list[ComponentDescriptor]:
        return list(self._components.values())


def create_default_registry() -> ComponentRegistry:
    """Crea un registro con los componentes predeterminados del motor."""
    from engine.components.audiosource import AudioSource
    from engine.components.animator import Animator
    from engine.components.camera2d import Camera2D
    from engine.components.charactercontroller2d import CharacterController2D
    from engine.components.canvas import Canvas
    from engine.components.collider import Collider
    from engine.components.inputmap import InputMap
    from engine.components.joint2d import Joint2D
    from engine.components.playercontroller2d import PlayerController2D
    from engine.components.recttransform import RectTransform
    from engine.components.renderorder2d import RenderOrder2D
    from engine.components.renderstyle2d import RenderStyle2D
    from engine.components.rigidbody import RigidBody
    from engine.components.scene_link import SceneLink
    from engine.components.scriptbehaviour import ScriptBehaviour
    from engine.components.sprite import Sprite
    from engine.components.tilemap import Tilemap
    from engine.components.transform import Transform
    from engine.components.uibutton import UIButton
    from engine.components.uitext import UIText

    registry = ComponentRegistry()
    registry.register("Transform", Transform)
    registry.register("Sprite", Sprite)
    registry.register("Collider", Collider)
    registry.register("CharacterController2D", CharacterController2D)
    registry.register("Joint2D", Joint2D)
    registry.register("RigidBody", RigidBody)
    registry.register("Animator", Animator)
    registry.register("Camera2D", Camera2D)
    registry.register("AudioSource", AudioSource)
    registry.register("InputMap", InputMap)
    registry.register("PlayerController2D", PlayerController2D)
    registry.register("RenderOrder2D", RenderOrder2D)
    registry.register("RenderStyle2D", RenderStyle2D)
    registry.register("SceneLink", SceneLink)
    registry.register("ScriptBehaviour", ScriptBehaviour)
    registry.register("Tilemap", Tilemap)
    registry.register("Canvas", Canvas)
    registry.register("RectTransform", RectTransform)
    registry.register("UIText", UIText)
    registry.register("UIButton", UIButton)
    return registry
