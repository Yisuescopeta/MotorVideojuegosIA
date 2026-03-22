"""
engine/systems/animation_system.py - Sistema de actualización de animaciones

PROPÓSITO:
    Actualiza las animaciones cada frame.
    Emite eventos on_animation_end cuando una animación termina.

EVENTOS EMITIDOS:
    - on_animation_end: Una animación no-loop termina
"""

from typing import Optional, TYPE_CHECKING

from engine.ecs.world import World
from engine.ecs.entity import Entity
from engine.components.animator import Animator

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
    
    def set_event_bus(self, event_bus: "EventBus") -> None:
        """Asigna el bus de eventos."""
        self._event_bus = event_bus
    
    def update(self, world: World, delta_time: float) -> None:
        """Actualiza todas las animaciones."""
        entities = world.get_entities_with(Animator)
        
        for entity in entities:
            animator = entity.get_component(Animator)
            
            if animator is None:
                continue
            
            self._update_animator(entity, animator, delta_time)
    
    def _update_animator(self, entity: Entity, animator: Animator, delta_time: float) -> None:
        """Actualiza un animator individual."""
        anim = animator.get_current_animation()
        
        if anim is None or anim.get_frame_count() <= 0:
            return
        
        if animator.is_finished and not anim.loop:
            return
        
        if anim.fps <= 0:
            return
        
        frame_duration = 1.0 / anim.fps
        animator.elapsed_time += delta_time
        
        while animator.elapsed_time >= frame_duration:
            animator.elapsed_time -= frame_duration
            animator.current_frame += 1
            
            if animator.current_frame >= anim.get_frame_count():
                if anim.loop:
                    animator.current_frame = 0
                else:
                    animator.current_frame = anim.get_frame_count() - 1
                    animator.is_finished = True
                    
                    # Emitir evento de animación terminada
                    self._emit_animation_end(entity, animator.current_state)
                    
                    if anim.on_complete is not None:
                        animator.play(anim.on_complete)
                    
                    break
    
    def _emit_animation_end(self, entity: Entity, animation_name: str) -> None:
        """Emite evento de animación terminada."""
        if self._event_bus is None:
            return
        
        self._event_bus.emit("on_animation_end", {
            "entity": entity.name,
            "entity_id": entity.id,
            "animation": animation_name
        })
