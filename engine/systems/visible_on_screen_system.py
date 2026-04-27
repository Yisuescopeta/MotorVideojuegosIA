"""
engine/systems/visible_on_screen_system.py - Sistema de deteccion de visibilidad en viewport.

Actualiza VisibleOnScreenNotifier2D y VisibleOnScreenEnabler2D comparando
AABB contra el rect del viewport en coordenadas de mundo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.components.visible_on_screen_notifier_2d import (
    VisibleOnScreenEnabler2D,
    VisibleOnScreenNotifier2D,
)
from engine.ecs.entity import Entity
from engine.ecs.world import World

if TYPE_CHECKING:
    from engine.events.signals import SignalRuntime


class VisibleOnScreenSystem:
    """Sistema que detecta entidades dentro del viewport y emite senales."""

    def __init__(self, signal_runtime: Optional["SignalRuntime"] = None) -> None:
        self._signal_runtime: Optional["SignalRuntime"] = signal_runtime

    def set_signal_runtime(self, signal_runtime: "SignalRuntime") -> None:
        self._signal_runtime = signal_runtime

    def update(
        self,
        world: World,
        viewport_rect: tuple[float, float, float, float] | None = None,
    ) -> None:
        """
        viewport_rect: (left, top, right, bottom) en coordenadas de mundo.
        Si es None, no se procesan notificadores (no hay camara activa).
        """
        if viewport_rect is None:
            return

        left, top, right, bottom = viewport_rect

        # Buscar tanto Notifier2D como Enabler2D (hereda del primero)
        # ya que el indice ECS usa tipos exactos.
        seen_ids: set[int] = set()
        for component_type in (VisibleOnScreenNotifier2D, VisibleOnScreenEnabler2D):
            for entity in world.get_entities_with(component_type):
                if entity.id in seen_ids:
                    continue
                seen_ids.add(entity.id)
                notifier = entity.get_component(component_type)
                if notifier is None or not notifier.enabled:
                    continue
                self._update_notifier(entity, notifier, left, top, right, bottom)

    def _update_notifier(
        self,
        entity: Entity,
        notifier: VisibleOnScreenNotifier2D,
        left: float,
        top: float,
        right: float,
        bottom: float,
    ) -> None:
        from engine.components.transform import Transform

        transform = entity.get_component(Transform)
        if transform is None:
            return

        # Calcular AABB absoluto del notifier
        abs_left = transform.x + notifier.rect_x
        abs_top = transform.y + notifier.rect_y
        abs_right = abs_left + notifier.rect_width
        abs_bottom = abs_top + notifier.rect_height

        # Interseccion AABB vs viewport
        intersects = not (abs_right < left or abs_left > right or abs_bottom < top or abs_top > bottom)

        was_on_screen = notifier._is_on_screen
        is_first_check = not notifier._vos_checked
        notifier._vos_checked = True
        notifier._is_on_screen = intersects

        if intersects and not was_on_screen:
            self._emit(entity, "screen_entered")
            self._try_enable_entity(entity, notifier, True)
        elif not intersects and (was_on_screen or is_first_check):
            self._emit(entity, "screen_exited")
            self._try_enable_entity(entity, notifier, False)

    def _try_enable_entity(
        self,
        entity: Entity,
        notifier: VisibleOnScreenNotifier2D,
        enable: bool,
    ) -> None:
        if not isinstance(notifier, VisibleOnScreenEnabler2D):
            return

        target_entity = None
        if notifier.enable_node_path:
            # Buscar por nombre en el mundo
            owner_world = getattr(entity, "_owner_world", None)
            if owner_world is not None and hasattr(owner_world, "get_entity_by_name"):
                target_entity = owner_world.get_entity_by_name(notifier.enable_node_path)

        if target_entity is None:
            target_entity = entity

        if target_entity is not None:
            target_entity.active = enable

    def _emit(self, entity: Entity, signal_name: str) -> None:
        if self._signal_runtime is None:
            return
        self._signal_runtime.emit(entity.name, signal_name)
