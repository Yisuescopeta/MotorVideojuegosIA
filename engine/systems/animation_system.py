"""
engine/systems/animation_system.py - Sistema de actualizacion de animaciones

PROPOSITO:
    Actualiza las animaciones cada frame.
    Emite eventos on_animation_end cuando una animacion termina.
    Emite eventos on_state_changed cuando cambia el estado.
    Emite eventos on_animation_transition cuando una transicion declarativa aplica.

EVENTOS EMITIDOS:
    - on_animation_end: Una animacion no-loop termina
    - on_state_changed: El estado del animator cambio
    - on_animation_transition: Una transicion declarativa fue aplicada
"""

from typing import TYPE_CHECKING, Optional, Set

from engine.components.animator import AnimationTransition, Animator
from engine.ecs.entity import Entity
from engine.ecs.world import World

if TYPE_CHECKING:
    from engine.events.event_bus import EventBus


class AnimationSystem:
    """Sistema que actualiza las animaciones de todas las entidades."""

    def __init__(self, event_bus: Optional["EventBus"] = None) -> None:
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
        self._try_apply_transition(entity, animator, allow_exit_time=False)

        anim = animator.get_current_animation()
        if anim is None or anim.get_frame_count() <= 0:
            return

        animation_completed = False
        completed_state = animator.current_state
        completed_normalized_time = animator.normalized_time

        if anim.fps > 0 and not (animator.is_finished and not anim.loop):
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
                        animation_completed = True
                        completed_state = animator.current_state
                        completed_normalized_time = animator.normalized_time
                        break

        post_transition_applied = self._try_apply_transition(entity, animator, allow_exit_time=True)

        if not animation_completed:
            return

        self._emit_animation_end(entity, completed_state, completed_normalized_time)

        if post_transition_applied:
            return

        if anim.on_complete is not None:
            previous_state = animator.current_state
            animator.play(anim.on_complete)
            if previous_state != animator.current_state:
                self._emit_state_changed(entity, previous_state, animator.current_state)

    def _try_apply_transition(self, entity: Entity, animator: Animator, *, allow_exit_time: bool) -> bool:
        for transition in animator.get_state_transitions():
            if not self._transition_matches(animator, transition, allow_exit_time=allow_exit_time):
                continue
            if transition.to not in animator.animations:
                continue

            previous_state = animator.current_state
            animator.play(transition.to, force_restart=transition.force_restart)
            transition_applied = transition.force_restart or previous_state != animator.current_state
            if not transition_applied:
                continue

            animator.consume_transition_triggers(transition)
            self._emit_animation_transition(entity, previous_state, animator.current_state, transition.name)
            if previous_state != animator.current_state:
                self._emit_state_changed(entity, previous_state, animator.current_state)
            return True
        return False

    def _transition_matches(self, animator: Animator, transition: AnimationTransition, *, allow_exit_time: bool) -> bool:
        if transition.has_exit_time != allow_exit_time:
            return False
        if allow_exit_time and animator.normalized_time < transition.exit_time:
            return False
        return animator.transition_conditions_match(transition)

    def _emit_animation_end(self, entity: Entity, animation_name: str, normalized_time: float) -> None:
        """Emite evento de animacion terminada."""
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

    def _emit_animation_transition(
        self,
        entity: Entity,
        from_state: str,
        to_state: str,
        transition_name: Optional[str],
    ) -> None:
        """Emite evento de transicion declarativa."""
        if self._event_bus is None:
            return

        self._event_bus.emit("on_animation_transition", {
            "entity": entity.name,
            "entity_id": entity.id,
            "from_state": from_state,
            "to_state": to_state,
            "transition_name": transition_name,
        })
