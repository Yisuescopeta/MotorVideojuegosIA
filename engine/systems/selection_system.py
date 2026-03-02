"""
engine/systems/selection_system.py - Sistema de selección de entidades

PROPÓSITO:
    Detecta clicks del mouse sobre entidades en la escena y actualiza
    la selección en el World.

FUNCIONALIDAD:
    - Solo activo en modo EDIT.
    - Detecta click izquierdo.
    - Comprueba colisión punto-rectángulo con entidades.
    - Prioridad de tamaño: Collider > Sprite > Placeholder (32x32).
    - Actualiza world.selected_entity_name.

DEPENDENCIAS:
    - Transform: Requerido.
    - Collider: Opcional (para bounds precisos).
    - Sprite: Opcional (para bounds visuales).
"""

import pyray as rl
from typing import Optional

from engine.ecs.world import World
from engine.ecs.entity import Entity
from engine.components.transform import Transform
from engine.components.collider import Collider
from engine.components.sprite import Sprite
from engine.components.animator import Animator


class SelectionSystem:
    """
    Sistema que gestiona la selección de entidades mediante click.
    """
    
    # Tamaño por defecto para entidades sin tamaño explícito
    DEFAULT_SIZE: int = 32
    
    def update(self, world: World, mouse_world_pos: rl.Vector2) -> None:
        """
        Actualiza el sistema de selección.
        Should be called only in EDIT mode and if mouse is in scene view.
        
        Args:
            world: Mundo con las entidades
            mouse_world_pos: Posición transformada del mouse
        """
        # Solo procesar si hay click izquierdo
        if not rl.is_mouse_button_pressed(rl.MOUSE_BUTTON_LEFT):
            return
            
        mouse_x = mouse_world_pos.x
        mouse_y = mouse_world_pos.y
        
        # UI Check se hace fuera (en Game control loop)
            
        clicked_entity_name: Optional[str] = None
            
        clicked_entity_name: Optional[str] = None
        
        # Iterar todas las entidades con Transform
        # Iteramos en reverso para seleccionar la que se dibuja "encima" (última en la lista)
        # Esto es una aproximación simple al z-order
        entities = world.get_entities_with(Transform)
        for entity in reversed(entities):
            if self._is_point_in_entity(mouse_x, mouse_y, entity):
                clicked_entity_name = entity.name
                break
        
        # Actualizar selección en el mundo
        # Si clicked_entity_name es None, se deselecciona (click en vacío)
        if world.selected_entity_name != clicked_entity_name:
            world.selected_entity_name = clicked_entity_name
            print(f"[SELECTION] Selected: {clicked_entity_name}")
    
    def _is_point_in_entity(self, x: float, y: float, entity: Entity) -> bool:
        """Comprueba si un punto (x,y) está dentro de los límites de una entidad."""
        transform = entity.get_component(Transform)
        if transform is None:
            return False
            
        # 1. Usar Collider si existe (prioridad gameplay)
        collider = entity.get_component(Collider)
        if collider is not None:
            left, top, right, bottom = collider.get_bounds(transform.x, transform.y)
            return left <= x <= right and top <= y <= bottom
            
        # 2. Usar Sprite si existe (prioridad visual)
        # Nota: Sin cargar la textura real, usamos width/height explícitos o default
        width = self.DEFAULT_SIZE
        height = self.DEFAULT_SIZE
        offset_x = 0.5
        offset_y = 0.5
        
        sprite = entity.get_component(Sprite)
        if sprite is not None:
            # Si tiene dimensiones explícitas, usarlas
            if sprite.width > 0: width = sprite.width
            if sprite.height > 0: height = sprite.height
            offset_x = sprite.origin_x
            offset_y = sprite.origin_y
            
        # 3. Usar Animator (frame size)
        animator = entity.get_component(Animator)
        if animator is not None:
            if animator.frame_width > 0: width = animator.frame_width
            if animator.frame_height > 0: height = animator.frame_height
        
        # Aplicar escala
        width *= transform.scale_x
        height *= transform.scale_y
        
        # Calcular bounds centrado en origin
        left = transform.x - (width * offset_x)
        top = transform.y - (height * offset_y)
        right = left + width
        bottom = top + height
        
        return left <= x <= right and top <= y <= bottom
