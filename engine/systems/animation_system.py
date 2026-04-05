"""
engine/systems/animation_system.py - Sistema de actualización de animaciones

PROPÓSITO:
    Actualiza las animaciones cada frame.
    Emite eventos on_animation_end cuando una animación termina.
    Emite eventos on_state_changed cuando cambia el estado.

EVENTOS EMITIDOS:
    - on_animation_end: Una animación no-loop termina
    - on_state_changed: El estado del animator cambió
"""

from typing import TYPE_CHECKING, Optional, Set

from engine.components.animator import Animator
from engine.ecs.entity import Entity
from engine.ecs.world import World

if TYPE_CHECKING:
    from engine.events.event_bus import EventBus


class AnimationSystem:
    """Sistema que actualiza las animaciones de todas las entidades."""

    def __init__(self, event_bus: Optional["EventBus"] = None) -> None:
        """
        Inicializa el sistema.

        Args:
            event_bus: Bus de eventos para emitir fin de animación
        """
        self._event_bus: Optional["EventBus"] = event_bus
        self._tracked_animators: Set[int] = set()

    def set_event_bus(self, event_bus: "EventBus") -> None:
        """Asigna el bus de eventos."""
        self._event_bus = event_bus

    def update(self, world: World, delta_time: float) -> None:
        """Actualiza todas las animaciones."""
        entities = world.get_entities_with(Animator)
        current_ids: Set[int] = set()

        for entity in entities:
            animator = entity.get_component(Animator)

            if animator is None:
                continue

            current_ids.add(id(animator))
            self._update_animator(entity, animator, delta_time)

        for animator_id in list(self._tracked_animators):
            if animator_id not in current_ids:
                self._tracked_animators.discard(animator_id)

    def _update_animator(self, entity: Entity, animator: Animator, delta_time: float) -> None:
        """Actualiza un animator individual."""
        anim = animator.get_current_animation()

        if anim is None or anim.get_frame_count() <= 0:
            return

        if animator.is_finished and not anim.loop:
            return

        if anim.fps <= 0:
            return

        effective_delta = delta_time * animator.speed
        frame_duration = 1.0 / anim.fps
        animator.elapsed_time += effective_delta

        while animator.elapsed_time >= frame_duration:
            animator.elapsed_time -= frame_duration
            animator.current_frame += 1

            if animator.current_frame >= anim.get_frame_count():
                if anim.loop:
                    animator.current_frame = 0
                else:
                    animator.current_frame = anim.get_frame_count() - 1
                    animator.is_finished = True

                    self._emit_animation_end(entity, animator.current_state, animator.normalized_time)

                    if anim.on_complete is not None:
                        previous_state = animator.current_state
                        animator.play(anim.on_complete)
                        if previous_state != animator.current_state:
                            self._emit_state_changed(entity, previous_state, animator.current_state)

                    break

    def _emit_animation_end(self, entity: Entity, animation_name: str, normalized_time: float) -> None:
        """Emite evento de animación terminada."""
        if self._event_bus is None:
            return

        self._event_bus.emit("on_animation_end", {
            "entity": entity.name,
            "entity_id": entity.id,
            "animation": animation_name,
            "normalized_time": normalized_time,
        })

    def _emit_state_changed(self, entity: Entity, from_state: str, to_state: str) -> None:
        """Emite evento de cambio de estado."""
        if self._event_bus is None:
            return

        self._event_bus.emit("on_state_changed", {
            "entity": entity.name,
            "entity_id": entity.id,
            "from_state": from_state,
            "to_state": to_state,
        })
